"""
Pruebas unitarias para la máquina de estados en la aprobación y rechazo de gastos.
"""

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from models.expense import EstadoAprobacionEnum, Expense
from models.household import Household
from models.split import ExpenseSplit
from models.user import User
from routers.expenses import approve_expense_split, reject_expense


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


def test_approve_already_approved_expense_returns_400(db_session):
    """Verifica que intentar aprobar un gasto previamente APROBADO devuelva HTTP 400."""
    user = User(id=uuid4(), nombre_completo="Test User", email="test@example.com", hashed_password="pwd")
    db_session.add(user)
    
    household = Household(id=uuid4(), nombre="Test Household", moneda_base="COP")
    db_session.add(household)
    db_session.flush()

    expense = Expense(
        id=uuid4(),
        household_id=household.id,
        pagado_por_id=user.id,
        descripcion="Test Expense",
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

    with pytest.raises(HTTPException) as exc_info:
        approve_expense_split(expense.id, current_user=user, db=db_session)
    
    assert exc_info.value.status_code == 400


def test_reject_already_approved_expense_returns_400(db_session):
    """Verifica que intentar rechazar un gasto previamente APROBADO devuelva HTTP 400."""
    user = User(id=uuid4(), nombre_completo="Test User", email="test@example.com", hashed_password="pwd")
    db_session.add(user)
    
    household = Household(id=uuid4(), nombre="Test Household", moneda_base="COP")
    db_session.add(household)
    db_session.flush()

    expense = Expense(
        id=uuid4(),
        household_id=household.id,
        pagado_por_id=user.id,
        descripcion="Test Expense",
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

    with pytest.raises(HTTPException) as exc_info:
        reject_expense(expense.id, current_user=user, db=db_session)
    
    assert exc_info.value.status_code == 400


def test_approve_already_rejected_expense_returns_400(db_session):
    """Verifica que intentar aprobar un gasto previamente RECHAZADO devuelva HTTP 400."""
    user = User(id=uuid4(), nombre_completo="Test User", email="test@example.com", hashed_password="pwd")
    db_session.add(user)
    
    household = Household(id=uuid4(), nombre="Test Household", moneda_base="COP")
    db_session.add(household)
    db_session.flush()

    expense = Expense(
        id=uuid4(),
        household_id=household.id,
        pagado_por_id=user.id,
        descripcion="Test Expense",
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

    with pytest.raises(HTTPException) as exc_info:
        approve_expense_split(expense.id, current_user=user, db=db_session)
    
    assert exc_info.value.status_code == 400


def test_reject_already_rejected_expense_returns_400(db_session):
    """Verifica que intentar rechazar un gasto previamente RECHAZADO devuelva HTTP 400."""
    user = User(id=uuid4(), nombre_completo="Test User", email="test@example.com", hashed_password="pwd")
    db_session.add(user)
    
    household = Household(id=uuid4(), nombre="Test Household", moneda_base="COP")
    db_session.add(household)
    db_session.flush()

    expense = Expense(
        id=uuid4(),
        household_id=household.id,
        pagado_por_id=user.id,
        descripcion="Test Expense",
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

    with pytest.raises(HTTPException) as exc_info:
        reject_expense(expense.id, current_user=user, db=db_session)
    
    assert exc_info.value.status_code == 400
