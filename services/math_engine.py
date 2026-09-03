"""
Motor de Cálculo Proporcional y Matemático para SplitPay.

Provee la función `calculate_proportional_split` para calcular la división
proporcional de gastos compartidos entre los miembros de un hogar según
sus ingresos mensuales declarados.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Union
from uuid import UUID


def calculate_proportional_split(
    total_amount: Union[Decimal, float, int, str],
    members_incomes: Dict[Union[UUID, str], Optional[Union[Decimal, float, int, str]]],
) -> List[Dict[str, Any]]:
    """
    Calcula la división proporcional de un monto total entre un grupo de usuarios,
    basándose en los ingresos declarados de cada uno.

    Comportamiento y Reglas de Negocio:
    1. Si la suma de los ingresos declarados por los miembros es mayor a cero,
       el gasto se divide proporcionalmente a dichos ingresos.
    2. Si ningún miembro ha declarado ingresos (o todos declararon 0 o None),
       se realiza una división equitativa (partes iguales) entre todos los miembros.
    3. Si algún miembro individual tiene ingreso None o menor a cero, se trata como 0.
    4. Garantiza la precisión monetaria en 2 decimales y realiza el ajuste fino
       de centavos por redondeo sobre los miembros con mayor residuo fraccionario,
       asegurando que la suma exacta de las cuotas coincida con `total_amount`.

    :param total_amount: Monto total del gasto a dividir.
    :param members_incomes: Diccionario que mapea identificadores de usuario (UUID o str)
                            a su ingreso mensual declarado (Decimal, float, int, str o None).
    :return: Lista de diccionarios con las llaves 'user_id', 'monto_asignado' (Decimal) y
             'porcentaje_aplicado' (Decimal).
    :raises ValueError: Si el monto total es menor o igual a cero o si el diccionario de miembros está vacío.
    """
    if not isinstance(total_amount, Decimal):
        total_amount = Decimal(str(total_amount))

    total_amount = total_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    if total_amount <= Decimal("0"):
        raise ValueError("El monto total a dividir debe ser mayor a cero.")

    if not members_incomes:
        raise ValueError("Debe proporcionar al menos un miembro para realizar el cálculo de división.")

    num_members = Decimal(len(members_incomes))

    # Normalización de ingresos declarados
    parsed_incomes: Dict[Union[UUID, str], Decimal] = {}
    for user_id, raw_income in members_incomes.items():
        if raw_income is None:
            parsed_incomes[user_id] = Decimal("0")
        else:
            income_dec = Decimal(str(raw_income)) if not isinstance(raw_income, Decimal) else raw_income
            parsed_incomes[user_id] = max(Decimal("0"), income_dec)

    sum_incomes = sum(parsed_incomes.values())

    # Cálculo de porcentajes teóricos y cuotas iniciales
    raw_splits: List[Dict[str, Any]] = []

    for user_id, income in parsed_incomes.items():
        if sum_incomes > Decimal("0"):
            proportion = income / sum_incomes
        else:
            proportion = Decimal("1") / num_members

        raw_amount = total_amount * proportion
        assigned_amount = raw_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        applied_percentage = proportion.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

        raw_splits.append({
            "user_id": user_id,
            "raw_amount": raw_amount,
            "monto_asignado": assigned_amount,
            "porcentaje_aplicado": applied_percentage,
            "remainder": raw_amount - assigned_amount,
        })

    # Ajuste por redondeo de centavos sobrantes o faltantes
    calculated_sum = sum(item["monto_asignado"] for item in raw_splits)
    difference = total_amount - calculated_sum

    if difference != Decimal("0"):
        cent = Decimal("0.01") if difference > Decimal("0") else Decimal("-0.01")
        steps = int(abs(difference) / Decimal("0.01"))

        # Ordenar por residuo fraccionario para asignar centavos con criterio justo
        sorted_splits = sorted(
            raw_splits,
            key=lambda x: x["remainder"],
            reverse=(difference > Decimal("0")),
        )

        for i in range(steps):
            sorted_splits[i % len(sorted_splits)]["monto_asignado"] += cent

    # Construir lista de resultados final
    results: List[Dict[str, Any]] = []
    for item in raw_splits:
        results.append({
            "user_id": item["user_id"],
            "monto_asignado": item["monto_asignado"],
            "porcentaje_aplicado": item["porcentaje_aplicado"],
        })

    return results
