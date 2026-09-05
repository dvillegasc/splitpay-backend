"""
Endpoints para la gestión de gastos y división de cuotas en SplitPay.

Permite registrar gastos, calcular las cuotas mediante el motor matemático
proporcional, aprobar las cuotas individuales de los usuarios y consultar el
historial de gastos de los hogares.
"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload, selectinload

from database import get_db
from dependencies import get_current_user
from models.expense import EstadoAprobacionEnum, Expense
from models.household import Household
from models.member import HouseholdMember
from models.split import ExpenseSplit
from models.user import User
from schemas import ExpenseCreate, ExpenseResponse
from services.math_engine import calculate_proportional_split

router = APIRouter(tags=["Gastos"])


@router.post(
    "/api/expenses",
    response_model=ExpenseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un nuevo gasto y calcular sus cuotas (splits) con estado pendiente",
)
def create_expense(
    expense_in: ExpenseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Expense:
    """
    Registra un gasto en un hogar, calcula las cuotas (splits) correspondientes
    a cada miembro del hogar mediante el motor matemático proporcional y guarda
    los registros en 'Expense' y 'ExpenseSplit' con estado de aprobación 'pendiente'.
    """
    if expense_in.splits is not None:
        total_splits_amount = sum(split.monto_asignado for split in expense_in.splits)
        if total_splits_amount != expense_in.monto_total:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La suma del monto asignado de las cuotas (splits) debe ser exactamente igual al monto total del gasto.",
            )

    household = db.query(Household).filter(Household.id == expense_in.household_id).first()
    if not household:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El hogar especificado no existe.",
        )

    requester_membership = (
        db.query(HouseholdMember)
        .filter(
            HouseholdMember.household_id == expense_in.household_id,
            HouseholdMember.user_id == current_user.id,
        )
        .first()
    )
    if not requester_membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para registrar gastos en este hogar.",
        )

    pagador_membership = (
        db.query(HouseholdMember)
        .filter(
            HouseholdMember.household_id == expense_in.household_id,
            HouseholdMember.user_id == expense_in.pagado_por_id,
        )
        .first()
    )
    if not pagador_membership:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario que pagó el gasto debe ser miembro del hogar.",
        )

    memberships = (
        db.query(HouseholdMember)
        .options(joinedload(HouseholdMember.usuario))
        .filter(HouseholdMember.household_id == expense_in.household_id)
        .all()
    )

    if not memberships:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El hogar no cuenta con miembros registrados.",
        )

    household_member_ids = {m.user_id for m in memberships}

    if expense_in.splits:
        for split in expense_in.splits:
            if split.user_id not in household_member_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"El usuario {split.user_id} especificado en los splits no es miembro del hogar.",
                )

    new_expense = Expense(
        household_id=expense_in.household_id,
        pagado_por_id=expense_in.pagado_por_id,
        descripcion=expense_in.descripcion,
        monto_total=expense_in.monto_total,
        moneda=expense_in.moneda,
        fecha_gasto=expense_in.fecha_gasto,
        estado_aprobacion=EstadoAprobacionEnum.PENDIENTE,
    )

    db.add(new_expense)
    db.flush()

    if expense_in.splits:
        for split_in in expense_in.splits:
            is_pagador = split_in.user_id == expense_in.pagado_por_id
            split_record = ExpenseSplit(
                expense_id=new_expense.id,
                user_id=split_in.user_id,
                monto_asignado=split_in.monto_asignado,
                porcentaje_aplicado=split_in.porcentaje_aplicado,
                aprobado_por_usuario=is_pagador,
                fecha_aprobacion=datetime.now(timezone.utc) if is_pagador else None,
            )
            db.add(split_record)
    else:
        members_incomes = {
            m.user_id: m.usuario.ingreso_mensual_declarado for m in memberships
        }

        calculated_splits = calculate_proportional_split(
            total_amount=expense_in.monto_total,
            members_incomes=members_incomes,
        )

        for split_info in calculated_splits:
            user_id = split_info["user_id"]
            is_pagador = user_id == expense_in.pagado_por_id
            split_record = ExpenseSplit(
                expense_id=new_expense.id,
                user_id=user_id,
                monto_asignado=split_info["monto_asignado"],
                porcentaje_aplicado=split_info["porcentaje_aplicado"],
                aprobado_por_usuario=is_pagador,
                fecha_aprobacion=datetime.now(timezone.utc) if is_pagador else None,
            )
            db.add(split_record)

    db.commit()
    db.refresh(new_expense)

    return new_expense


@router.put(
    "/api/expenses/{expense_id}/approve",
    response_model=ExpenseResponse,
    status_code=status.HTTP_200_OK,
    summary="Aprobar la cuota individual (split) de un gasto para el usuario autenticado",
)
def approve_expense_split(
    expense_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Expense:
    """
    Marca la cuota (ExpenseSplit) del usuario autenticado en un gasto específico como aprobada.

    Si todas las cuotas asociadas al gasto resultan aprobadas tras esta acción,
    el estado de aprobación general del gasto pasa automáticamente a 'aprobado'.
    """
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El gasto especificado no existe.",
        )

    split = (
        db.query(ExpenseSplit)
        .filter(
            ExpenseSplit.expense_id == expense_id,
            ExpenseSplit.user_id == current_user.id,
        )
        .first()
    )
    if not split:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No tienes una cuota asignada en este gasto.",
        )

    split.aprobado_por_usuario = True
    split.fecha_aprobacion = datetime.now(timezone.utc)

    db.flush()

    all_splits = db.query(ExpenseSplit).filter(ExpenseSplit.expense_id == expense_id).all()
    if all(s.aprobado_por_usuario for s in all_splits):
        expense.estado_aprobacion = EstadoAprobacionEnum.APROBADO

    db.commit()
    db.refresh(expense)

    return expense


@router.get(
    "/api/households/{household_id}/expenses",
    response_model=list[ExpenseResponse],
    status_code=status.HTTP_200_OK,
    summary="Obtener el historial de gastos de un hogar ordenados por fecha descendente",
)
def get_household_expenses(
    household_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Expense]:
    """
    Retorna el historial de gastos registrados en un hogar, ordenados por fecha de gasto descendente.

    Requiere que el usuario autenticado sea miembro del hogar especificado.
    """
    household = db.query(Household).filter(Household.id == household_id).first()
    if not household:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El hogar especificado no existe.",
        )

    requester_membership = (
        db.query(HouseholdMember)
        .filter(
            HouseholdMember.household_id == household_id,
            HouseholdMember.user_id == current_user.id,
        )
        .first()
    )
    if not requester_membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver los gastos de este hogar.",
        )

    expenses = (
        db.query(Expense)
        .options(selectinload(Expense.splits))
        .filter(Expense.household_id == household_id)
        .order_by(Expense.fecha_gasto.desc(), Expense.created_at.desc())
        .all()
    )

    return expenses
