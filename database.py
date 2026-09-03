"""
Configuración de la conexión a PostgreSQL para SplitPay.

Expone `engine`, la fábrica de sesiones `SessionLocal`, la clase base
declarativa `Base` (de la que heredan todos los modelos en `models/`) y la
dependencia `get_db` para inyectar sesiones en los endpoints de FastAPI.
"""

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# La URL siempre se toma de una variable de entorno; nunca se hardcodean
# credenciales en el código fuente. Formato esperado:
# postgresql+psycopg2://usuario:password@host:5432/splitpay_db
DATABASE_URL = os.environ["DATABASE_URL"]

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # evita usar conexiones muertas tras inactividad
    pool_size=10,
    max_overflow=20,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Clase base declarativa compartida por todos los modelos ORM."""


def get_db() -> Generator[Session, None, None]:
    """Dependencia de FastAPI: entrega una sesión por request y la cierra al final."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
