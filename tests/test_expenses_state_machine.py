"""
Pruebas unitarias para la validación de la máquina de estados en los endpoints de aprobación y rechazo de gastos.
"""

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base, get_db
from main import app
from models.expense import EstadoAprobacionEnum, Expense
from models.household import Household
from models.member import HouseholdMember
from models.split import ExpenseSplit
from models.user import User
from utils.security import create_access_token


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


@pytest.fixture
def client(db_session):
    def _get_db_override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _get_db_override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_approve_already_approved_expense_returns_400(client, db_session):
    user = User(id=uuid4(), nombre_completo="Test User", email="test1@example.com", hashed_password="pwd")
    db_session.add(user)
    db_session.flush()

    household = Household(id=uuid4(), nombre="Hogar Test", moneda_base="COP")
    db_session.add(household)
    db_session.flush()

    member = HouseholdMember(household_id=household.id, user_id=user.id)
    db_session.add(member)

    expense = Expense(
        id=uuid4(),
        household_id=household.id,
        pagado_por_id=user.id,
        descripcion="Gasto Ya Aprobado",
        monto_total=Decimal("100.00"),
        monto_total_moneda_base=Decimal("100.00"),
        moneda="COP",
        estado_aprobacion=EstadoAprobacionEnum.APROBADO,
    )
    db_session.add(expense)
    db_session.flush()

    split = ExpenseSplit(expense_id=expense.id, user_id=user.id, monto_asignado=Decimal("100.00"), aprobado_por_usuario=True)
    db_session.add(split)
    db_session.commit()

    token = create_access_token({"sub": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}

    response = client.put(f"/api/expenses/{expense.id}/approve", headers=headers)
    assert response.status_code == 400
    assert "APROBADO" in response.json()["detail"] or "RECHAZADO" in response.json()["detail"]


def test_reject_already_approved_expense_returns_400(client, db_session):
    user = User(id=uuid4(), nombre_completo="Test User", email="test2@example.com", hashed_password="pwd")
    db_session.add(user)
    db_session.flush()

    household = Household(id=uuid4(), nombre="Hogar Test", moneda_base="COP")
    db_session.add(household)
    db_session.flush()

    member = HouseholdMember(household_id=household.id, user_id=user.id)
    db_session.add(member)

    expense = Expense(
        id=uuid4(),
        household_id=household.id,
        pagado_por_id=user.id,
        descripcion="Gasto Ya Aprobado",
        monto_total=Decimal("100.00"),
        monto_total_moneda_base=Decimal("100.00"),
        moneda="COP",
        estado_aprobacion=EstadoAprobacionEnum.APROBADO,
    )
    db_session.add(expense)
    db_session.flush()

    split = ExpenseSplit(expense_id=expense.id, user_id=user.id, monto_asignado=Decimal("100.00"), aprobado_por_usuario=True)
    db_session.add(split)
    db_session.commit()

    token = create_access_token({"sub": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}

    response = client.put(f"/api/expenses/{expense.id}/reject", headers=headers)
    assert response.status_code == 400


def test_approve_already_rejected_expense_returns_400(client, db_session):
    user = User(id=uuid4(), nombre_completo="Test User", email="test3@example.com", hashed_password="pwd")
    db_session.add(user)
    db_session.flush()

    household = Household(id=uuid4(), nombre="Hogar Test", moneda_base="COP")
    db_session.add(household)
    db_session.flush()

    member = HouseholdMember(household_id=household.id, user_id=user.id)
    db_session.add(member)

    expense = Expense(
        id=uuid4(),
        household_id=household.id,
        pagado_por_id=user.id,
        descripcion="Gasto Ya Rechazado",
        monto_total=Decimal("100.00"),
        monto_total_moneda_base=Decimal("100.00"),
        moneda="COP",
        estado_aprobacion=EstadoAprobacionEnum.RECHAZADO,
    )
    db_session.add(expense)
    db_session.flush()

    split = ExpenseSplit(expense_id=expense.id, user_id=user.id, monto_asignado=Decimal("100.00"), aprobado_por_usuario=False)
    db_session.add(split)
    db_session.commit()

    token = create_access_token({"sub": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}

    response = client.put(f"/api/expenses/{expense.id}/approve", headers=headers)
    assert response.status_code == 400


def test_reject_already_rejected_expense_returns_400(client, db_session):
    user = User(id=uuid4(), nombre_completo="Test User", email="test4@example.com", hashed_password="pwd")
    db_session.add(user)
    db_session.flush()

    household = Household(id=uuid4(), nombre="Hogar Test", moneda_base="COP")
    db_session.add(household)
    db_session.flush()

    member = HouseholdMember(household_id=household.id, user_id=user.id)
    db_session.add(member)

    expense = Expense(
        id=uuid4(),
        household_id=household.id,
        pagado_por_id=user.id,
        descripcion="Gasto Ya Rechazado",
        monto_total=Decimal("100.00"),
        monto_total_moneda_base=Decimal("100.00"),
        moneda="COP",
        estado_aprobacion=EstadoAprobacionEnum.RECHAZADO,
    )
    db_session.add(expense)
    db_session.flush()

    split = ExpenseSplit(expense_id=expense.id, user_id=user.id, monto_asignado=Decimal("100.00"), aprobado_por_usuario=False)
    db_session.add(split)
    db_session.commit()

    token = create_access_token({"sub": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}

    response = client.put(f"/api/expenses/{expense.id}/reject", headers=headers)
    assert response.status_code == 400
