# 💱 Quotes-Service 📈

Microservicio de **cotizaciones y factores externos** de la plataforma de BearSoft: el dólar oficial del Banco Central de Bolivia, el USDT de Binance P2P como dólar paralelo, y los factores que cada empresa sigue (combustible, rendimiento y los que declare).

-----

## 🎯 Propósito Principal

El **Quotes-Service** guarda y sirve las cifras de mercado. Sus funcionalidades clave incluyen:

  * **Serie del Dólar:** Guarda una copia diaria de la cotización oficial (el BCB sirve una fecha por llamada) y del USDT; la serie sin fecha de inicio arranca en el régimen flotante del 27-jun-2026.
  * **Sincronización Programada:** Una regla de EventBridge (`cron(0 13 * * ? *)`, 09:00 La Paz) invoca el Lambda con `{"task": "sync_rates"}` y repara los últimos días.
  * **Proyección del Dólar:** Pide la proyección a ML-Functions (`/v1/prediction/forecast/compare`); aquí se decide la confianza y se rechaza una proyección que se desploma.
  * **Factores Externos:** Cada empresa declara sus factores y registra su historia fechada; un cálculo usa el valor y el estado de su propia fecha.
  * **Costo de Transporte:** Lo que cuesta una entrega local por una distancia, con los factores de combustible.

-----

## 🛠️ Tecnologías Utilizadas

  * **Lenguaje:** Python 3.14 🐍
  * **Framework Web:** FastAPI ✨
  * **Servidor ASGI:** Uvicorn 🚀
  * **Base de Datos:** AWS DynamoDB (`boto3`)
  * **Fuentes:** BCB (HTML) y Binance P2P (`requests`)
  * **Validación de Datos:** Pydantic V2
  * **Plataforma Cloud:** AWS Lambda (`Mangum`) y EventBridge

-----

## 🚀 Endpoints de la API

A continuación se listan los **endpoints** de la API, agrupados por su funcionalidad. Todos exigen `Authorization: Bearer <jwt>` salvo que se indique otra cosa.

### Tipo de Cambio (`/v1/quotes`)

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `GET` | `/v1/quotes/exchange-rates` | La **serie** guardada, oficial y USDT. |
| `GET` | `/v1/quotes/exchange-rates/at` | La **cotización** vigente en un día. |
| `POST` | `/v1/quotes/exchange-rates/sync` | Trae las **cotizaciones** publicadas que falten. Idempotente. |
| `GET` | `/v1/quotes/exchange-rates/forecast` | Hacia dónde va el **dólar oficial**, con su confianza. |
| `GET` | `/v1/quotes/exchange-rates/bench` | Compara los **modelos de proyección** sobre la misma serie. |

### Factores Externos (`/v1/quotes/factors`)

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/v1/quotes/factors` | Declara un **factor** de la empresa. |
| `GET` | `/v1/quotes/factors` | Los **factores** de la empresa, con su última lectura. |
| `POST` | `/v1/quotes/factors/{code}/values` | Carga lecturas de un **factor**. |
| `GET` | `/v1/quotes/factors/{code}/values` | La serie de un **factor**. |
| `GET` | `/v1/quotes/factors/{code}/state` | Lo que un **factor** era en un día dado. |
| `GET` | `/v1/quotes/factors/transport-cost` | Lo que cuesta una **entrega local** por una distancia. |

### Salud

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `GET` | `/` | Página de inicio del servicio. |
| `GET` | `/v1/quotes/health` | Salud del servicio y validación de su configuración. |
| `GET` | `/v1/quotes/health/tables` | Estado de las tablas DynamoDB del servicio. |

-----

## 🗄️ Datos que guarda

| Tabla | Partición | Orden | Qué guarda |
|---|---|---|---|
| `exchange_rates` | `currency` | `date` (`YYYY-MM-DD`) | Cotización del día: `official_rate`, `source`, `retrieved_at` (`models/quotes.py`) |
| `quotes_factors` | `owner_email` | `code` | Declaración de cada factor: `name`, `unit`, `source`, `status`, `latest_date`, `latest_value` (`models/factors.py`) |
| `quotes_factor_values` | `owner_code` (`{owner_email}#{code}`) | `factor_date` | Historia fechada de cada factor: `value`, `recorded_at` |
| `quotes_parameters` | `code` | — | Los valores de negocio del servicio |

Códigos de error en `schemas/quotes.py` y `schemas/factors.py`: `SOURCE_UNAVAILABLE`, `SOURCE_UNREADABLE`, `NO_RATE_PUBLISHED`, `EMPTY_PERIOD`, `INVALID_DATE_RANGE`, entre otros.

-----

## ⚙️ Valores de negocio

Los valores de negocio del servicio viven en la tabla `quotes_parameters` (un ítem por
código), no en el `.env`. Los lee `load_parameters`, del bloque SERVICE
PARAMETERS al final de `services/utils.py`, una vez por contenedor; un valor
cambiado en la tabla lo toman los contenedores que arrancan después. Si falta
uno, el servicio no arranca. Definición: filas `quotes` de
`docs/parametros.md`. Siembra:

```shell
python -m tools.seeds.seed_service_parameters quotes --yes
```

-----

## ⏰ Sincronización Programada

```shell
bash services/ci/api/create_schedules.sh        # crea la regla; idempotente, después de desplegar
aws lambda invoke --function-name quotes-handler-service \
    --payload '{"task":"sync_rates"}' --cli-binary-format raw-in-base64-out \
    --profile deploy_ml /dev/stdout                 # probarla sin esperar al horario
```

Si la sincronización falla, la invocación falla (`RuntimeError`), para que EventBridge reintente y el fallo se vea en las métricas.

-----

## 🗂️ Estructura del Microservicio

```txt
quotes/
├── controllers/
│   ├── __init__.py
│   ├── factors.py
│   └── quotes.py
├── models/
│   ├── __init__.py
│   ├── factors.py
│   └── quotes.py
├── routes/
│   ├── __init__.py
│   ├── factors.py
│   └── quotes.py
├── schemas/
│   ├── __init__.py
│   ├── factors.py
│   ├── health.py
│   └── quotes.py
├── services/
│   ├── __init__.py
│   ├── api_exceptions.py
│   ├── bcb_source.py
│   ├── crud.py
│   ├── db_connection.py
│   ├── environment.py
│   ├── exceptions.py
│   ├── factors.py
│   ├── logger_config.py
│   ├── quotes.py
│   ├── quotes_utils.py
│   ├── rate_forecast.py
│   ├── security.py
│   ├── usdt_source.py
│   └── utils.py
├── tests/
├── .dockerignore
├── .env
├── .gitignore
├── deploy.config
├── main.py
├── README.md
└── requirements.txt
```

-----

## 📀 Ejecución Local

Para ejecutar el microservicio localmente, sigue los siguientes pasos:

1.  **Instala las dependencias:**

```shell
pip install -r requirements.txt
```

2.  **Configura el entorno:** Crea el archivo `.env` con `HOST`, `PORT`, `APP_ENV`, `SECRET_KEY`, `ALGORITHM`, `TARGET_TIMEZONE`, `ROOT_PATH`, `API_URL`, las tablas `DYNAMODB_TABLE_NAME_*`, `BCB_BASE_URL`, `USDT_SOURCE_URL` y sus tiempos de espera, y `REQUEST_TIMEOUT_SECONDS`.

3.  **Ejecuta el servidor de la API:**

```shell
python main.py
```

4.  **Ejecuta las pruebas:**

```shell
python -m pytest -q
pylint --fail-under=10.0 .
```

-----

## 👤 Creado Por

**Rafael Ríos Bascón**
[raforios@gmail.com](mailto:raforios@gmail.com)
