"""
Punto de entrada principal de la aplicación FastAPI para SplitPay.

Inicializa la API REST y expone el endpoint de estado general.
"""

from fastapi import FastAPI

app = FastAPI(
    title="SplitPay API",
    description="Backend API para la gestión y división de gastos compartidos en el hogar.",
    version="0.1.0",
)


@app.get("/")
def read_root() -> dict[str, str]:
    """Endpoint de prueba para verificar que la API de SplitPay está funcionando."""
    return {"status": "SplitPay API running"}
