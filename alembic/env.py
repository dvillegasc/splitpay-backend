"""
Configuración del entorno de ejecución para Alembic.

Lee la URL de la base de datos desde la configuración/entorno de SplitPay
y registra el objeto MetaData de SQLAlchemy con todos los modelos cargados
para soportar la autogeneración de migraciones.
"""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from database import Base, DATABASE_URL
import models  # noqa: F401 - Asegura la carga de todos los modelos en Base.metadata

config = context.config

if config.config_file_name:
    fileConfig(config.config_file_name)

# Prioriza la variable de entorno DATABASE_URL sobre la URL hardcodeada en alembic.ini
db_url = os.getenv("DATABASE_URL", DATABASE_URL)
config.set_main_option("sqlalchemy.url", db_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Ejecuta migraciones en modo 'offline'."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Ejecuta migraciones en modo 'online'."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
