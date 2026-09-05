"""
Funciones utilitarias de seguridad para SplitPay.

Incluye el hashing y verificación de contraseñas mediante bcrypt
y la generación y decodificación de tokens de acceso JWT.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt
from passlib.context import CryptContext

# Configuración de seguridad desde variables de entorno
SECRET_KEY = os.environ["SECRET_KEY"]
ALGORITHM = os.environ.get("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Genera el hash de una contraseña en texto plano utilizando bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica si una contraseña plana coincide con su hash almacenado."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    data: dict[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """
    Genera un token de acceso JWT firmado con expiración.

    :param data: Diccionario con los datos (claims) a incluir en el payload.
    :param expires_delta: Duración opcional del token. Si no se provee, usa el tiempo por defecto.
    :return: Token JWT firmado como string.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decodifica y verifica la firma y expiración de un token JWT.

    :param token: Token JWT a verificar.
    :return: Payload decodificado como diccionario.
    :raises jwt.PyJWTError: Si el token es inválido, expiró o la firma no coincide.
    """
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
