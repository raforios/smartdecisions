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

Este microservicio sigue los estándares de alta disponibilidad, precisión financiera y robustez de la arquitectura SmartDecisions:

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
| `GET`  | `/v1/mining-analysis/reports/daily?date=YYYY-MM-DD` | Devuelve la cotización más reciente por mineral del catálogo oficial hasta la fecha indicada, con `is_fallback = true` cuando se usa un día anterior. Incluye `previous_price_low` y `change_pct` (variación vs. día previo con dato). Insumo del reporte interno **Minerales_01**. |
| `GET`  | `/v1/mining-analysis/reports/biweekly?year=YYYY&month=MM&half=1\|2` | Promedio simple de `price_low` por mineral en la quincena solicitada (`half=1` cubre los días 1-15; `half=2` cubre del 16 al fin de mes). Cuando no hay datos en el periodo, retrocede hasta hallar la quincena más reciente con cotizaciones. Insumo del reporte oficial **Minerales_02**. |

### Endpoints públicos (sin JWT) para el sitio institucional

Pensados para `mineria.gob.bo` y otros consumidores anónimos. Requieren que el dominio esté listado en la variable de entorno `CORS_ORIGINS` (lista separada por coma).

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `GET`  | `/v1/mining-analysis/public/reports/daily?date=YYYY-MM-DD` | Idéntico a `/reports/daily` pero anónimo. |
| `GET`  | `/v1/mining-analysis/public/reports/biweekly?year=&month=&half=` | Idéntico a `/reports/biweekly` pero anónimo. |
| `GET`  | `/v1/mining-analysis/public/reports/biweekly/history?from=YYYY-MM-DD&to=YYYY-MM-DD` | Serie histórica de quincenas con datos, ordenada cronológicamente. `from`/`to` opcionales (defaults a `MIN`/`MAX` de `t_mining_prices`). |
| `GET`  | `/v1/mining-analysis/public/reports/daily/{png\|pdf}?date=YYYY-MM-DD` | Reporte diario renderizado sobre la plantilla **Minerales_01** (binario, descarga directa). |
| `GET`  | `/v1/mining-analysis/public/reports/biweekly/{png\|pdf}?year=&month=&half=` | Reporte quincenal renderizado sobre la plantilla **Minerales_02** (binario, descarga directa). |

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

## 🧰 Scripts Operativos

Los scripts viven en `scripts/` y se ejecutan como módulos para que respeten el `PYTHONPATH` del microservicio. Todos exponen `--yes` como interruptor explícito de escritura; sin él imprimen el plan y salen sin tocar la base de datos.

### Backfill de `t_mining_prices`
Reproceso completo con el ETL ya corregido (separador decimal anglo/europeo). Borra el contenido actual de `t_mining_prices` antes de reingresar el archivo fuente:

```shell
python -m scripts.backfill_prices --source /ruta/cotizaciones_min.xlsx --yes
```

### Ingesta de Diarios extraídos de PDFs escaneados
Carga las hojas `… Q1/Q2 - Diario` del Excel curado (`cotizaciones_mineras_bolivia.xlsx`) en `t_mining_prices`. Idempotente: omite fechas que ya tengan registro:

```shell
python -m scripts.ingest_pdf_xlsx --source /ruta/cotizaciones_mineras_bolivia.xlsx --yes
```

---

## 🧪 Pruebas

```shell
pytest -v
```

Suite enfocada en:
- `clean_currency_pro` (formato anglo vs. europeo, casos límite y la regresión Bismuto `17.54 → 1754`).
- Servicio de reporte diario con fallback al registro previo más reciente.
- Servicio de reporte quincenal con promedio sobre días disponibles, fallback al periodo anterior y manejo de `half` inválido.
- Idempotencia del seed `ensure_official_minerals`.

---

## 👤 Creado Por

**Rafael Ríos Bascón** [raforios@gmail.com](mailto:raforios@gmail.com)
