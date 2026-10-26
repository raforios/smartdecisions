# 📊 Finance-Service 💰

Microservicio del **Análisis Financiero** de SmartDecisions. Con cifras agregadas por cuenta —diarias, mensuales o anuales, en bolivianos— arma el Estado de Resultados y el Balance General, y proyecta los meses siguientes en tres escenarios.

-----

## 🎯 Propósito Principal

El **Finance-Service** convierte los montos de cada cuenta en informes y respuestas para el gerente. Sus funcionalidades clave incluyen:

  * **Catálogo de Cuentas:** Uno solo, de BearSoft; sólo el `ADMIN` lo cambia.
  * **Tasas de Ley:** IVA, IT e IUE con la fecha desde la que rigen; un mes se calcula con la tasa vigente en ese mes.
  * **Carga de Montos:** Por API o por la plantilla, con el historial de cargas; cada monto se corrige o se borra, y un período se vacía.
  * **Informe:** Estado de Resultados, impuestos, Balance General e indicadores por mes y año, calculado al pedirlo; cada línea dice si fue cargada o calculada.
  * **Proyección:** Tres escenarios (peor, realista, mejor) con la serie proyectada por ML-Functions y los porcentajes que el gerente puede cambiar.
  * **Modelo de Negocio:** Lo que el cliente describe de su negocio, para leer sus números.
  * **Moneda:** Todo en bolivianos; dólar oficial y USDT de QUOTES como referencia.

-----

## 🛠️ Tecnologías Utilizadas

  * **Lenguaje:** Python 3.14 🐍
  * **Framework Web:** FastAPI ✨
  * **Servidor ASGI:** Uvicorn 🚀
  * **Base de Datos:** AWS DynamoDB (`boto3`)
  * **Lectura de Plantillas:** pandas y `openpyxl`, a través de FILES
  * **Validación de Datos:** Pydantic V2
  * **Plataforma Cloud:** AWS Lambda (`Mangum`) detrás de `api.bearsoft.com.bo`

-----

## 🚀 Endpoints de la API

A continuación se listan los **endpoints** de la API, agrupados por su funcionalidad. Todos exigen `Authorization: Bearer <jwt>` salvo que se indique otra cosa.

### Catálogo y Tasas de Ley

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `GET` | `/v1/finance/accounts` | El **catálogo de cuentas**. |
| `POST` | `/v1/finance/accounts` | Agrega una **cuenta** al catálogo. Sólo `ADMIN`. |
| `PATCH` | `/v1/finance/accounts/{account_code}` | Cambia el nombre de una **cuenta**. Sólo `ADMIN`. |
| `DELETE` | `/v1/finance/accounts/{account_code}` | Quita una **cuenta** sin montos cargados. Sólo `ADMIN`. |
| `GET` | `/v1/finance/law-parameters` | Las **tasas de ley**, con el día desde el que rige cada una. |
| `POST` | `/v1/finance/law-parameters` | Registra una **tasa** desde el día en que rige. Sólo `ADMIN`. |

### Cargas y Montos

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/v1/finance/loads` | Carga **montos** por API. `MANAGER`. |
| `POST` | `/v1/finance/loads/file` | Carga **montos** desde la plantilla subida a FILES. `MANAGER`. |
| `GET` | `/v1/finance/loads` | Las **cargas** del cliente, la más reciente primero. |
| `GET` | `/v1/finance/entries` | Los **montos** del cliente. |
| `PATCH` | `/v1/finance/entries` | Corrige un **monto**. |
| `DELETE` | `/v1/finance/entries` | Elimina un **monto**. |
| `DELETE` | `/v1/finance/periods` | Vacía un **período**. |

### Informe, Proyección y Parámetros

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `GET` | `/v1/finance/report` | El **informe financiero**: Estado de Resultados, impuestos, Balance e indicadores por mes y año. |
| `GET` | `/v1/finance/projection` | La **proyección** de los meses siguientes en tres escenarios. |
| `GET` | `/v1/finance/parameters` | Los **parámetros** que el cliente puede fijar, junto a la sugerencia. |
| `PUT` | `/v1/finance/parameters/{parameter_code}` | Fija el valor que el cliente eligió para un **parámetro**. |
| `GET` | `/v1/finance/suggested-parameters` | Los valores que BearSoft **sugiere** a todos los clientes. |
| `PUT` | `/v1/finance/suggested-parameters` | Fija un valor **sugerido**. Sólo `ADMIN`. |
| `GET` | `/v1/finance/business-model` | El **modelo de negocio** que describió el cliente. |
| `PUT` | `/v1/finance/business-model` | Guarda el **modelo de negocio** del cliente. |

### Salud

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `GET` | `/` | Página de inicio del servicio. |
| `GET` | `/v1/finance/health` | Salud del servicio y validación de su configuración. |
| `GET` | `/v1/finance/health/tables` | Estado de las tablas DynamoDB del servicio. |

-----

## 🗄️ Datos que guarda

| Tabla | Partición | Orden | Qué guarda |
|---|---|---|---|
| `finance_accounts` | `account_code` | — | El catálogo de cuentas |
| `finance_law_parameters` | `parameter_code` | `valid_from` | Las tasas de ley y desde cuándo rigen |
| `finance_loads` | `client` | `load_id` | El historial de cargas |
| `finance_entries` | `client` | `entry_key` | Los montos por cuenta y período (índice `account_code-index`) |
| `finance_suggested_parameters` | `parameter_code` | — | Los valores que BearSoft sugiere |
| `finance_client_parameters` | `client` | `parameter_code` | Los valores que cada cliente eligió |
| `finance_business_models` | `client` | — | El modelo de negocio de cada cliente |
| `finance_parameters` | `code` | — | Los valores de negocio del servicio |

El catálogo y las tasas se siembran desde el contrato aprobado (`docs/cambios/smartdecisions/contrato.md`):

```shell
python -m tools.seeds.seed_finance          # simulación
python -m tools.seeds.seed_finance --yes
```

-----

## ⚙️ Valores de negocio

Los valores de negocio del servicio viven en la tabla `finance_parameters` (un ítem por
código), no en el `.env`. Los lee `load_parameters`, del bloque SERVICE
PARAMETERS al final de `services/utils.py`, una vez por contenedor; un valor
cambiado en la tabla lo toman los contenedores que arrancan después. Si falta
uno, el servicio no arranca. Lo de cada cliente está en `finance_client_parameters`. Definición: filas `finance` de
`docs/parametros.md`. Siembra:

```shell
python -m tools.seeds.seed_service_parameters finance --yes
```

-----

## 🗂️ Estructura del Microservicio

```txt
finance/
├── controllers/
│   ├── __init__.py
│   ├── entries.py
│   ├── finance.py
│   └── report.py
├── models/
│   ├── __init__.py
│   └── finance.py
├── routes/
│   ├── __init__.py
│   ├── entries.py
│   ├── finance.py
│   └── report.py
├── schemas/
│   ├── __init__.py
│   ├── business_model.py
│   ├── entries.py
│   ├── files.py
│   ├── finance.py
│   ├── health.py
│   ├── projection.py
│   └── report.py
├── services/
│   ├── __init__.py
│   ├── api_exceptions.py
│   ├── business_model.py
│   ├── crud.py
│   ├── db_connection.py
│   ├── entries.py
│   ├── entries_validator.py
│   ├── environment.py
│   ├── exceptions.py
│   ├── finance.py
│   ├── finance_utils.py
│   ├── logger_config.py
│   ├── parameters.py
│   ├── projection.py
│   ├── rates.py
│   ├── report.py
│   ├── report_periods.py
│   ├── security.py
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

2.  **Configura el entorno:** Crea el archivo `.env` con `HOST`, `PORT`, `APP_ENV`, `SECRET_KEY`, `ALGORITHM`, `TARGET_TIMEZONE`, `ROOT_PATH`, `API_URL`, `BUCKET_NAME`, `BUCKET_PATH`, las tablas `DYNAMODB_TABLE_NAME_*` y los tiempos de espera.

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
