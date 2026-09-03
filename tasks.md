# Backlog de Desarrollo Autónomo - SplitPay (PMV)

## Fase 1: Configuración de Infraestructura y Entorno
- [x] Backend: Inicializar proyecto de Python con `FastAPI`. Configurar `requirements.txt` incluyendo `fastapi`, `uvicorn`, `sqlalchemy`, `psycopg2-binary`, `alembic`, `python-dotenv`.
- [ ] Backend: Crear archivo `main.py` con un endpoint de prueba `GET /` que retorne `{"status": "SplitPay API running"}`.
- [x] Backend: Configurar la conexión a la base de datos PostgreSQL en `database.py` utilizando SQLAlchemy y variables de entorno (`DATABASE_URL`).
- [ ] Backend: Inicializar `alembic` para el control de migraciones de la base de datos.

## Fase 2: Modelado de Base de Datos (PostgreSQL)
- [x] Backend: Crear modelo `User` en `models/user.py` (id, nombre, email, password_hash, ingreso_mensual_declarado, fecha_creacion).
- [x] Backend: Crear modelo `Household` en `models/household.py` (id, nombre, moneda_base, fecha_creacion).
- [x] Backend: Crear modelo `HouseholdMember` en `models/member.py` (id, user_id, household_id, es_tesorero_dinamico, fecha_ingreso). Configurar relaciones.
- [x] Backend: Crear modelo `Expense` en `models/expense.py` (id, household_id, creador_id, monto_total, descripcion, estado_aprobacion, fecha).
- [x] Backend: Crear modelo `ExpenseSplit` en `models/split.py` (id, expense_id, user_id, monto_adeudado, aprobado_por_usuario).
- [ ] Backend: Generar y ejecutar la primera migración de Alembic para crear todas las tablas relacionales en PostgreSQL.

## Fase 3: Autenticación y Gestión de Usuarios
- [ ] Backend: Implementar funciones utilitarias en `utils/security.py` para hashear contraseñas (bcrypt) y generar tokens JWT.
- [ ] Backend: Crear endpoint `POST /api/auth/register` para registrar usuarios guardando su `ingreso_mensual_declarado`.
- [ ] Backend: Crear endpoint `POST /api/auth/login` para autenticar usuarios y retornar un token JWT.
- [ ] Backend: Configurar middleware/dependencia `get_current_user` en FastAPI para proteger rutas privadas.

## Fase 4: Lógica de Hogares y Tesorería Dinámica
- [ ] Backend: Crear endpoint `POST /api/households` para registrar un nuevo hogar y asignar al creador como miembro fundador.
- [ ] Backend: Crear endpoint `POST /api/households/{id}/members` para añadir nuevos roomies al hogar.
- [ ] Backend: Crear endpoint `PUT /api/households/{id}/treasurer` para actualizar el flag `es_tesorero_dinamico` de un miembro específico (votación de tesorero).

## Fase 5: Motor Matemático y Gestión de Gastos (Core)
- [ ] Backend: Crear servicio `services/math_engine.py` con una función `calculate_proportional_split(total_amount, members_incomes)` que divida un monto basándose en los ingresos declarados.
- [ ] Backend: Crear endpoint `POST /api/expenses` que reciba un gasto, calcule las cuotas usando el motor matemático y guarde los registros en `Expense` y `ExpenseSplit` con estado 'pendiente'.
- [ ] Backend: Crear endpoint `PUT /api/expenses/{id}/approve` para que un usuario marque su cuota como aprobada (Feed de Aprobación).
- [ ] Backend: Crear algoritmo de simplificación de deudas en `services/debt_simplifier.py`. Debe cruzar todos los saldos y retornar transferencias únicas hacia el tesorero actual.
- [ ] Backend: Crear endpoint `GET /api/households/{id}/balances` que retorne el resumen de deudas simplificadas usando el algoritmo anterior.

## Fase 6: Importación de Datos (Data Portability)
- [ ] Backend: Crear endpoint `POST /api/import/splitwise` que reciba un archivo CSV.
- [ ] Backend: Implementar lógica en el endpoint de importación para parsear las columnas de Splitwise (Date, Description, Cost, Currency) y mapearlas a la estructura de la base de datos de SplitPay.
