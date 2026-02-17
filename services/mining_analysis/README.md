# ⛏️ Mining-Analysis-Service 📊

Bienvenido al microservicio de **Análisis Minero**, un componente estratégico dentro de la arquitectura de la API **SMARTBEAR**. Este servicio actúa como un **Data Warehouse** especializado en el sector minero, permitiendo la ingesta, normalización y análisis de cotizaciones de minerales para la generación de KPI's críticos.

-----

## 🎯 Propósito Principal

El **Mining-Analysis-Service** está diseñado para centralizar la inteligencia de mercado minero. Su propósito es transformar datos operativos en información estratégica para la toma de decisiones. Sus funcionalidades clave incluyen:

  * **Motor ETL Especializado:** Permite la carga de archivos CSV con cotizaciones diarias, realizando una limpieza automática de formatos numéricos latinos y normalizando la información en un esquema relacional.
  * **Data Warehouse Normalizado:** Almacena de forma eficiente el catálogo de minerales (`t_minerals`) y su histórico de precios (`t_mining_prices`), garantizando integridad referencial y precisión financiera.
  * **Interconexión Institucional:** Provee **endpoints** seguros para que otras instituciones puedan consultar el histórico de precios de manera estandarizada.
  * **Módulo de BI (Dashboard):** Integra una interfaz en **Streamlit** que consume los propios endpoints del servicio para visualizar tendencias y variaciones de precios mediante gráficos interactivos.
  * **Auditoría y Trazabilidad:** Cada proceso de carga masiva genera eventos de auditoría asíncronos para el seguimiento de operaciones sensibles.

-----

## 🛠️ Tecnologías Utilizadas

Este microservicio sigue los estándares de alta disponibilidad y precisión de la arquitectura SmartBear:

  * **Lenguaje:** Python 3.13 🐍
  * **Framework Web:** FastAPI ✨
  * **Servidor ASGI:** Uvicorn 🚀
  * **ORM:** SQLAlchemy (MySQL)
  * **Procesamiento de Datos:** Pandas 🐼
  * **Visualización:** Streamlit & Plotly
  * **Seguridad:** JWT (Integrado con Central Auth Service)
  * **Contenedorización:** Docker 🐳

-----

## 🚀 Endpoints de la API

### Gestión de Precios y ETL

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/v1/mining-analysis/etl/upload` | Carga masiva de cotizaciones desde un archivo CSV. Dispara proceso de normalización y auditoría. |
| `GET`  | `/v1/mining-analysis/prices` | Recupera el listado completo de precios históricos con metadatos del mineral. |

### Utilidades y Salud

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `GET` | `/` | Healthcheck del servicio, estado de la base de datos y entorno. |
| `GET` | `/docs` | Documentación interactiva Swagger UI. |

-----

## 🗂️ Estructura del Microservicio

    ```txt
    mining_analysis/
    ├── controllers/      # Lógica de orquestación (mining_analysis.py)
    ├── models/           # Definición de tablas t_minerals, t_mining_prices
    ├── routes/           # Definición de endpoints y seguridad
    ├── schemas/          # Contratos Pydantic v2 (Request/Response)
    ├── services/         # Lógica de negocio, ETL y utilitarios
    ├── dashboard/        # Interfaz BI en Streamlit
    ├── main.py           # Punto de entrada FastAPI
    └── requirements.txt  # Dependencias del sistema
    ```

-----

## 📀 Ejecución Local

1.  **Instalar dependencias:**
    ```shell
    pip install -r requirements.txt
    ```
2.  **Configurar Variables:** Ajustar el archivo `.env` con las credenciales de MySQL y la URL del servicio de Auth.
3.  **Iniciar Servicio:**
    ```shell
    python main.py
    ```

-----

## 👤 Creado Por

**Rafael Ríos Bascón** [raforios@gmail.com](mailto:raforios@gmail.com)
