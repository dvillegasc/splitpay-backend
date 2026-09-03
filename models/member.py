"""
Modelo de datos para la entidad HouseholdMember.

Objeto de asociación enriquecido entre User y Household: modela la relación
muchos-a-muchos y añade el flag `es_tesorero_dinamico`, que identifica al
miembro elegido por votación para recibir las transferencias consolidadas
del algoritmo de Simplificación de Deuda.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, UniqueConstraint, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

if TYPE_CHECKING:
    from models.household import Household
    from models.user import User


class HouseholdMember(Base):
    """Vínculo entre un usuario y un hogar, con metadatos propios de la membresía."""

    __tablename__ = "household_members"
    __table_args__ = (
        # Un usuario no puede tener dos membresías activas en el mismo hogar.
        UniqueConstraint("user_id", "household_id", name="uq_user_household"),
        # Índice único parcial (específico de PostgreSQL): garantiza a nivel de
        # base de datos que exista como máximo un tesorero dinámico por hogar.
        # No obliga a que siempre haya uno (permite 0), solo impide que haya 2+.
        Index(
            "uq_household_tesorero_dinamico",
            "household_id",
            unique=True,
            postgresql_where=text("es_tesorero_dinamico = true"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    household_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )

    es_tesorero_dinamico: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fecha_ingreso: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # --- Relaciones ---
    usuario: Mapped["User"] = relationship(back_populates="household_memberships")
    household: Mapped["Household"] = relationship(back_populates="miembros")

    def __repr__(self) -> str:
        return f"<HouseholdMember user_id={self.user_id} household_id={self.household_id}>"
