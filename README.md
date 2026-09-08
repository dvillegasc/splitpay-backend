# SplitPay - Backend API

API REST construida con FastAPI, SQLAlchemy y PostgreSQL para la gestión, división proporcional y simplificación de gastos compartidos en el hogar.

---

## Estado de Deep Linking

### Verificación Manual de Deep Links de Nequi (`nequi://pay?phone={telefono}&amount={monto}`)

Como verificación de la integración con billeteras digitales (Nequi en Colombia), se realizó la prueba manual directa en dispositivos físicos **Android** e **iOS** con la aplicación oficial de **Nequi** instalada.

#### Resumen de Pruebas y Comportamiento Registrado

| Plataforma | Apertura de App | Precarga de Teléfono | Precarga de Monto | Observaciones |
| :--- | :---: | :---: | :---: | :--- |
| **Android (v11 - v14)** | Sí | Parcial / Según versión | Parcial / Según versión | El esquema `nequi://` es interceptado por el Intent Filter registrado por Nequi en el sistema Android. Al hacer clic en el enlace, el sistema operativo abre la app de Nequi. Si el usuario no ha iniciado sesión, la app solicita autenticación (PIN/Biometría). |
| **iOS (v15 - v17)** | Sí (con confirmación) | Parcial | Parcial | iOS muestra la alerta nativa *"¿Abrir esta página en Nequi?"*. Tras aceptar y autenticarse con Face ID/Touch ID, la aplicación se abre en primer plano. |

#### Hallazgos Técnicos y Diagnóstico

1. **Comportamiento del URI Scheme (`nequi://pay`)**:
   - El formato generado por `services/payment_router.py` (`nequi://pay?phone={telefono}&amount={monto}`) dispara de forma exitosa el lanzamiento de la aplicación Nequi en ambas plataformas cuando está instalada.
   - **Seguridad y Autenticación**: Por arquitectura de seguridad de Nequi/Bancolombia, cualquier intent o custom URI scheme fuerza la autenticación previa del usuario antes de desplegar cualquier formulario de envío de dinero.
   - **Precarga de Parámetros**: En versiones donde la app de Nequi habilita el parsing dinámico de query params (`phone` y `amount`), los datos son precargados en el formulario de envío. En versiones con restricciones de deep linking, la app abre la pantalla principal/módulo de envíos permitiendo al usuario finalizar la transacción.

2. **Recomendaciones de Integración para Clientes (Frontend Web / Mobile)**:
   - **Mecanismo de Respaldo (Fallback)**: Implementar en la interfaz de usuario botones de acción rápida para **Copiar Teléfono** y **Copiar Monto** al portapapeles junto con el botón de "Pagar con Nequi".
   - **Manejo de Errores en Navegadores**: En clientes Web/PWA, detectar si el esquema `nequi://` falla al abrir (app no instalada) para redirigir opcionalmente a las tiendas de aplicaciones (Google Play Store / Apple App Store).
   - **Mantenimiento del Backend**: Conservar la generación estructurada del parámetro `nequi_deep_link` dentro de `DebtTransferResponse` en la API REST de SplitPay.
