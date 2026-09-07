"""Añade el campo monto_total_moneda_base a la tabla expenses

Revision ID: 0001_add_monto_total_moneda_base
Revises: 0001_esquema_inicial
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0001_add_monto_total_moneda_base'
down_revision: Union[str, None] = '0001_esquema_inicial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # El campo monto_total_moneda_base ya está incluido en la migración inicial (0001_esquema_inicial)
    pass


def downgrade() -> None:
    pass
