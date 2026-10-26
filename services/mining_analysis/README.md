# ⛏️ Mining-Analysis-Service 📊

The **mining analysis** service of SmartDecisions. It stores and serves the official mineral quotations, the market prices that anticipate them and the royalty scales, and answers whether to sell today or wait.

-----

## 🎯 Main Purpose

The **Mining-Analysis-Service** centralizes mineral price information. Its key features:

  * **Official Quotations:** The fortnightly quotations per mineral and the daily (**Minerales_01**) and fortnightly (**Minerales_02**) reports, falling back to the latest available data.
  * **Public Reports:** The same reports without JWT, as JSON, PDF and PNG, for the institutional website.
  * **Market Prices:** Daily sync of the LBMA fixings (via Westmetall) and LME cash, and the estimate of the official quotation of the current fortnight.
  * **Price Projection:** Each mineral's series projected by ML-Functions (`/v1/prediction/forecast/compare`), with its confidence.
  * **Royalties:** The Art. 227 scales per mineral.
  * **Sell Today or Wait:** Compares both ends in bolivianos with the projected dollar from QUOTES.
  * **Switchable Persistence:** DynamoDB on AWS or MySQL locally, according to `PERSISTENCE_BACKEND`.

-----

## 🛠️ Technologies

  * **Language:** Python 3.14 🐍
  * **Web Framework:** FastAPI ✨
  * **ASGI Server:** Uvicorn 🚀
  * **Database:** AWS DynamoDB (`boto3`) on AWS; MySQL (SQLAlchemy) locally
  * **Data Validation:** Pydantic V2
  * **Data Processing:** pandas 🐼
  * **Reports:** PDF and PNG over the official templates
  * **Cloud Platform:** AWS Lambda (`Mangum`) behind `api.bearsoft.com.bo`

-----

## 🚀 API Endpoints

The API **endpoints**, grouped by feature. All of them require `Authorization: Bearer <jwt>` except the public reports, meant for `mineria.gob.bo` and other anonymous consumers; the default CORS regex already covers `*.mineria.gob.bo`, `*.bearsoft.com.bo`, `*.cloudfront.net` and `localhost`, and other domains go in `CORS_ALLOWED_ORIGINS` (CSV list) or `CORS_ALLOWED_ORIGIN_REGEX`.

### Quotations, Projection and Market

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/v1/mining-analysis/prices` | Every stored official **quotation**, with each mineral's data. |
| `GET` | `/v1/mining-analysis/reports/daily?date=YYYY-MM-DD` | The latest **quotation** of each catalogue mineral up to that date (`is_fallback` when an earlier day is used), with the change against the previous day. Template **Minerales_01**. |
| `GET` | `/v1/mining-analysis/reports/biweekly?year=YYYY&month=MM&half=1\|2` | The fortnight **average** per mineral; with no data, it goes back to the latest fortnight with quotations. Template **Minerales_02**. |
| `GET` | `/v1/mining-analysis/forecast/prices` | A mineral's **price projection**, with its confidence. |
| `POST` | `/v1/mining-analysis/market/sync` | Reads the public **market sources** (LBMA via Westmetall, LME cash) and stores the missing days. |
| `GET` | `/v1/mining-analysis/market/estimate` | The **official quotation** each mineral is heading to, estimated from the fortnight's market. |
| `GET` | `/v1/mining-analysis/market/prices/{mineral_id}` | A mineral's daily **market series**. |
| `GET` | `/v1/mining-analysis/royalty-rules` | The **royalty scales** in force (Art. 227). |
| `PUT` | `/v1/mining-analysis/royalty-rules` | Creates or replaces a mineral's **royalty scale**. |
| `POST` | `/v1/mining-analysis/sale-scenario` | **Sell today or wait**: compares both ends in bolivianos. `ADMIN` only. |

### Public Reports (no JWT)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/v1/mining-analysis/public/reports/daily?date=YYYY-MM-DD` | Same as `/reports/daily`, anonymous. |
| `GET` | `/v1/mining-analysis/public/reports/biweekly?year=&month=&half=` | Same as `/reports/biweekly`, anonymous. |
| `GET` | `/v1/mining-analysis/public/reports/biweekly/history?from=YYYY-MM-DD&to=YYYY-MM-DD` | Historical series of the **fortnights** with data, in chronological order; `from` and `to` are optional. |
| `GET` | `/v1/mining-analysis/public/reports/daily/png` | Daily **report** rendered as PNG (template **Minerales_01**). |
| `GET` | `/v1/mining-analysis/public/reports/daily/pdf` | Daily **report** rendered as PDF (template **Minerales_01**). |
| `GET` | `/v1/mining-analysis/public/reports/biweekly/png` | Fortnightly **report** rendered as PNG (template **Minerales_02**). |
| `GET` | `/v1/mining-analysis/public/reports/biweekly/pdf` | Fortnightly **report** rendered as PDF (template **Minerales_02**). |

### Health

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Service home page. |
| `GET` | `/v1/mining-analysis/health` | Service health and configuration check. |
| `GET` | `/v1/mining-analysis/health/tables` | State of the service's DynamoDB tables. |

-----

## 🗄️ Stored Data

On DynamoDB (models in `models/mining_analysis_dyb.py` and `models/market_prices.py`):

| Table | Partition key | Sort key | What it holds |
|---|---|---|---|
| `minerals` | `mineral_id` | — | Catalogue: `name`, `unit`, `chemical_symbol`, `quoted_in`, `method`, `created_at` |
| `mining_prices` | `mineral_id` | `date` | Official fortnightly quotation: `price_low`, `price_high`, `created_at` |
| `mining_market_prices` | `mineral_id` | `date` | Daily market price (LME, LBMA): `price`, `source`, `retrieved_at` |
| `mining_royalty_rules` | `mineral_id` | — | Royalty rate: `slope`, `intercept`, `min_rate`, `max_rate`, `internal_factor`, `legal_basis`, `updated_at` |
| `mining_analysis_parameters` | `code` | — | The service's business values |

The sort key is what reads "this mineral between these two dates" in a single query. The relational data (departments, municipalities, companies, royalty transactions and payments) lives in the local MySQL, in `models/mining_analysis.py`, and is used only by the `*_sql.py` modules.

-----

## ⚙️ Business Values

The service's business values live in the `mining_analysis_parameters` table (one item per code),
not in `.env`. They are read by `load_parameters`, from the SERVICE PARAMETERS
block at the end of `services/utils.py`, once per container; a value changed in
the table is picked up by the containers that start afterwards. If one is
missing, the service does not start. Definition: the `mining_analysis` rows of
`docs/parametros.md`. Seed:

```shell
python -m tools.seeds.seed_service_parameters mining_analysis --yes
```

-----

## ☁️ Switchable Persistence

The service runs on **MySQL or DynamoDB**, according to `PERSISTENCE_BACKEND` in `.env`:

| Value | What it uses |
|---|---|
| `sql` | The relational engine of `DB_HOST` / `DATABASE`. |
| `dynamodb` | The DynamoDB tables above. |

**On AWS it must be `dynamodb`:** there is no RDS. To work locally against the Docker MySQL, set it to `sql`. The test suite is pinned to the SQL path by `tests/conftest.py`, so it does not depend on `.env` and never touches AWS.

-----

## 🧰 Operational Scripts

They live in `scripts/` and run as modules, so they keep the service's `PYTHONPATH`. **The ones that write require `--yes`**; without it they print the plan and exit without touching anything.

#### The fortnightly routine, in order

Used together every 15 days, when the Ministry PDF arrives:

**1. `audit_decimals.py` — before loading.** Read-only. The official PDF publishes two decimals (`WÓLFRAM 64205.75`); retyping them into the consolidated Excel sometimes drops them. It walks every `Diario` sheet, checks the average in the Excel against the arithmetic mean of the days, and lists the cells to verify against the PDF.

```shell
python -m scripts.audit_decimals                       # uses data/cotizaciones_mineras_bolivia.xlsx
python -m scripts.audit_decimals --source /path.xlsx --tolerance 0.01
```

**2. `ingest_pdf_xlsx.py` — the load.** Reads the `{Mes} Q{1|2} - Diario` sheets of the consolidated Excel and inserts them into `t_mining_prices`. Idempotent: dates already stored are skipped.

```shell
python -m scripts.ingest_pdf_xlsx --source /path/cotizaciones_mineras_bolivia.xlsx --yes
```

**3. `migrate_to_dynamodb.py` — publishing.** The load writes to the relational database and the deployed service reads DynamoDB, so the new fortnight has to be pushed. Idempotent: every write is a put by key, using as partition the same numeric id the SQL path exposes (`str(row.id)`).

```shell
python -m scripts.migrate_to_dynamodb            # reports what it would copy
python -m scripts.migrate_to_dynamodb --yes      # copies and verifies
```

`cli_support.py` is not run: it is the shared scaffolding (opens and closes the database session, aborts if the source file is missing).

#### Loading against MySQL, then publishing

```bash
PERSISTENCE_BACKEND=sql python main.py          # 1. the service against MySQL, without editing .env
                                                # 2. upload the xlsx from Streamlit (http://localhost:3020)
python -m scripts.migrate_to_dynamodb --yes     # 3. push the new fortnight to DynamoDB
```

#### Pointing Streamlit at the deployed service

`demo/utils/config.py` reads `API_BASE_URL` from the environment; its default is the service's former API Gateway URL.

```bash
export API_BASE_URL="https://api.bearsoft.com.bo/v1/mining-analysis"
streamlit run app.py
```

Against AWS the reads work (`/prices`, the daily and fortnightly reports, the PDF and the PNG); the fortnightly load runs locally, as above.

-----

## 🗂️ Service Structure

```txt
mining_analysis/
├── assets/
│   └── templates/
├── controllers/
│   ├── __init__.py
│   ├── market.py
│   └── mining_analysis.py
├── models/
│   ├── __init__.py
│   ├── market_prices.py
│   ├── mining_analysis.py
│   └── mining_analysis_dyb.py
├── routes/
│   ├── __init__.py
│   ├── market.py
│   ├── mining_analysis.py
│   └── public_reports.py
├── schemas/
│   ├── __init__.py
│   ├── health.py
│   ├── market.py
│   └── mining_analysis.py
├── scripts/
│   ├── __init__.py
│   ├── audit_decimals.py
│   ├── cli_support.py
│   ├── ingest_pdf_xlsx.py
│   └── migrate_to_dynamodb.py
├── services/
│   ├── __init__.py
│   ├── api_exceptions.py
│   ├── crud.py
│   ├── db_connection.py
│   ├── db_connection_sql.py
│   ├── environment.py
│   ├── exceptions.py
│   ├── logger_config.py
│   ├── market_sources.py
│   ├── mining_analysis.py
│   ├── official_estimate.py
│   ├── official_reports.py
│   ├── price_forecast.py
│   ├── prices_dyb.py
│   ├── prices_store.py
│   ├── reports_renderer.py
│   ├── royalty_rules.py
│   ├── sale_scenario.py
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

## 📀 Local Setup

To run the service locally:

1.  **Install the dependencies:**

```shell
pip install -r requirements.txt
```

2.  **Configure the environment:** Create the `.env` file with `HOST`, `PORT`, `APP_ENV`, `SECRET_KEY`, `ALGORITHM`, `TARGET_TIMEZONE`, `ROOT_PATH`, `API_URL`, `REQUEST_TIMEOUT_SECONDS`, `PERSISTENCE_BACKEND`, the MySQL connection (`DB_*`, `DATABASE`), the tables `DYNAMODB_TABLE_NAME_*` and the market sources (`LBMA_PRICES_URL`, `WESTMETALL_*`, `MARKET_SOURCE_TIMEOUT_SECONDS`).

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
