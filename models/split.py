"""
Modelo de datos para la entidad ExpenseSplit.

Cuota individual de un usuario dentro de un Expense, calculada por el Motor
de División Proporcional. `aprobado_por_usuario` es el mecanismo atómico del
Contrato Social: cada co-deudor aprueba su propia cuota.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

if TYPE_CHECKING:
    from models.expense import Expense
    from models.user import User


class ExpenseSplit(Base):
    """Cuota individual de un usuario dentro de un gasto."""

    __tablename__ = "expense_splits"
    __table_args__ = (
        UniqueConstraint("expense_id", "user_id", name="uq_expense_user_split"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    expense_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("expenses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    # Numeric(12, 2): nunca Float para dinero.
    monto_asignado: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    # Fracción del ingreso relativo usada en el cálculo (0 a 1), guardada para
    # trazabilidad histórica: el ingreso declarado del usuario puede cambiar
    # después de que el gasto ya fue dividido.
    porcentaje_aplicado: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))

    aprobado_por_usuario: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fecha_aprobacion: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # --- Relaciones ---
    expense: Mapped["Expense"] = relationship(back_populates="splits")
    usuario: Mapped["User"] = relationship(back_populates="expense_splits")

    def __repr__(self) -> str:
        return f"<ExpenseSplit expense_id={self.expense_id} user_id={self.user_id}>"
