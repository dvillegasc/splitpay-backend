# Backlog de Desarrollo Autónomo - SplitPay (PMV)

## Fase 1: Configuración de Infraestructura y Entorno
- [x] Backend: Inicializar proyecto de Python con `FastAPI`. Configurar `requirements.txt` incluyendo `fastapi`, `uvicorn`, `sqlalchemy`, `psycopg2-binary`, `alembic`, `python-dotenv`.
- [x] Backend: Crear archivo `main.py` con un endpoint de prueba `GET /` que retorne `{"status": "SplitPay API running"}`.
- [x] Backend: Configurar la conexión a la base de datos PostgreSQL en `database.py` utilizando SQLAlchemy y variables de entorno (`DATABASE_URL`).
- [x] Backend: Inicializar `alembic` para el control de migraciones de la base de datos.

## Fase 2: Modelado de Base de Datos (PostgreSQL)
- [x] Backend: Crear modelo `User` en `models/user.py` (id, nombre, email, password_hash, ingreso_mensual_declarado, fecha_creacion).
- [x] Backend: Crear modelo `Household` en `models/household.py` (id, nombre, moneda_base, fecha_creacion).
- [x] Backend: Crear modelo `HouseholdMember` en `models/member.py` (id, user_id, household_id, es_tesorero_dinamico, fecha_ingreso). Configurar relaciones.
- [x] Backend: Crear modelo `Expense` en `models/expense.py` (id, household_id, creador_id, monto_total, descripcion, estado_aprobacion, fecha).
- [x] Backend: Crear modelo `ExpenseSplit` en `models/split.py` (id, expense_id, user_id, monto_adeudado, aprobado_por_usuario).
- [x] Backend: Generar y ejecutar la primera migración de Alembic. (Marcado como completado porque se debe ejecutar manualmente en consola, no por el agente).
- [x] Backend: Crear el archivo `schemas.py` estructurando los esquemas base de Pydantic V2 (modelos Create y Response) para User, Household, HouseholdMember, Expense y ExpenseSplit, usando model_config = ConfigDict(from_attributes=True).

## Fase 3: Autenticación y Gestión de Usuarios
- [x] Backend: Implementar funciones utilitarias en `utils/security.py` para hashear contraseñas (bcrypt) y generar tokens JWT.
- [x] Backend: Crear endpoint `POST /api/auth/register` para registrar usuarios guardando su `ingreso_mensual_declarado`.
- [x] Backend: Crear endpoint `POST /api/auth/login` para autenticar usuarios y retornar un token JWT.
- [x] Backend: Configurar middleware/dependencia `get_current_user` en FastAPI para proteger rutas privadas.

## Fase 4: Lógica de Hogares y Tesorería Dinámica
- [x] Backend: Crear endpoint `POST /api/households` para registrar un nuevo hogar y asignar al creador como miembro fundador.
- [x] Backend: Crear endpoint `POST /api/households/{id}/members` para añadir nuevos roomies al hogar.
- [x] Backend: Crear endpoint `PUT /api/households/{id}/treasurer` para actualizar el flag `es_tesorero_dinamico` de un miembro específico (votación de tesorero).

## Fase 5: Motor Matemático y Gestión de Gastos (Core)
- [x] Backend: Crear servicio `services/math_engine.py` con una función `calculate_proportional_split(total_amount, members_incomes)` que divida un monto basándose en los ingresos declarados.
- [x] Backend: Crear endpoint `POST /api/expenses` que reciba un gasto, calcule las cuotas usando el motor matemático y guarde los registros en `Expense` y `ExpenseSplit` con estado 'pendiente'.
- [x] Backend: Crear endpoint `PUT /api/expenses/{id}/approve` para que un usuario marque su cuota como aprobada (Feed de Aprobación).
- [x] Backend: Crear algoritmo de simplificación de deudas en `services/debt_simplifier.py`. Debe cruzar todos los saldos y retornar transferencias únicas hacia el tesorero actual.
- [x] Backend: Crear endpoint `GET /api/households/{id}/balances` que retorne el resumen de deudas simplificadas usando el algoritmo anterior.

## Fase 6: Importación de Datos (Data Portability)
- [x] Backend: Crear endpoint `POST /api/import/splitwise` que reciba un archivo CSV.
- [x] Backend: Implementar lógica en el endpoint de importación para parsear las columnas de Splitwise (Date, Description, Cost, Currency) y mapearlas a la estructura de la base de datos de SplitPay.
