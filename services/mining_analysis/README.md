# ⛏️ Mining-Analysis-Service 📊

Bienvenido al microservicio de **Análisis Minero**, un componente estratégico dentro de la arquitectura de la API **SMARTBEAR**. Este servicio actúa como un **Data Warehouse** especializado en el sector minero, permitiendo la ingesta, normalización y análisis avanzado tanto de cotizaciones de minerales como de la recaudación de regalías mineras, impulsando la generación de KPI's críticos.

---

## 🎯 Propósito Principal

El **Mining-Analysis-Service** está diseñado para centralizar la inteligencia de mercado y la gestión financiera del sector minero. Su propósito es transformar datos operativos brutos en información estratégica para la toma de decisiones. Sus funcionalidades clave incluyen:

* **Motor ETL Especializado:** Capacidad dual para procesar archivos CSV (cotizaciones diarias con limpieza automática de formatos numéricos latinos) y archivos Excel (liquidaciones y transacciones de regalías procesadas directamente en memoria).
* **Data Warehouse Relacional:** Almacena de forma eficiente y normalizada el catálogo de minerales (`t_minerals`), histórico de precios (`t_mining_prices`), padrón de operadores mineros (`t_companies`) y el desglose de distribución de regalías a nivel departamental y municipal (`t_royalties` y `t_royalty_transactions`).
* **Interconexión Institucional:** Provee **endpoints** seguros para que otras instituciones puedan consultar históricos de precios y resúmenes de recaudación de manera estandarizada.
* **Módulo de BI Integrado:** Diseñado para alimentar interfaces analíticas (como Streamlit), entregando estructuras de datos optimizadas para visualizaciones de tendencias, variaciones porcentuales (YOY/MoM) y distribución geográfica de recursos.
* **Auditoría y Trazabilidad:** Identificación precisa del usuario que ejecuta las cargas masivas con registros detallados en los logs del sistema, asegurando el seguimiento de operaciones financieras sensibles.

---

## 🛠️ Tecnologías Utilizadas

Este microservicio sigue los estándares de alta disponibilidad, precisión financiera y robustez de la arquitectura SmartBear:

* **Lenguaje:** Python 3.14 🐍
* **Framework Web:** FastAPI ✨
* **Servidor ASGI:** Uvicorn 🚀
* **ORM & Base de Datos:** SQLAlchemy (MySQL)
* **Validación de Datos:** Pydantic
* **Procesamiento de Datos:** Pandas 🐼
* **Seguridad:** JWT (Integrado con Central Auth Service)
* **Contenedorización:** Docker 🐳

---

## 🚀 Endpoints de la API

A continuación se listan los **endpoints** principales de la API, agrupados por su dominio de datos para una mejor referencia.

### Cotizaciones y Precios de Minerales

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/v1/mining-analysis/etl/upload` | Carga masiva de cotizaciones mineras desde un archivo CSV. Dispara proceso de normalización y auditoría. |
| `GET`  | `/v1/mining-analysis/prices` | Recupera el listado completo de precios históricos, incluyendo la metadata de cada mineral. |

### Regalías Mineras y Transacciones

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/v1/mining-analysis/royalties/upload` | Ejecuta el proceso ETL en memoria a partir de un archivo Excel con las liquidaciones oficiales del SIN. |
| `GET`  | `/v1/mining-analysis/royalties/summary` | Obtiene el resumen agregado de coparticipación de regalías mineras (recaudación bruta, comisiones y distribución neta a gobernaciones y municipios). Soporta filtrado por gestión fiscal. |
| `GET`  | `/v1/mining-analysis/royalties/transactions` | Recupera un análisis granular de las transacciones de pago de regalías agrupadas por empresa operadora (NIT), municipio y gestión. |

### Utilidades y Salud

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `GET` | `/` | Healthcheck del servicio, estado de la conexión a la base de datos y validación del entorno. |
| `GET` | `/docs` | Documentación interactiva Swagger UI con esquemas detallados de Request/Response. |

---

## 🗂️ Estructura del Microservicio

```txt
mining_analysis/
├── controllers/
│   ├── __init__.py
│   └── mining_analysis.py
├── models/
│   ├── __init__.py
│   └── mining_analysis.py
├── routes/
│   ├── __init__.py
│   └── mining_analysis.py
├── schemas/
│   ├── __init__.py
│   └── mining_analysis.py
├── services/
│   ├── __init__.py
│   ├── api_exceptions.py
│   ├── crud.py
│   ├── db_connection.py
│   ├── environment.py
│   ├── exceptions.py
│   ├── logger_config.py
│   ├── mining_analysis.py
│   ├── royalties_etl.py
│   ├── security.py
│   └── utils.py
├── .dockerignore
├── .env
├── .gitignore
├── deploy.config
├── Dockerfile
├── Dockerfile.api
├── main.py
├── README.md
├── requirements.txt
└── seed_locations.txt
```

---

## 📀 Ejecución Local

Para levantar el microservicio en tu entorno de desarrollo local, sigue estos pasos:

1. **Instalar dependencias:**
   ```shell
   pip install -r requirements.txt
   ```

2. **Configurar Variables de Entorno:** Renombra o crea un archivo `.env` en la raíz del proyecto y ajusta las credenciales de conexión a MySQL, así como la URL del servicio de autenticación central.

3. **Iniciar el Servicio:**
   ```shell
   python main.py
   ```
   *(El servidor se iniciará típicamente en `http://localhost:3000`, y podrás acceder a la documentación en `/docs`).*

---

## 👤 Creado Por

**Rafael Ríos Bascón** [raforios@gmail.com](mailto:raforios@gmail.com)
