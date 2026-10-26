# 💱 Quotes-Service 📈

The **quotes and external factors** service of the BearSoft platform: the official dollar rate of the Central Bank of Bolivia, USDT from Binance P2P as the parallel dollar, and the factors each company tracks (fuel, efficiency and any it declares).

-----

## 🎯 Main Purpose

The **Quotes-Service** stores and serves market figures. Its key features:

  * **Dollar Series:** Keeps a daily copy of the official rate (the BCB serves one date per call) and of USDT; a series with no start date begins at the floating regime of 27-Jun-2026.
  * **Scheduled Sync:** An EventBridge rule (`cron(0 13 * * ? *)`, 09:00 La Paz) invokes the Lambda with `{"task": "sync_rates"}` and repairs the last days.
  * **Dollar Projection:** Asks ML-Functions for the projection (`/v1/prediction/forecast/compare`); the confidence is decided here, and a projection that collapses is refused.
  * **External Factors:** Each company declares its factors and records their dated history; a calculation uses the value and status of its own date.
  * **Transport Cost:** What a local delivery over a distance costs, from the fuel factors.

-----

## 🛠️ Technologies

  * **Language:** Python 3.14 🐍
  * **Web Framework:** FastAPI ✨
  * **ASGI Server:** Uvicorn 🚀
  * **Database:** AWS DynamoDB (`boto3`)
  * **Sources:** BCB (HTML) and Binance P2P (`requests`)
  * **Data Validation:** Pydantic V2
  * **Cloud Platform:** AWS Lambda (`Mangum`) and EventBridge

-----

## 🚀 API Endpoints

The API **endpoints**, grouped by feature. All of them require `Authorization: Bearer <jwt>` unless stated otherwise.

### Exchange Rates (`/v1/quotes`)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/v1/quotes/exchange-rates` | The stored **series**, official and USDT. |
| `GET` | `/v1/quotes/exchange-rates/at` | The **rate** in force on one day. |
| `POST` | `/v1/quotes/exchange-rates/sync` | Pulls the published **rates** that are missing. Idempotent. |
| `GET` | `/v1/quotes/exchange-rates/forecast` | Where the **official rate** is heading, with its confidence. |
| `GET` | `/v1/quotes/exchange-rates/bench` | Compares the **projection models** on the same series. |

### External Factors (`/v1/quotes/factors`)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/v1/quotes/factors` | Declares a company **factor**. |
| `GET` | `/v1/quotes/factors` | The company's **factors**, with their latest reading. |
| `POST` | `/v1/quotes/factors/{code}/values` | Loads readings of a **factor**. |
| `GET` | `/v1/quotes/factors/{code}/values` | The series of a **factor**. |
| `GET` | `/v1/quotes/factors/{code}/state` | What a **factor** was on a given day. |
| `GET` | `/v1/quotes/factors/transport-cost` | What a **local delivery** over a distance costs. |

### Health

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Service home page. |
| `GET` | `/v1/quotes/health` | Service health and configuration check. |
| `GET` | `/v1/quotes/health/tables` | State of the service's DynamoDB tables. |

-----

## 🗄️ Stored Data

| Table | Partition key | Sort key | What it holds |
|---|---|---|---|
| `exchange_rates` | `currency` | `date` (`YYYY-MM-DD`) | The day's rate: `official_rate`, `source`, `retrieved_at` (`models/quotes.py`) |
| `quotes_factors` | `owner_email` | `code` | Each factor's declaration: `name`, `unit`, `source`, `status`, `latest_date`, `latest_value` (`models/factors.py`) |
| `quotes_factor_values` | `owner_code` (`{owner_email}#{code}`) | `factor_date` | Each factor's dated history: `value`, `recorded_at` |
| `quotes_parameters` | `code` | — | The service's business values |

Error codes in `schemas/quotes.py` and `schemas/factors.py`: `SOURCE_UNAVAILABLE`, `SOURCE_UNREADABLE`, `NO_RATE_PUBLISHED`, `EMPTY_PERIOD`, `INVALID_DATE_RANGE`, among others.

-----

## ⚙️ Business Values

The service's business values live in the `quotes_parameters` table (one item per code),
not in `.env`. They are read by `load_parameters`, from the SERVICE PARAMETERS
block at the end of `services/utils.py`, once per container; a value changed in
the table is picked up by the containers that start afterwards. If one is
missing, the service does not start. Definition: the `quotes` rows of
`docs/parametros.md`. Seed:

```shell
python -m tools.seeds.seed_service_parameters quotes --yes
```

-----

## ⏰ Scheduled Sync

```shell
bash services/ci/api/create_schedules.sh        # creates the rule; idempotent, run after deploying
aws lambda invoke --function-name quotes-handler-service \
    --payload '{"task":"sync_rates"}' --cli-binary-format raw-in-base64-out \
    --profile deploy_ml /dev/stdout                 # try it without waiting for the schedule
```

If the sync fails, the invocation fails (`RuntimeError`), so EventBridge retries and the failure shows in the metrics.

-----

## 🗂️ Service Structure

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

## 📀 Local Setup

To run the service locally:

1.  **Install the dependencies:**

```shell
pip install -r requirements.txt
```

2.  **Configure the environment:** Create the `.env` file with `HOST`, `PORT`, `APP_ENV`, `SECRET_KEY`, `ALGORITHM`, `TARGET_TIMEZONE`, `ROOT_PATH`, `API_URL`, the tables `DYNAMODB_TABLE_NAME_*`, `BCB_BASE_URL`, `USDT_SOURCE_URL` and their timeouts, and `REQUEST_TIMEOUT_SECONDS`.

3.  **Start the API server:**

```shell
python main.py
```

4.  **Run the tests:**

```shell
python -m pytest -q
pylint --fail-under=10.0 .
```

-----

## 👤 Created By

**Rafael Ríos Bascón**
[raforios@gmail.com](mailto:raforios@gmail.com)
