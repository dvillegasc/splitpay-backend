"""
Punto de entrada principal de la aplicación FastAPI para SplitPay.

Inicializa la API REST y expone el endpoint de estado general.
"""

from fastapi import FastAPI

from routers.auth import router as auth_router
from routers.expenses import router as expenses_router
from routers.households import router as households_router
from routers.import_splitwise import router as import_router

app = FastAPI(
    title="SplitPay API",
    description="Backend API para la gestión y división de gastos compartidos en el hogar.",
    version="0.1.0",
)

app.include_router(auth_router)
app.include_router(households_router)
app.include_router(expenses_router)
app.include_router(import_router)


@app.get("/")
def read_root() -> dict[str, str]:
    """Endpoint de prueba para verificar que la API de SplitPay está funcionando."""
    return {"status": "SplitPay API running"}
