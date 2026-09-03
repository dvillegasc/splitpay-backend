"""
Endpoints de autenticación para SplitPay.

Provee la gestión de registro, inicio de sesión y consulta de perfil de usuario.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from models.user import User
from schemas import LoginRequest, Token, UserCreate, UserResponse
from utils.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["Autenticación"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un nuevo usuario",
)
def register_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
) -> User:
    """
    Registra un nuevo usuario en la plataforma.

    Guarda la información personal, la contraseña hasheada y el
    `ingreso_mensual_declarado` utilizado por el Motor de División Proporcional.
    """
    user_exists = db.query(User).filter(User.email == user_in.email).first()
    if user_exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El correo electrónico ya está registrado.",
        )

    hashed_password = hash_password(user_in.password)

    new_user = User(
        nombre_completo=user_in.nombre_completo,
        email=user_in.email,
        telefono=user_in.telefono,
        ingreso_mensual_declarado=user_in.ingreso_mensual_declarado,
        hashed_password=hashed_password,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


@router.post(
    "/login",
    response_model=Token,
    status_code=status.HTTP_200_OK,
    summary="Autenticar usuario y retornar token JWT",
)
def login(
    credentials: LoginRequest,
    db: Session = Depends(get_db),
) -> Token:
    """
    Autentica a un usuario mediante correo electrónico y contraseña.

    Si las credenciales son válidas y el usuario está activo, genera
    y retorna un token de acceso JWT firmado.
    """
    user = db.query(User).filter(User.email == credentials.email).first()
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo electrónico o contraseña incorrectos.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario se encuentra inactivo.",
        )

    access_token = create_access_token(data={"sub": str(user.id)})

    return Token(access_token=access_token, token_type="bearer")


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener perfil del usuario autenticado",
)
def get_me(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Retorna la información del usuario actualmente autenticado en la sesión.
    """
    return current_user
