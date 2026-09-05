"""
Endpoints para la gestión de hogares en SplitPay.

Permite la creación de hogares, la administración de sus miembros,
la asignación/votación del tesorero dinámico y la consulta de saldos y deudas simplificadas.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from database import get_db
from dependencies import get_current_user
from models.household import Household
from models.member import HouseholdMember
from models.user import User
from schemas import (
    DebtSimplificationResponse,
    HouseholdCreate,
    HouseholdMemberAdd,
    HouseholdMemberResponse,
    HouseholdResponse,
    HouseholdTreasurerUpdate,
)
from services.debt_simplifier import simplify_household_debts

router = APIRouter(prefix="/api/households", tags=["Hogares"])


@router.post(
    "",
    response_model=HouseholdResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un nuevo hogar y asignar al creador como miembro fundador",
)
def create_household(
    household_in: HouseholdCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Household:
    """
    Crea un nuevo hogar en el sistema y asigna automáticamente al usuario autenticado
    como su primer miembro (miembro fundador).
    """
    new_household = Household(
        nombre=household_in.nombre,
        moneda_base=household_in.moneda_base,
    )
    db.add(new_household)
    db.flush()  # Asigna un UUID a new_household.id antes de confirmar la transacción

    founding_member = HouseholdMember(
        user_id=current_user.id,
        household_id=new_household.id,
        es_tesorero_dinamico=False,
    )
    db.add(founding_member)

    db.commit()
    db.refresh(new_household)

    return new_household


@router.get(
    "/me",
    response_model=list[HouseholdResponse],
    status_code=status.HTTP_200_OK,
    summary="Obtener la lista de hogares a los que pertenece el usuario autenticado",
)
def get_my_households(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Household]:
    """
    Retorna la lista de todos los hogares a los que pertenece el usuario actualmente autenticado.
    """
    households = (
        db.query(Household)
        .join(HouseholdMember, HouseholdMember.household_id == Household.id)
        .filter(HouseholdMember.user_id == current_user.id)
        .all()
    )
    return households


@router.post(
    "/{household_id}/members",
    response_model=HouseholdMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Añadir un nuevo miembro (roomie) al hogar",
)
def add_household_member(
    household_id: UUID,
    member_in: HouseholdMemberAdd,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HouseholdMember:
    """
    Añade un nuevo miembro (roomie) a un hogar existente.

    Requiere que el usuario autenticado sea miembro del hogar en cuestión.
    Verifica que el hogar exista, el usuario a añadir exista y no esté
    previamente registrado como miembro en el hogar.
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
            detail="No tienes permiso para agregar miembros a este hogar.",
        )

    new_member_user = db.query(User).filter(User.id == member_in.user_id).first()
    if not new_member_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El usuario que se desea agregar no existe.",
        )

    existing_membership = (
        db.query(HouseholdMember)
        .filter(
            HouseholdMember.household_id == household_id,
            HouseholdMember.user_id == member_in.user_id,
        )
        .first()
    )
    if existing_membership:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario ya es miembro de este hogar.",
        )

    if member_in.es_tesorero_dinamico:
        existing_treasurer = (
            db.query(HouseholdMember)
            .filter(
                HouseholdMember.household_id == household_id,
                HouseholdMember.es_tesorero_dinamico.is_(True),
            )
            .first()
        )
        if existing_treasurer:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El hogar ya cuenta con un tesorero dinámico asignado.",
            )

    new_member = HouseholdMember(
        household_id=household_id,
        user_id=member_in.user_id,
        es_tesorero_dinamico=member_in.es_tesorero_dinamico,
    )
    db.add(new_member)
    db.commit()
    db.refresh(new_member)

    return new_member


@router.get(
    "/{household_id}/members",
    response_model=list[HouseholdMemberResponse],
    status_code=status.HTTP_200_OK,
    summary="Obtener la lista de miembros de un hogar",
)
def get_household_members(
    household_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[HouseholdMember]:
    """
    Retorna la lista de miembros de un hogar con sus datos de usuario anidados.

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
            detail="No tienes permiso para ver los miembros de este hogar.",
        )

    members = (
        db.query(HouseholdMember)
        .options(joinedload(HouseholdMember.usuario))
        .filter(HouseholdMember.household_id == household_id)
        .all()
    )

    return members


@router.put(
    "/{household_id}/treasurer",
    response_model=HouseholdMemberResponse,
    status_code=status.HTTP_200_OK,
    summary="Actualizar el tesorero dinámico de un hogar",
)
def update_household_treasurer(
    household_id: UUID,
    treasurer_in: HouseholdTreasurerUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HouseholdMember:
    """
    Actualiza el flag es_tesorero_dinamico de un miembro específico en el hogar (votación de tesorero).

    Garantiza que solo exista un tesorero dinámico por hogar desmarcando al tesorero anterior
    antes de asignar el nuevo rol al miembro indicado. Requiere que el usuario autenticado sea miembro del hogar.
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
            detail="No perteneces a este hogar.",
        )

    target_membership = (
        db.query(HouseholdMember)
        .filter(
            HouseholdMember.household_id == household_id,
            HouseholdMember.user_id == treasurer_in.user_id,
        )
        .first()
    )
    if not target_membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El usuario especificado no es miembro de este hogar.",
        )

    if treasurer_in.es_tesorero_dinamico:
        current_treasurers = (
            db.query(HouseholdMember)
            .filter(
                HouseholdMember.household_id == household_id,
                HouseholdMember.es_tesorero_dinamico.is_(True),
            )
            .all()
        )
        for treasurer in current_treasurers:
            treasurer.es_tesorero_dinamico = False

    target_membership.es_tesorero_dinamico = treasurer_in.es_tesorero_dinamico
    db.commit()
    db.refresh(target_membership)

    return target_membership


@router.get(
    "/{household_id}/balances",
    response_model=DebtSimplificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener el resumen de deudas y saldos simplificados del hogar",
)
def get_household_balances(
    household_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    Retorna los saldos netos de todos los miembros del hogar y la lista de
    transferencias optimizadas (simplificación de deudas).

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
            detail="No tienes permiso para ver los balances de este hogar.",
        )

    try:
        debt_summary = simplify_household_debts(db, household_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    return debt_summary
