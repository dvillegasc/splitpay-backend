"""
Esquemas Pydantic V2 para la validación de entrada y serialización de salida en SplitPay.

Estructura los modelos Create y Response para las entidades User, Household,
HouseholdMember, Expense y ExpenseSplit, así como los esquemas de autenticación,
simplificación de deudas e importación masiva de gastos.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from models.expense import EstadoAprobacionEnum


# ========================================== #
#               AUTH SCHEMAS                 #
# ========================================== #

class LoginRequest(BaseModel):
    """Esquema para las credenciales de inicio de sesión."""

    email: EmailStr
    password: str


class Token(BaseModel):
    """Esquema de respuesta que contiene el token de acceso JWT."""

    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Esquema para los datos contenidos dentro del payload del token JWT."""

    user_id: Optional[UUID] = None


# ========================================== #
#               USER SCHEMAS                 #
# ========================================== #

class UserBase(BaseModel):
    """Campos comunes de un usuario."""

    nombre_completo: str = Field(..., max_length=150)
    email: EmailStr
    telefono: Optional[str] = Field(None, max_length=20)
    ingreso_mensual_declarado: Optional[Decimal] = Field(None, ge=0)


class UserCreate(UserBase):
    """Esquema para el registro/creación de un usuario."""

    password: str = Field(..., min_length=8)


class UserResponse(UserBase):
    """Esquema de lectura/respuesta para un usuario."""

    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ========================================== #
#            HOUSEHOLD SCHEMAS               #
# ========================================== #

class HouseholdBase(BaseModel):
    """Campos comunes de un hogar."""

    nombre: str = Field(..., max_length=150)
    moneda_base: str = Field(default="COP", min_length=3, max_length=3)


class HouseholdCreate(HouseholdBase):
    """Esquema para la creación de un hogar."""


class HouseholdResponse(HouseholdBase):
    """Esquema de lectura/respuesta para un hogar."""

    id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ========================================== #
#         HOUSEHOLD MEMBER SCHEMAS          #
# ========================================== #

class HouseholdMemberBase(BaseModel):
    """Campos comunes de una membresía de hogar."""

    user_id: UUID
    household_id: UUID
    es_tesorero_dinamico: bool = False


class HouseholdMemberAdd(BaseModel):
    """Esquema de entrada para agregar un miembro a un hogar."""

    user_id: UUID
    es_tesorero_dinamico: bool = False


class HouseholdTreasurerUpdate(BaseModel):
    """Esquema de entrada para actualizar/asignar el tesorero dinámico de un hogar."""

    user_id: UUID
    es_tesorero_dinamico: bool = True


class HouseholdMemberCreate(HouseholdMemberBase):
    """Esquema para agregar un miembro a un hogar."""


class HouseholdMemberResponse(HouseholdMemberBase):
    """Esquema de lectura/respuesta para un miembro de hogar."""

    id: UUID
    fecha_ingreso: datetime
    usuario: Optional[UserResponse] = None

    model_config = ConfigDict(from_attributes=True)


# ========================================== #
#           EXPENSE SPLIT SCHEMAS            #
# ========================================== #

class ExpenseSplitBase(BaseModel):
    """Campos comunes de la cuota/split de un gasto."""

    user_id: UUID
    monto_asignado: Decimal = Field(..., ge=0)
    porcentaje_aplicado: Optional[Decimal] = Field(None, ge=0, le=1)


class ExpenseSplitCreate(ExpenseSplitBase):
    """Esquema para la creación individual o anidada de un split de gasto."""


class ExpenseSplitResponse(ExpenseSplitBase):
    """Esquema de lectura/respuesta para un split de gasto."""

    id: UUID
    expense_id: UUID
    aprobado_por_usuario: bool
    fecha_aprobacion: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ========================================== #
#              EXPENSE SCHEMAS               #
# ========================================== #

class ExpenseBase(BaseModel):
    """Campos comunes de un gasto registrado en un hogar."""

    household_id: UUID
    pagado_por_id: UUID
    descripcion: str = Field(..., max_length=255)
    monto_total: Decimal = Field(..., gt=0)
    moneda: str = Field(default="COP", min_length=3, max_length=3)
    fecha_gasto: date


class ExpenseCreate(ExpenseBase):
    """Esquema para la creación de un gasto, pudiendo incluir splits iniciales."""

    splits: Optional[list[ExpenseSplitCreate]] = None


class ExpenseResponse(ExpenseBase):
    """Esquema de lectura/respuesta para un gasto."""

    id: UUID
    estado_aprobacion: EstadoAprobacionEnum
    created_at: datetime
    splits: list[ExpenseSplitResponse] = []

    model_config = ConfigDict(from_attributes=True)


# ========================================== #
#         DEBT SIMPLIFICATION SCHEMAS        #
# ========================================== #

class DebtTransferResponse(BaseModel):
    """Esquema para una transferencia individual resultante de la simplificación de deuda."""

    deudor_id: UUID
    acreedor_id: UUID
    monto: Decimal = Field(..., gt=0)


class DebtSimplificationResponse(BaseModel):
    """Esquema de respuesta para la simplificación de deudas de un hogar."""

    household_id: UUID
    tesorero_id: Optional[UUID] = None
    saldos_netos: dict[UUID, Decimal]
    transferencias: list[DebtTransferResponse]


# ========================================== #
#               IMPORT SCHEMAS               #
# ========================================== #

class ImportSplitwiseResponse(BaseModel):
    """Esquema de respuesta para la importación masiva de gastos desde Splitwise."""

    household_id: UUID
    gastos_importados: int
    mensajes: list[str] = []
    gastos: list[ExpenseResponse] = []
