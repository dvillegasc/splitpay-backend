"""
Punto de entrada principal de la aplicación FastAPI para SplitPay.

Inicializa la API REST, configura CORSMiddleware para habilitar la integración
con el frontend (Next.js) y expone el endpoint de estado general.
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.auth import router as auth_router
from routers.expenses import router as expenses_router
from routers.households import router as households_router
from routers.import_splitwise import router as import_router

# Lectura y parseo de los orígenes permitidos desde la variable de entorno CORS_ORIGINS
cors_origins_raw = os.getenv("CORS_ORIGINS", "http://localhost:3000")
allow_origins = [origin.strip() for origin in cors_origins_raw.split(",") if origin.strip()]

app = FastAPI(
    title="SplitPay API",
    description="Backend API para la gestión y división de gastos compartidos en el hogar.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(households_router)
app.include_router(expenses_router)
app.include_router(import_router)


@app.get("/")
def read_root() -> dict[str, str]:
    """Endpoint de prueba para verificar que la API de SplitPay está funcionando."""
    return {"status": "SplitPay API running"}
