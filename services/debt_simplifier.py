"""
Servicio de Simplificación de Deudas para SplitPay.

Calcula los saldos netos de todos los miembros de un hogar a partir de los
gastos aprobados y genera el conjunto consolidado de transferencias requeridas
para saldar las deudas, canalizadas a través del Tesorero Dinámico del hogar.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from models.expense import EstadoAprobacionEnum, Expense
from models.household import Household
from models.member import HouseholdMember
from models.split import ExpenseSplit
from models.user import User
from services.currency_converter import convert_amount
from services.payment_router import generate_nequi_deep_link


def calculate_member_balances(db: Session, household_id: UUID) -> Dict[UUID, Decimal]:
    """
    Calcula el saldo neto de cada miembro dentro de un hogar.

    Solo se consideran los gastos que han sido aprobados en su totalidad
    (estado_aprobacion == APROBADO). Para cada gasto aprobado:
    - El pagador recibe un crédito por el monto total desembolsado (+monto_total).
    - Cada participante en el split recibe un débito por la cuota asignada (-monto_asignado).

    Si la moneda del gasto difiere de la moneda base del hogar, se invoca `convert_amount`
    para expresar los saldos netos en la moneda base del hogar.

    :param db: Sesión de base de datos SQLAlchemy.
    :param household_id: Identificador único del hogar.
    :return: Diccionario que mapea el ID de cada usuario a su saldo neto (Decimal).
    :raises ValueError: Si el hogar especificado no existe.
    """
    household = db.query(Household).filter(Household.id == household_id).first()
    if not household:
        raise ValueError(f"El hogar con ID {household_id} no existe.")

    members = (
        db.query(HouseholdMember)
        .filter(HouseholdMember.household_id == household_id)
        .all()
    )

    balances: Dict[UUID, Decimal] = {m.user_id: Decimal("0.00") for m in members}

    approved_expenses = (
        db.query(Expense)
        .filter(
            Expense.household_id == household_id,
            Expense.estado_aprobacion == EstadoAprobacionEnum.APROBADO,
        )
        .all()
    )

    for expense in approved_expenses:
        if expense.moneda != household.moneda_base:
            monto_exp = convert_amount(expense.monto_total, expense.moneda, household.moneda_base)
        else:
            monto_exp = expense.monto_total

        pagador_id = expense.pagado_por_id
        if pagador_id in balances:
            balances[pagador_id] += monto_exp
        else:
            balances[pagador_id] = monto_exp

        splits = (
            db.query(ExpenseSplit)
            .filter(ExpenseSplit.expense_id == expense.id)
            .all()
        )
        for split in splits:
            if expense.moneda != household.moneda_base:
                monto_split = convert_amount(split.monto_asignado, expense.moneda, household.moneda_base)
            else:
                monto_split = split.monto_asignado

            if split.user_id in balances:
                balances[split.user_id] -= monto_split
            else:
                balances[split.user_id] = -monto_split

    # Asegurar redondeo estandarizado a dos decimales para cada saldo
    for user_id, amount in balances.items():
        balances[user_id] = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return balances


def simplify_household_debts(
    db: Session, household_id: UUID
) -> Dict[str, Any]:
    """
    Cruza todos los saldos netos de un hogar y retorna las transferencias únicas requeridas.

    Si el hogar cuenta con un Tesorero Dinámico asignado (`es_tesorero_dinamico == True`), 
    todas las deudas se centralizan: los usuarios deudores realizan transferencias hacia
    el tesorero actual, y el tesorero distribuye los fondos correspondientes a los acreedores.

    Si no existe un tesorero dinámico asignado, aplica un algoritmo voraz (greedy)
    para resolver las deudas directamente entre deudores y acreedores con el menor número
    de transferencias posibles.

    Para cada transferencia calculada, enruta el pago intentando generar un deep link
    de Nequi si el acreedor tiene teléfono registrado.

    :param db: Sesión de base de datos SQLAlchemy.
    :param household_id: Identificador único del hogar.
    :return: Diccionario con la estructura requerida para `DebtSimplificationResponse`:
             - household_id: UUID
             - tesorero_id: Optional[UUID]
             - saldos_netos: Dict[UUID, Decimal]
             - transferencias: List[Dict[str, Any]]
    :raises ValueError: Si el hogar no existe.
    """
    balances = calculate_member_balances(db, household_id)

    treasurer_member = (
        db.query(HouseholdMember)
        .filter(
            HouseholdMember.household_id == household_id,
            HouseholdMember.es_tesorero_dinamico.is_(True),
        )
        .first()
    )

    tesorero_id: Optional[UUID] = treasurer_member.user_id if treasurer_member else None
    transfers: List[Dict[str, Any]] = []

    cent = Decimal("0.01")

    if tesorero_id is not None:
        # Tesorería Dinámica: centralizar cobros y pagos en el tesorero actual
        for user_id, balance in balances.items():
            if balance < -cent and user_id != tesorero_id:
                # El usuario le debe al hogar -> Transfiere hacia el tesorero
                monto = abs(balance).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                transfers.append({
                    "deudor_id": user_id,
                    "acreedor_id": tesorero_id,
                    "monto": monto,
                })
            elif balance > cent and user_id != tesorero_id:
                # El hogar le debe al usuario -> El tesorero le transfiere al usuario
                monto = balance.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                transfers.append({
                    "deudor_id": tesorero_id,
                    "acreedor_id": user_id,
                    "monto": monto,
                })
    else:
        # Fallback sin tesorero: Cruce voraz directo entre deudores y acreedores
        creditors: List[Dict[str, Any]] = []
        debtors: List[Dict[str, Any]] = []

        for user_id, balance in balances.items():
            if balance > cent:
                creditors.append({"user_id": user_id, "amount": balance})
            elif balance < -cent:
                debtors.append({"user_id": user_id, "amount": abs(balance)})

        creditors.sort(key=lambda x: x["amount"], reverse=True)
        debtors.sort(key=lambda x: x["amount"], reverse=True)

        i, j = 0, 0
        while i < len(debtors) and j < len(creditors):
            debtor = debtors[i]
            creditor = creditors[j]

            transfer_amount = min(debtor["amount"], creditor["amount"]).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

            if transfer_amount > Decimal("0"):
                transfers.append({
                    "deudor_id": debtor["user_id"],
                    "acreedor_id": creditor["user_id"],
                    "monto": transfer_amount,
                })

            debtor["amount"] -= transfer_amount
            creditor["amount"] -= transfer_amount

            if debtor["amount"] <= cent:
                i += 1
            if creditor["amount"] <= cent:
                j += 1

    # Enriquecer las transferencias con nequi_deep_link consultando los teléfonos de los acreedores
    acreedores_ids = list({t["acreedor_id"] for t in transfers})
    if acreedores_ids:
        acreedores = db.query(User).filter(User.id.in_(acreedores_ids)).all()
        phones_map = {u.id: u.telefono for u in acreedores}
    else:
        phones_map = {}

    for transfer in transfers:
        creditor_phone = phones_map.get(transfer["acreedor_id"])
        transfer["nequi_deep_link"] = generate_nequi_deep_link(creditor_phone, transfer["monto"])

    return {
        "household_id": household_id,
        "tesorero_id": tesorero_id,
        "saldos_netos": balances,
        "transferencias": transfers,
    }
