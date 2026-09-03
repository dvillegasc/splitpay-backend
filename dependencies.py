"""
Dependencias reutilizables de FastAPI para SplitPay.

Provee la inyección de dependencias para autenticación y autorización
de usuarios en rutas protegidas.
"""

from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from utils.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Dependencia de FastAPI para obtener y validar el usuario autenticado a partir del JWT.

    :param token: Token de acceso extraído del encabezado Authorization (Bearer).
    :param db: Sesión de base de datos inyectada.
    :return: Instancia del modelo User correspondiente al token válido.
    :raises HTTPException 401: Si el token es inválido, expiró o el usuario no existe.
    :raises HTTPException 400: Si el usuario está inactivo.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales de acceso.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
        user_id = UUID(user_id_str)
    except (jwt.PyJWTError, ValueError):
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuario inactivo.",
        )

    return user
