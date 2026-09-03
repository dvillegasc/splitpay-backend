"""
Modelo de datos para la entidad User.

`ingreso_mensual_declarado` alimenta el Motor de División Proporcional.
`telefono` existe porque el Enrutamiento de Pagos necesita un identificador
para construir el deep link de la billetera digital (ej. nequi://pay?...).
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, Numeric, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

if TYPE_CHECKING:
    from models.expense import Expense
    from models.member import HouseholdMember
    from models.split import ExpenseSplit


class User(Base):
    """Usuario registrado en la plataforma."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre_completo: Mapped[str] = mapped_column(String(150), nullable=False)
    telefono: Mapped[Optional[str]] = mapped_column(String(20))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    # Nullable a propósito: None = "aún no declaró ingreso", distinto de
    # Decimal("0") = "declaró que gana cero". El motor de división proporcional
    # debe tratar ambos casos de forma distinta. Numeric(12, 2): nunca Float
    # para dinero (evita errores de precisión de coma flotante).
    ingreso_mensual_declarado: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))

    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    # --- Relaciones ---
    household_memberships: Mapped[List["HouseholdMember"]] = relationship(
        back_populates="usuario", cascade="all, delete-orphan"
    )
    expenses_pagados: Mapped[List["Expense"]] = relationship(back_populates="pagador")
    expense_splits: Mapped[List["ExpenseSplit"]] = relationship(back_populates="usuario")

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"
