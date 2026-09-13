"""
Pruebas unitarias en pytest para el servicio de simplificación de deudas (`simplify_household_debts`).

Cubre los siguientes escenarios:
- Hogar sin tesorero asignado (modo greedy / voraz).
- Hogar con tesorero dinámico asignado (centralización de transferencias).
- Hogar donde el tesorero dinámico tiene saldo neto propio (acreedor o deudor).
- Gastos con moneda distinta a la moneda base del hogar (verificando invocación de `convert_amount`).
- Filtrado exclusivo de gastos en estado APROBADO.
- Generación de enlaces Nequi deep link.
- Validación de excepciones al consultar hogares inexistentes.
"""

from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from models.expense import EstadoAprobacionEnum, Expense
from models.household import Household
from models.member import HouseholdMember
from models.split import ExpenseSplit
from models.user import User
from services.debt_simplifier import calculate_member_balances, simplify_household_debts


@pytest.fixture
def db_session():
    """Fixture para crear una base de datos SQLite en memoria para cada prueba."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_simplify_household_debts_no_treasurer_greedy_mode(db_session):
    """
    Verifica la simplificación de deudas en un hogar sin tesorero asignado (modo greedy).

    Escenario:
    - Miembros: User A, User B, User C.
    - Expense de $300 pagado por User B (Aprobado).
    - Splits: $100 para A, $100 para B, $100 para C.
    - Saldos netos: B = +200, A = -100, C = -100.
    - Resultado: A le paga 100 a B, C le paga 100 a B.
    """
    user_a = User(id=uuid4(), nombre_completo="User A", email="a@example.com", hashed_password="pwd", telefono="3001111111")
    user_b = User(id=uuid4(), nombre_completo="User B", email="b@example.com", hashed_password="pwd", telefono="3002222222")
    user_c = User(id=uuid4(), nombre_completo="User C", email="c@example.com", hashed_password="pwd", telefono="3003333333")
    db_session.add_all([user_a, user_b, user_c])

    household = Household(id=uuid4(), nombre="Hogar Sin Tesorero", moneda_base="COP")
    db_session.add(household)
    db_session.flush()

    m1 = HouseholdMember(household_id=household.id, user_id=user_a.id, es_tesorero_dinamico=False)
    m2 = HouseholdMember(household_id=household.id, user_id=user_b.id, es_tesorero_dinamico=False)
    m3 = HouseholdMember(household_id=household.id, user_id=user_c.id, es_tesorero_dinamico=False)
    db_session.add_all([m1, m2, m3])

    expense = Expense(
        id=uuid4(),
        household_id=household.id,
        pagado_por_id=user_b.id,
        descripcion="Supermercado",
        monto_total=Decimal("300.00"),
        monto_total_moneda_base=Decimal("300.00"),
        moneda="COP",
        estado_aprobacion=EstadoAprobacionEnum.APROBADO,
    )
    db_session.add(expense)
    db_session.flush()

    s1 = ExpenseSplit(expense_id=expense.id, user_id=user_a.id, monto_asignado=Decimal("100.00"), aprobado_por_usuario=True)
    s2 = ExpenseSplit(expense_id=expense.id, user_id=user_b.id, monto_asignado=Decimal("100.00"), aprobado_por_usuario=True)
    s3 = ExpenseSplit(expense_id=expense.id, user_id=user_c.id, monto_asignado=Decimal("100.00"), aprobado_por_usuario=True)
    db_session.add_all([s1, s2, s3])
    db_session.commit()

    result = simplify_household_debts(db_session, household.id)

    assert result["household_id"] == household.id
    assert result["tesorero_id"] is None
    assert result["saldos_netos"][user_b.id] == Decimal("200.00")
    assert result["saldos_netos"][user_a.id] == Decimal("-100.00")
    assert result["saldos_netos"][user_c.id] == Decimal("-100.00")

    transfers = result["transferencias"]
    assert len(transfers) == 2

    # Ambas transferencias deben ir dirigidas a User B (acreedor)
    for t in transfers:
        assert t["acreedor_id"] == user_b.id
        assert t["monto"] == Decimal("100.00")
        assert t["nequi_deep_link"] == "nequi://pay?phone=3002222222&amount=100.00"

    deudores = {t["deudor_id"] for t in transfers}
    assert deudores == {user_a.id, user_c.id}


def test_simplify_household_debts_with_assigned_treasurer(db_session):
    """
    Verifica la simplificación centralizada cuando el hogar tiene un tesorero asignado.

    Escenario:
    - Miembros: User A, User B, Tesorero T (`es_tesorero_dinamico=True`).
    - Expense de $300 pagado por User A (Aprobado).
    - Splits: $100 para A, $100 para B, $100 para T.
    - Saldos netos: A = +200, B = -100, T = -100.
    - Transferencias esperadas:
      - B (-100) le transfiere 100 al Tesorero T.
      - Tesorero T le transfiere 200 al acreedor A.
    """
    user_a = User(id=uuid4(), nombre_completo="User A", email="a@example.com", hashed_password="pwd", telefono="3001111111")
    user_b = User(id=uuid4(), nombre_completo="User B", email="b@example.com", hashed_password="pwd", telefono="3002222222")
    user_t = User(id=uuid4(), nombre_completo="Tesorero T", email="t@example.com", hashed_password="pwd", telefono="3009999999")
    db_session.add_all([user_a, user_b, user_t])

    household = Household(id=uuid4(), nombre="Hogar Con Tesorero", moneda_base="COP")
    db_session.add(household)
    db_session.flush()

    m1 = HouseholdMember(household_id=household.id, user_id=user_a.id, es_tesorero_dinamico=False)
    m2 = HouseholdMember(household_id=household.id, user_id=user_b.id, es_tesorero_dinamico=False)
    m_t = HouseholdMember(household_id=household.id, user_id=user_t.id, es_tesorero_dinamico=True)
    db_session.add_all([m1, m2, m_t])

    expense = Expense(
        id=uuid4(),
        household_id=household.id,
        pagado_por_id=user_a.id,
        descripcion="Servicios Públicos",
        monto_total=Decimal("300.00"),
        monto_total_moneda_base=Decimal("300.00"),
        moneda="COP",
        estado_aprobacion=EstadoAprobacionEnum.APROBADO,
    )
    db_session.add(expense)
    db_session.flush()

    s1 = ExpenseSplit(expense_id=expense.id, user_id=user_a.id, monto_asignado=Decimal("100.00"), aprobado_por_usuario=True)
    s2 = ExpenseSplit(expense_id=expense.id, user_id=user_b.id, monto_asignado=Decimal("100.00"), aprobado_por_usuario=True)
    st = ExpenseSplit(expense_id=expense.id, user_id=user_t.id, monto_asignado=Decimal("100.00"), aprobado_por_usuario=True)
    db_session.add_all([s1, s2, st])
    db_session.commit()

    result = simplify_household_debts(db_session, household.id)

    assert result["tesorero_id"] == user_t.id
    assert result["saldos_netos"][user_a.id] == Decimal("200.00")
    assert result["saldos_netos"][user_b.id] == Decimal("-100.00")
    assert result["saldos_netos"][user_t.id] == Decimal("-100.00")

    transfers = result["transferencias"]
    assert len(transfers) == 2

    # Transferencia 1: Deudor B paga a Tesorero T
    t_from_b = next(t for t in transfers if t["deudor_id"] == user_b.id)
    assert t_from_b["acreedor_id"] == user_t.id
    assert t_from_b["monto"] == Decimal("100.00")
    assert t_from_b["nequi_deep_link"] == "nequi://pay?phone=3009999999&amount=100.00"

    # Transferencia 2: Tesorero T paga a Acreedor A
    t_to_a = next(t for t in transfers if t["acreedor_id"] == user_a.id)
    assert t_to_a["deudor_id"] == user_t.id
    assert t_to_a["monto"] == Decimal("200.00")
    assert t_to_a["nequi_deep_link"] == "nequi://pay?phone=3001111111&amount=200.00"


def test_simplify_household_debts_treasurer_with_own_positive_balance(db_session):
    """
    Verifica el comportamiento cuando el tesorero tiene saldo neto propio como acreedor.

    Escenario:
    - Miembros: User A, User B, Tesorero T (`es_tesorero_dinamico=True`).
    - Expense de $300 pagado por el Tesorero T (Aprobado).
    - Splits: $100 para A, $100 para B, $100 para T.
    - Saldos netos: T = +200 (Acreedor), A = -100 (Deudor), B = -100 (Deudor).
    - Transferencias esperadas:
      - A (-100) le transfiere 100 al Tesorero T.
      - B (-100) le transfiere 100 al Tesorero T.
      - T no se transfiere a sí mismo; recibe $200 en total que cubren su saldo acreedor.
    """
    user_a = User(id=uuid4(), nombre_completo="User A", email="a@example.com", hashed_password="pwd", telefono="3001111111")
    user_b = User(id=uuid4(), nombre_completo="User B", email="b@example.com", hashed_password="pwd", telefono="3002222222")
    user_t = User(id=uuid4(), nombre_completo="Tesorero T", email="t@example.com", hashed_password="pwd", telefono="3009999999")
    db_session.add_all([user_a, user_b, user_t])

    household = Household(id=uuid4(), nombre="Hogar Tesorero Acreedor", moneda_base="COP")
    db_session.add(household)
    db_session.flush()

    m1 = HouseholdMember(household_id=household.id, user_id=user_a.id, es_tesorero_dinamico=False)
    m2 = HouseholdMember(household_id=household.id, user_id=user_b.id, es_tesorero_dinamico=False)
    m_t = HouseholdMember(household_id=household.id, user_id=user_t.id, es_tesorero_dinamico=True)
    db_session.add_all([m1, m2, m_t])

    expense = Expense(
        id=uuid4(),
        household_id=household.id,
        pagado_por_id=user_t.id,
        descripcion="Alquiler Pagado por Tesorero",
        monto_total=Decimal("300.00"),
        monto_total_moneda_base=Decimal("300.00"),
        moneda="COP",
        estado_aprobacion=EstadoAprobacionEnum.APROBADO,
    )
    db_session.add(expense)
    db_session.flush()

    s1 = ExpenseSplit(expense_id=expense.id, user_id=user_a.id, monto_asignado=Decimal("100.00"), aprobado_por_usuario=True)
    s2 = ExpenseSplit(expense_id=expense.id, user_id=user_b.id, monto_asignado=Decimal("100.00"), aprobado_por_usuario=True)
    st = ExpenseSplit(expense_id=expense.id, user_id=user_t.id, monto_asignado=Decimal("100.00"), aprobado_por_usuario=True)
    db_session.add_all([s1, s2, st])
    db_session.commit()

    result = simplify_household_debts(db_session, household.id)

    assert result["tesorero_id"] == user_t.id
    assert result["saldos_netos"][user_t.id] == Decimal("200.00")
    assert result["saldos_netos"][user_a.id] == Decimal("-100.00")
    assert result["saldos_netos"][user_b.id] == Decimal("-100.00")

    transfers = result["transferencias"]
    assert len(transfers) == 2

    for t in transfers:
        assert t["acreedor_id"] == user_t.id
        assert t["monto"] == Decimal("100.00")
        assert t["nequi_deep_link"] == "nequi://pay?phone=3009999999&amount=100.00"

    deudores = {t["deudor_id"] for t in transfers}
    assert deudores == {user_a.id, user_b.id}


def test_simplify_household_debts_different_currency(db_session):
    """
    Verifica que si Expense.moneda difiere de household.moneda_base,
    se invoque `convert_amount` y el saldo final quede expresado en la moneda base del hogar.

    Escenario:
    - Hogar con moneda_base = 'COP'.
    - Gasto registrado en USD ($100.00 USD) pagado por User A (Aprobado).
    - Splits: $50.00 USD para User A y $50.00 USD para User B.
    - Tasa de cambio simulada: 1 USD = 4000 COP.
    - Invocación de `convert_amount` verificada mediante mock.
    - Saldo final expresado en COP: User A = +200,000 COP, User B = -200,000 COP.
    """
    user_a = User(id=uuid4(), nombre_completo="User A", email="a@example.com", hashed_password="pwd", telefono="3001111111")
    user_b = User(id=uuid4(), nombre_completo="User B", email="b@example.com", hashed_password="pwd", telefono="3002222222")
    db_session.add_all([user_a, user_b])

    household = Household(id=uuid4(), nombre="Hogar Multidivisa", moneda_base="COP")
    db_session.add(household)
    db_session.flush()

    m1 = HouseholdMember(household_id=household.id, user_id=user_a.id, es_tesorero_dinamico=False)
    m2 = HouseholdMember(household_id=household.id, user_id=user_b.id, es_tesorero_dinamico=False)
    db_session.add_all([m1, m2])

    expense = Expense(
        id=uuid4(),
        household_id=household.id,
        pagado_por_id=user_a.id,
        descripcion="Reserva en USD",
        monto_total=Decimal("100.00"),
        monto_total_moneda_base=Decimal("400000.00"),
        moneda="USD",
        estado_aprobacion=EstadoAprobacionEnum.APROBADO,
    )
    db_session.add(expense)
    db_session.flush()

    s1 = ExpenseSplit(expense_id=expense.id, user_id=user_a.id, monto_asignado=Decimal("50.00"), aprobado_por_usuario=True)
    s2 = ExpenseSplit(expense_id=expense.id, user_id=user_b.id, monto_asignado=Decimal("50.00"), aprobado_por_usuario=True)
    db_session.add_all([s1, s2])
    db_session.commit()

    with patch("services.debt_simplifier.convert_amount") as mock_convert:
        mock_convert.side_effect = lambda amount, from_curr, to_curr: (
            Decimal(str(amount)) * Decimal("4000")
        ).quantize(Decimal("0.01"))

        result = simplify_household_debts(db_session, household.id)

        # Verificación de que convert_amount fue invocado
        assert mock_convert.called
        assert mock_convert.call_count >= 1

        # Verificación de que el saldo final quedó en la moneda base del hogar (COP)
        assert result["saldos_netos"][user_a.id] == Decimal("200000.00")
        assert result["saldos_netos"][user_b.id] == Decimal("-200000.00")

        transfers = result["transferencias"]
        assert len(transfers) == 1
        assert transfers[0]["deudor_id"] == user_b.id
        assert transfers[0]["acreedor_id"] == user_a.id
        assert transfers[0]["monto"] == Decimal("200000.00")


def test_simplify_household_debts_only_approved_expenses_counted(db_session):
    """Verifica que los gastos pendientes o rechazados no afecten los saldos netos ni transferencias."""
    user_a = User(id=uuid4(), nombre_completo="User A", email="a@example.com", hashed_password="pwd")
    user_b = User(id=uuid4(), nombre_completo="User B", email="b@example.com", hashed_password="pwd")
    db_session.add_all([user_a, user_b])

    household = Household(id=uuid4(), nombre="Hogar Gastos Mixtos", moneda_base="COP")
    db_session.add(household)
    db_session.flush()

    m1 = HouseholdMember(household_id=household.id, user_id=user_a.id, es_tesorero_dinamico=False)
    m2 = HouseholdMember(household_id=household.id, user_id=user_b.id, es_tesorero_dinamico=False)
    db_session.add_all([m1, m2])

    # Gasto Pendiente (no debe contarse)
    e_pending = Expense(
        id=uuid4(),
        household_id=household.id,
        pagado_por_id=user_a.id,
        descripcion="Gasto Pendiente",
        monto_total=Decimal("100.00"),
        monto_total_moneda_base=Decimal("100.00"),
        moneda="COP",
        estado_aprobacion=EstadoAprobacionEnum.PENDIENTE,
    )
    db_session.add(e_pending)
    db_session.flush()
    s_p1 = ExpenseSplit(expense_id=e_pending.id, user_id=user_a.id, monto_asignado=Decimal("50.00"), aprobado_por_usuario=True)
    s_p2 = ExpenseSplit(expense_id=e_pending.id, user_id=user_b.id, monto_asignado=Decimal("50.00"), aprobado_por_usuario=False)
    db_session.add_all([s_p1, s_p2])

    # Gasto Rechazado (no debe contarse)
    e_rejected = Expense(
        id=uuid4(),
        household_id=household.id,
        pagado_por_id=user_b.id,
        descripcion="Gasto Rechazado",
        monto_total=Decimal("200.00"),
        monto_total_moneda_base=Decimal("200.00"),
        moneda="COP",
        estado_aprobacion=EstadoAprobacionEnum.RECHAZADO,
    )
    db_session.add(e_rejected)
    db_session.flush()
    s_r1 = ExpenseSplit(expense_id=e_rejected.id, user_id=user_a.id, monto_asignado=Decimal("100.00"), aprobado_por_usuario=False)
    s_r2 = ExpenseSplit(expense_id=e_rejected.id, user_id=user_b.id, monto_asignado=Decimal("100.00"), aprobado_por_usuario=False)
    db_session.add_all([s_r1, s_r2])

    db_session.commit()

    balances = calculate_member_balances(db_session, household.id)
    assert balances[user_a.id] == Decimal("0.00")
    assert balances[user_b.id] == Decimal("0.00")

    result = simplify_household_debts(db_session, household.id)
    assert len(result["transferencias"]) == 0


def test_simplify_household_debts_non_existent_household(db_session):
    """Verifica que se lance una excepción ValueError cuando el hogar no existe."""
    fake_id = uuid4()
    with pytest.raises(ValueError, match=f"El hogar con ID {fake_id} no existe."):
        simplify_household_debts(db_session, fake_id)
