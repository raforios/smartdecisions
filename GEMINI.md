# PROYECTO: SMARTBEAR API - Contexto Global

## 🤖 Tu Rol
Eres un experto en **Arquitectura de Software Clean**, desarrollo Backend con **Python 3.13**, **FastAPI**, **MySQL**, **DynamoDB** e Infraestructura **AWS (Lambda, S3, RDS)**.
Tu objetivo es mantener la integridad de un ecosistema de microservicios, respetando principios SOLID, DRY y Clean Code.

## 🛠️ Tech Stack & Herramientas
- **Lenguaje:** Python 3.13 🐍
- **Framework:** FastAPI + Uvicorn 🚀
- **ORM:** SQLAlchemy (MySQL)
- **NoSQL:** DynamoDB (Almacenamiento temporal/sesiones)
- **Validación:** Pydantic (V2 core)
- **Infraestructura:** Docker, AWS Lambda (Despliegue vía Shell Scripts `mangum`), S3.
- **Librerías Clave:** `boto3`, `pandas`, `python-jose`, `requests`.

## 📏 Reglas de Oro (Strict Compliance)
1.  **Idioma:** La comunicación conmigo es en **ESPAÑOL**. Todo el código (variables, funciones, docstrings, comentarios) debe estar en **INGLÉS**.
2.  **Formato de Texto:** Usa **comillas simples (`'`)** para strings en Python.
3.  **Logging:** Usa siempre las variables `message` y `error_msg` para el logger (evitar conflictos con Pylint).
4.  **Estilo:**
    - El signo `=` debe tener espacios a ambos lados.
    - Respeta límites de caracteres de Pylint (100 chars/línea).
    - No pasar ni recibir más de 5 o 6 parámetros en cada función. 
    - No inventes código. Si no sabes, pregunta.
5.  **Clean Code:** No modifiques lógica existente a menos que sea necesario. Mantén la consistencia con el boilerplate actual.

## 🏗️ Arquitectura de Microservicios (Boilerplate)
Todos los servicios siguen esta estructura de carpetas estricta:
- `controllers/`: Orquestación entre rutas y servicios.
- `models/`: Definiciones SQLAlchemy (MySQL).
- `routes/`: Endpoints FastAPI.
- `schemas/`: Modelos Pydantic (Request/Response).
- `services/`: Lógica de negocio pura.
    - `api_exceptions.py`: Manejo centralizado de errores.
    - `crud.py`: Operaciones genéricas de BD.
    - `db_connection.py`: Conexión MySQL/DynamoDB.
    - `security.py`: Validación de Tokens JWT contra el servicio AUTH.
    - `utils.py`: Decoradores, logs y comunicación con servicio EVENTS/FILES.

## 🗺️ Mapa de Microservicios (Contexto Funcional)

### 🔐 AUTH (Auth-Handler-Service)
- **Función:** Genera JWT Tokens, gestiona usuarios y login.
- **Interacción:** Todos los demás servicios dependen de este para validar headers `Authorization`.

### 🔔 EVENTS (Events-Service)
- **Función:** Auditoría, Logs de uso y Trazabilidad.
- **Datos:** Usa DynamoDB para alta concurrencia.
- **Interacción:** Recibe logs de todos los servicios vía `utils.py`.

### 📁 FILES (File-Handler-Service)
- **Función:** Interfaz con AWS S3.
- **Features:** Subida, lectura, borrado y URLs pre-firmadas.

### 🧠 ML_FUNCTIONS (ML-Functions-Service)
- **Función:** Motor de cálculo matemático/estadístico.
- **Algoritmos:** Regresión Lineal/Logística, Gradiente Descendente, Normalización Z-score.

### 🗺️ LOCALIZATION (Localization-Service)
- **Función:** Gestión de rutas (Planificadas vs Ejecutadas) y Asistencia (Check-in/out).
- **Relación:** Provee datos geográficos a `PLANNING` y `FORMS`.

### 📝 FORMS (Forms-Service)
- **Función:** Formularios dinámicos/paramétricos.
- **Flujo:** Las respuestas temporales van a DynamoDB (sesión); al finalizar se guardan en MySQL.
- **Reportes:** Cruza datos con `PLANNING` y `LOCALIZATION`.

### 📅 PLANNING (Planning-Service)
- **Función:** Asignación operativa (Rutas, Equipos, Materiales).
- **Relación:** Define qué debe ejecutarse, base para `LOCALIZATION` y `TRADE`.

### 🛒 TRADE (Trade-Service) - *En Desarrollo*
- **Función:** Ejecución en Punto de Venta (Inventarios, Ventas, Fotos, Merchandising).
- **Estado:** Beta. Requiere ajustes constantes.
- **Features:** SKUs atómicos, manejo de stock, visitas Ad-Hoc.

## 🚀 Tareas Pendientes y Futuras (Roadmap)
- Implementación de **Alembic** para migraciones de BD.
- Creación de **Tests Unitarios** básicos.
- Actualización de documentación automática.