"""
Pruebas unitarias y de integración para la máquina de estados de gastos en SplitPay.
"""

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base, get_db
from dependencies import get_current_user
from main import app
from models.expense import EstadoAprobacionEnum, Expense
from models.household import Household
from models.member import HouseholdMember
from models.split import ExpenseSplit
from models.user import User


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_approve_and_reject_expense_state_machine_validation(db_session):
    user_a = User(
        id=uuid4(),
        nombre_completo="User A",
        email="a@example.com",
        hashed_password="pwd",
    )
    user_b = User(
        id=uuid4(),
        nombre_completo="User B",
        email="b@example.com",
        hashed_password="pwd",
    )
    db_session.add_all([user_a, user_b])

    household = Household(id=uuid4(), nombre="Hogar Test", moneda_base="COP")
    db_session.add(household)
    db_session.flush()

    m1 = HouseholdMember(household_id=household.id, user_id=user_a.id)
    m2 = HouseholdMember(household_id=household.id, user_id=user_b.id)
    db_session.add_all([m1, m2])

    expense = Expense(
        id=uuid4(),
        household_id=household.id,
        pagado_por_id=user_a.id,
        descripcion="Test Gasto",
        monto_total=Decimal("100.00"),
        monto_total_moneda_base=Decimal("100.00"),
        moneda="COP",
        estado_aprobacion=EstadoAprobacionEnum.APROBADO,
    )
    db_session.add(expense)
    db_session.flush()

    s1 = ExpenseSplit(
        expense_id=expense.id,
        user_id=user_a.id,
        monto_asignado=Decimal("50.00"),
        aprobado_por_usuario=True,
    )
    s2 = ExpenseSplit(
        expense_id=expense.id,
        user_id=user_b.id,
        monto_asignado=Decimal("50.00"),
        aprobado_por_usuario=True,
    )
    db_session.add_all([s1, s2])
    db_session.commit()

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def override_get_current_user():
        return user_b

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    client = TestClient(app)

    res_approve = client.put(f"/api/expenses/{expense.id}/approve")
    assert res_approve.status_code == 400
    assert "no puede ser modificado" in res_approve.json()["detail"]

    res_reject = client.put(f"/api/expenses/{expense.id}/reject")
    assert res_reject.status_code == 400
    assert "no puede ser modificado" in res_reject.json()["detail"]

    expense.estado_aprobacion = EstadoAprobacionEnum.RECHAZADO
    db_session.commit()

    res_approve2 = client.put(f"/api/expenses/{expense.id}/approve")
    assert res_approve2.status_code == 400

    res_reject2 = client.put(f"/api/expenses/{expense.id}/reject")
    assert res_reject2.status_code == 400

    app.dependency_overrides.clear()
