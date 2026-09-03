"""
Endpoints para la importación masiva de datos externos en SplitPay.

Provee la funcionalidad para procesar archivos CSV exportados de plataformas
como Splitwise e importar sus gastos al historial de un hogar.
"""

import csv
import io
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session, joinedload

from database import get_db
from dependencies import get_current_user
from models.expense import EstadoAprobacionEnum, Expense
from models.household import Household
from models.member import HouseholdMember
from models.split import ExpenseSplit
from models.user import User
from schemas import ImportSplitwiseResponse
from services.math_engine import calculate_proportional_split

router = APIRouter(prefix="/api/import", tags=["Importación"])


def _parse_date(date_str: str) -> date:
    """Intenta convertir cadenas con representaciones comunes de fecha a un objeto date."""
    if not date_str:
        return date.today()
    date_str = date_str.strip()
    formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%Y/%m/%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%d-%m-%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    try:
        return date.fromisoformat(date_str[:10])
    except ValueError:
        return date.today()


def _clean_amount(val_str: str) -> Optional[Decimal]:
    """Limpia símbolos monetarios y formatea valores numéricos a Decimal."""
    if not val_str:
        return None
    cleaned = val_str.replace("$", "").replace("€", "").replace("COP", "").replace("USD", "").replace("EUR", "").strip()
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        parts = cleaned.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            cleaned = cleaned.replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    try:
        val = Decimal(cleaned)
        return val if val > Decimal("0") else None
    except (InvalidOperation, ValueError):
        return None


@router.post(
    "/splitwise",
    response_model=ImportSplitwiseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Importar gastos masivamente desde un archivo CSV exportado de Splitwise",
)
async def import_splitwise_csv(
    household_id: UUID = Query(..., description="ID del hogar al que se asignarán los gastos importados"),
    file: UploadFile = File(..., description="Archivo CSV exportado de Splitwise"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    Recibe un archivo CSV de exportación de Splitwise y procesa sus filas para registrar
    los gastos en el hogar especificado.

    Parsea las columnas estándar de Splitwise (Date, Description, Cost, Currency) y las mapea
    a la estructura de la base de datos de SplitPay.
    Calcula automáticamente las cuotas (splits) de cada miembro del hogar utilizando el
    motor de división proporcional. Requiere que el usuario autenticado sea miembro del hogar.
    """
    if file.filename and not file.filename.lower().endswith(".csv"):
        if file.content_type and "csv" not in file.content_type.lower() and "plain" not in file.content_type.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo subido debe ser un archivo de texto en formato CSV.",
            )

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
            detail="No tienes permiso para importar gastos en este hogar.",
        )

    memberships = (
        db.query(HouseholdMember)
        .options(joinedload(HouseholdMember.usuario))
        .filter(HouseholdMember.household_id == household_id)
        .all()
    )
    if not memberships:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El hogar no cuenta con miembros registrados.",
        )

    members_incomes = {
        m.user_id: m.usuario.ingreso_mensual_declarado for m in memberships
    }

    member_map = {}
    for m in memberships:
        if m.usuario.nombre_completo:
            member_map[m.usuario.nombre_completo.strip().lower()] = m.user_id
        if m.usuario.email:
            member_map[m.usuario.email.strip().lower()] = m.user_id

    contents = await file.read()
    try:
        decoded_content = contents.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            decoded_content = contents.decode("latin-1")
        except UnicodeDecodeError:
            decoded_content = contents.decode("utf-8", errors="ignore")

    csv_reader = csv.DictReader(io.StringIO(decoded_content))

    if not csv_reader.fieldnames:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo CSV está vacío o no contiene un formato de encabezados válido.",
        )

    fieldnames_lower = {fn.strip().lower(): fn for fn in csv_reader.fieldnames if fn}

    # Splitwise column identification
    date_col = next((fieldnames_lower[k] for k in fieldnames_lower if k in ("date", "fecha") or "date" in k or "fecha" in k), None)
    desc_col = next((fieldnames_lower[k] for k in fieldnames_lower if k in ("description", "descripcion", "detalle") or "desc" in k or "detalle" in k or "item" in k or "concept" in k), None)
    cost_col = next((fieldnames_lower[k] for k in fieldnames_lower if k in ("cost", "costo", "amount", "monto", "total") or "cost" in k or "amount" in k or "monto" in k or "total" in k or "valor" in k), None)
    curr_col = next((fieldnames_lower[k] for k in fieldnames_lower if k in ("currency", "moneda") or "currency" in k or "moneda" in k), None)
    payer_col = next((fieldnames_lower[k] for k in fieldnames_lower if "payer" in k or "pagado" in k or "paid" in k), None)

    created_expenses = []
    messages = []

    for row_idx, row in enumerate(csv_reader, start=2):
        if not any(row.values()):
            continue

        desc = row.get(desc_col, "").strip() if desc_col else ""
        if not desc:
            desc = row.get("Description", row.get("Descripcion", f"Gasto importado #{row_idx}")).strip()

        if "deleted" in desc.lower():
            messages.append(f"Fila {row_idx}: Ignorada por estar marcada como eliminada ('{desc}').")
            continue

        cost_str = row.get(cost_col, "").strip() if cost_col else ""
        monto_total = _clean_amount(cost_str) if cost_str else None

        if not monto_total:
            for k, v in row.items():
                if v and k not in (desc_col, date_col, curr_col):
                    m = _clean_amount(str(v))
                    if m:
                        monto_total = m
                        break

        if not monto_total:
            messages.append(f"Fila {row_idx}: Ignorada por no contener un monto válido.")
            continue

        raw_date = row.get(date_col, "").strip() if date_col else ""
        fecha_gasto = _parse_date(raw_date) if raw_date else date.today()

        moneda = row.get(curr_col, "").strip().upper() if curr_col else household.moneda_base
        if not moneda or len(moneda) != 3:
            moneda = household.moneda_base

        pagado_por_id = current_user.id
        if payer_col and row.get(payer_col):
            payer_str = row.get(payer_col).strip().lower()
            if payer_str in member_map:
                pagado_por_id = member_map[payer_str]

        new_expense = Expense(
            household_id=household_id,
            pagado_por_id=pagado_por_id,
            descripcion=desc[:255],
            monto_total=monto_total,
            moneda=moneda,
            fecha_gasto=fecha_gasto,
            estado_aprobacion=EstadoAprobacionEnum.PENDIENTE,
        )
        db.add(new_expense)
        db.flush()

        calculated_splits = calculate_proportional_split(
            total_amount=monto_total,
            members_incomes=members_incomes,
        )

        for split_info in calculated_splits:
            user_id = split_info["user_id"]
            is_pagador = (user_id == pagado_por_id)
            split_record = ExpenseSplit(
                expense_id=new_expense.id,
                user_id=user_id,
                monto_asignado=split_info["monto_asignado"],
                porcentaje_aplicado=split_info["porcentaje_aplicado"],
                aprobado_por_usuario=is_pagador,
                fecha_aprobacion=datetime.now(timezone.utc) if is_pagador else None,
            )
            db.add(split_record)

        created_expenses.append(new_expense)

    db.commit()

    for exp in created_expenses:
        db.refresh(exp)

    return {
        "household_id": household_id,
        "gastos_importados": len(created_expenses),
        "mensajes": messages,
        "gastos": created_expenses,
    }
"