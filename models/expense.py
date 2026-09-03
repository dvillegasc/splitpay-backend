"""
Modelo de datos para la entidad Expense (Gasto).

Cada gasto nace en estado PENDIENTE (Contrato Social) y requiere que los
co-deudores lo validen a través de su ExpenseSplit antes de impactar el
balance general del hogar.
"""

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

if TYPE_CHECKING:
    from models.household import Household
    from models.split import ExpenseSplit
    from models.user import User


class EstadoAprobacionEnum(str, enum.Enum):
    """Estados posibles del Contrato Social de un gasto."""

    PENDIENTE = "pendiente"
    APROBADO = "aprobado"
    RECHAZADO = "rechazado"


class Expense(Base):
    """Gasto registrado dentro de un hogar."""

    __tablename__ = "expenses"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Usuario que efectivamente desembolsó el dinero (necesario para que
    # debt_simplifier.py pueda construir la matriz de deudas internas).
    pagado_por_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    descripcion: Mapped[str] = mapped_column(String(255), nullable=False)
    monto_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    moneda: Mapped[str] = mapped_column(String(3), nullable=False, default="COP")
    fecha_gasto: Mapped[date] = mapped_column(Date, nullable=False, server_default=func.current_date())

    # values_callable asegura que en la BD se guarden los valores en minúscula
    # ("pendiente") y no el nombre del miembro del enum de Python ("PENDIENTE"),
    # que es el comportamiento por defecto de SQLAlchemy y una fuente común de
    # confusión al inspeccionar la BD directamente.
    estado_aprobacion: Mapped[EstadoAprobacionEnum] = mapped_column(
        Enum(
            EstadoAprobacionEnum,
            name="estado_aprobacion_enum",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=EstadoAprobacionEnum.PENDIENTE,
        index=True,  # el feed de aprobación filtra constantemente por este campo
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # --- Relaciones ---
    household: Mapped["Household"] = relationship(back_populates="gastos")
    pagador: Mapped["User"] = relationship(back_populates="expenses_pagados")
    splits: Mapped[List["ExpenseSplit"]] = relationship(
        back_populates="expense", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Expense id={self.id} estado={self.estado_aprobacion.value}>"
