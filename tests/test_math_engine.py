"""
Pruebas unitarias en pytest para el Motor Matemático de SplitPay (`calculate_proportional_split`).

Prueba los siguientes escenarios:
- Todos los ingresos en cero o None.
- Un solo miembro con ingreso y los demás en cero o None.
- Ingresos negativos (tratados como cero).
- Verificación de que la suma de `monto_asignado` siempre coincida exactamente con `total_amount`.
- Validaciones de entrada (monto <= 0, miembros vacíos).
"""

from decimal import Decimal
from uuid import uuid4

import pytest

from services.math_engine import calculate_proportional_split


def test_calculate_proportional_split_all_incomes_zero_or_none() -> None:
    """Verifica que si todos los ingresos son cero o None, el gasto se divida equitativamente."""
    u1, u2, u3 = uuid4(), uuid4(), uuid4()
    members_incomes = {
        u1: Decimal("0.00"),
        u2: 0,
        u3: None,
    }
    total_amount = Decimal("100.00")

    result = calculate_proportional_split(total_amount, members_incomes)

    # La suma total asignada debe coincidir exactamente con el monto total
    total_assigned = sum(item["monto_asignado"] for item in result)
    assert total_assigned == Decimal("100.00")

    # Cada miembro debe recibir una cuota cercana a 33.33 / 33.34 por el ajuste de centavos
    assigned_map = {item["user_id"]: item["monto_asignado"] for item in result}
    assert assigned_map[u1] in (Decimal("33.33"), Decimal("33.34"))
    assert assigned_map[u2] in (Decimal("33.33"), Decimal("33.34"))
    assert assigned_map[u3] in (Decimal("33.33"), Decimal("33.34"))


def test_calculate_proportional_split_single_member_with_income() -> None:
    """Verifica que si un solo miembro declara ingreso positivo y otros cero/None, asuma el 100% del gasto."""
    u1, u2, u3 = uuid4(), uuid4(), uuid4()
    members_incomes = {
        u1: Decimal("5000000.00"),
        u2: Decimal("0.00"),
        u3: None,
    }
    total_amount = Decimal("150000.00")

    result = calculate_proportional_split(total_amount, members_incomes)

    total_assigned = sum(item["monto_asignado"] for item in result)
    assert total_assigned == Decimal("150000.00")

    assigned_map = {item["user_id"]: item["monto_asignado"] for item in result}
    assert assigned_map[u1] == Decimal("150000.00")
    assert assigned_map[u2] == Decimal("0.00")
    assert assigned_map[u3] == Decimal("0.00")


def test_calculate_proportional_split_negative_incomes() -> None:
    """Verifica que los ingresos negativos sean tratados como 0."""
    u1, u2, u3 = uuid4(), uuid4(), uuid4()
    members_incomes = {
        u1: -1000,
        u2: Decimal("-500.00"),
        u3: Decimal("2000.00"),
    }
    total_amount = Decimal("300.00")

    result = calculate_proportional_split(total_amount, members_incomes)

    total_assigned = sum(item["monto_asignado"] for item in result)
    assert total_assigned == Decimal("300.00")

    assigned_map = {item["user_id"]: item["monto_asignado"] for item in result}
    assert assigned_map[u1] == Decimal("0.00")
    assert assigned_map[u2] == Decimal("0.00")
    assert assigned_map[u3] == Decimal("300.00")


@pytest.mark.parametrize(
    "total_amount, incomes",
    [
        (Decimal("100.00"), {"a": Decimal("1000"), "b": Decimal("2000"), "c": Decimal("3000")}),
        (Decimal("0.01"), {"a": 100, "b": 200, "c": 300}),
        (Decimal("10.05"), {"a": 0, "b": 0, "c": 0}),
        (Decimal("333.33"), {"a": 1500.50, "b": 2500.75, "c": 3500.25, "d": 4500.10}),
        (Decimal("1000000.00"), {"a": "1234567.89", "b": "9876543.21", "c": None}),
    ],
)
def test_calculate_proportional_split_sum_always_equals_total_amount(total_amount, incomes) -> None:
    """Garantiza que la suma de monto_asignado sea EXACTAMENTE igual a total_amount en diversos casos."""
    result = calculate_proportional_split(total_amount, incomes)

    total_assigned = sum(item["monto_asignado"] for item in result)
    assert total_assigned == total_amount


def test_calculate_proportional_split_standard_proportional() -> None:
    """Verifica el cálculo proporcional estándar entre dos usuarios con ingresos conocidos."""
    u1, u2 = uuid4(), uuid4()
    members_incomes = {
        u1: Decimal("2000.00"),
        u2: Decimal("1000.00"),
    }
    total_amount = Decimal("300.00")

    result = calculate_proportional_split(total_amount, members_incomes)

    total_assigned = sum(item["monto_asignado"] for item in result)
    assert total_assigned == Decimal("300.00")

    assigned_map = {item["user_id"]: item["monto_asignado"] for item in result}
    assert assigned_map[u1] == Decimal("200.00")
    assert assigned_map[u2] == Decimal("100.00")


def test_calculate_proportional_split_invalid_inputs() -> None:
    """Verifica la generación de excepciones al ingresar montos inválidos o listas de miembros vacías."""
    u1 = uuid4()

    with pytest.raises(ValueError, match="monto total a dividir debe ser mayor a cero"):
        calculate_proportional_split(Decimal("0.00"), {u1: 1000})

    with pytest.raises(ValueError, match="monto total a dividir debe ser mayor a cero"):
        calculate_proportional_split(Decimal("-50.00"), {u1: 1000})

    with pytest.raises(ValueError, match="Debe proporcionar al menos un miembro"):
        calculate_proportional_split(Decimal("100.00"), {})
"