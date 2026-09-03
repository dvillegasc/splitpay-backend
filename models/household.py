"""
Modelo de datos para la entidad Household (Hogar).

Agrupa a los miembros que comparten gastos y actúa como contenedor de la
Tesorería Dinámica y del Contrato Social.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

if TYPE_CHECKING:
    from models.expense import Expense
    from models.member import HouseholdMember


class Household(Base):
    """Hogar/grupo que agrupa a los miembros que comparten gastos."""

    __tablename__ = "households"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)

    # Moneda de referencia para estandarizar balances cuando el hogar tiene
    # flujos económicos mixtos (Soporte Multidivisa).
    moneda_base: Mapped[str] = mapped_column(String(3), nullable=False, default="COP")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # --- Relaciones ---
    miembros: Mapped[List["HouseholdMember"]] = relationship(
        back_populates="household", cascade="all, delete-orphan"
    )
    gastos: Mapped[List["Expense"]] = relationship(
        back_populates="household", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Household id={self.id} nombre={self.nombre!r}>"
