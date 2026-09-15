"""
Pruebas unitarias para las validaciones de máquina de estados en aprobación y rechazo de gastos.
"""

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException, status
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from models.expense import EstadoAprobacionEnum, Expense
from models.household import Household
from models.member import HouseholdMember
from models.split import ExpenseSplit
from models.user import User
from routers.expenses import approve_expense_split, reject_expense


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


def test_approve_expense_split_when_already_approved_or_rejected(db_session):
    user_a = User(id=uuid4(), nombre_completo="User A", email="a@example.com", hashed_password="pwd")
    db_session.add(user_a)

    household = Household(id=uuid4(), nombre="Hogar Test", moneda_base="COP")
    db_session.add(household)
    db_session.flush()

    m1 = HouseholdMember(household_id=household.id, user_id=user_a.id)
    db_session.add(m1)

    expense_approved = Expense(
        id=uuid4(),
        household_id=household.id,
        pagado_por_id=user_a.id,
        descripcion="Test Aprobado",
        monto_total=Decimal("100.00"),
        monto_total_moneda_base=Decimal("100.00"),
        moneda="COP",
        estado_aprobacion=EstadoAprobacionEnum.APROBADO,
    )
    db_session.add(expense_approved)
    db_session.flush()

    s1 = ExpenseSplit(
        expense_id=expense_approved.id,
        user_id=user_a.id,
        monto_asignado=Decimal("100.00"),
        aprobado_por_usuario=True,
    )
    db_session.add(s1)
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        approve_expense_split(expense_approved.id, current_user=user_a, db=db_session)
    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    with pytest.raises(HTTPException) as exc_info:
        reject_expense(expense_approved.id, current_user=user_a, db=db_session)
    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST


def test_reject_expense_when_already_rejected(db_session):
    user_a = User(id=uuid4(), nombre_completo="User A", email="a@example.com", hashed_password="pwd")
    db_session.add(user_a)

    household = Household(id=uuid4(), nombre="Hogar Test", moneda_base="COP")
    db_session.add(household)
    db_session.flush()

    m1 = HouseholdMember(household_id=household.id, user_id=user_a.id)
    db_session.add(m1)

    expense_rejected = Expense(
        id=uuid4(),
        household_id=household.id,
        pagado_por_id=user_a.id,
        descripcion="Test Rechazado",
        monto_total=Decimal("100.00"),
        monto_total_moneda_base=Decimal("100.00"),
        moneda="COP",
        estado_aprobacion=EstadoAprobacionEnum.RECHAZADO,
    )
    db_session.add(expense_rejected)
    db_session.flush()

    s1 = ExpenseSplit(
        expense_id=expense_rejected.id,
        user_id=user_a.id,
        monto_asignado=Decimal("100.00"),
        aprobado_por_usuario=False,
    )
    db_session.add(s1)
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        approve_expense_split(expense_rejected.id, current_user=user_a, db=db_session)
    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    with pytest.raises(HTTPException) as exc_info:
        reject_expense(expense_rejected.id, current_user=user_a, db=db_session)
    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
