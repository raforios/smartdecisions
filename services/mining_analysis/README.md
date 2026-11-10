# ⛏️ Mining-Analysis-Service 📊

The **mining analysis** service of SmartDecisions. It stores and serves the official mineral quotations, the market prices that anticipate them and the royalty scales, and answers whether to sell today or wait.

-----

## 🎯 Main Purpose

The **Mining-Analysis-Service** centralizes mineral price information. Its key features:

  * **Official Quotations:** The fortnightly quotations per mineral and the daily (**Minerales_01**) and fortnightly (**Minerales_02**) reports, falling back to the latest available data.
  * **Market Prices:** Daily sync of the LBMA fixings (via Westmetall) and LME cash, and the estimate of the official quotation of the current fortnight.
  * **Price Projection:** Each mineral's series projected by ML-Functions (`/v1/prediction/forecast/compare`), with its confidence.
  * **Royalties:** The Art. 227 scales per mineral.
  * **Sell Today or Wait:** Compares both ends in bolivianos with the projected dollar from QUOTES.

-----

## 🛠️ Technologies

  * **Language:** Python 3.14 🐍
  * **Web Framework:** FastAPI ✨
  * **ASGI Server:** Uvicorn 🚀
  * **Database:** AWS DynamoDB (`boto3`)
  * **Data Validation:** Pydantic V2
  * **Cloud Platform:** AWS Lambda (`Mangum`) behind `api.bearsoft.com.bo`

-----

## 🚀 API Endpoints

The API **endpoints**, grouped by feature. All of them require `Authorization: Bearer <jwt>`. The PNG and PDF of the reports are drawn by the Streamlit app from `/reports/daily` and `/reports/biweekly`. The default CORS regex already covers `*.mineria.gob.bo`, `*.bearsoft.com.bo`, `*.cloudfront.net` and `localhost`, and other domains go in `CORS_ALLOWED_ORIGINS` (CSV list) or `CORS_ALLOWED_ORIGIN_REGEX`.

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
| `POST` | `/v1/mining-analysis/sale-scenario` | **Sell today or wait**: compares both ends in bolivianos. `ADMIN` only. |

### Health

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Service home page. |
| `GET` | `/v1/mining-analysis/health` | Service health and configuration check. |
| `GET` | `/v1/mining-analysis/health/tables` | State of the service's DynamoDB tables. |

-----

## 🗄️ Stored Data

On DynamoDB (models in `models/mining_analysis.py` and `models/market_prices.py`):

| Table | Partition key | Sort key | What it holds |
|---|---|---|---|
| `minerals` | `mineral_id` | — | Catalogue: `name`, `unit`, `chemical_symbol`, `quoted_in`, `method`, `created_at` |
| `mining_prices` | `mineral_id` | `date` | Official fortnightly quotation: `price_low`, `price_high`, `created_at` |
| `mining_market_prices` | `mineral_id` | `date` | Daily market price (LME, LBMA): `price`, `source`, `retrieved_at` |
| `mining_royalty_rules` | `mineral_id` | — | Royalty rate: `slope`, `intercept`, `min_rate`, `max_rate`, `internal_factor`, `legal_basis`, `updated_at` |
| `mining_analysis_parameters` | `code` | — | The service's business values |

The sort key is what reads "this mineral between these two dates" in a single query. The item definitions live in `models/mining_analysis.py`.

-----

## ⚙️ Business Values

The service's business values live in the `mining_analysis_parameters` table (one item per code),
not in `.env`. They are read by `load_parameters`, from the SERVICE PARAMETERS
block at the end of `core/utils.py`, once per container; a value changed in
the table is picked up by the containers that start afterwards. If one is
missing, the service does not start. Definition: the `mining_analysis` rows of
`docs/parametros.md`. Seed:

```shell
python -m tools.seeds.seed_service_parameters mining_analysis --yes
```

-----

## 🧰 Fortnightly Load

The service only reads. The fortnightly quotations are loaded by
`tools/etl_minerals/` (audit, load into its own MySQL, publish to DynamoDB),
which is independent of the API and imports nothing from this service. Steps
and environment: `tools/etl_minerals/README.md`, or the `/quincena-minerales`
skill.

#### Pointing Streamlit at the deployed service

`demo/utils/config.py` reads `API_BASE_URL` from the environment; its default is the service's former API Gateway URL.

```bash
export API_BASE_URL="https://api.bearsoft.com.bo/v1/mining-analysis"
streamlit run app.py
```

Against AWS the reads work (`/prices` and the daily and fortnightly reports).

-----

## 🗂️ Service Structure

```txt
mining_analysis/
├── controllers/
│   ├── __init__.py
│   ├── market.py
│   └── mining_analysis.py
├── models/
│   ├── __init__.py
│   ├── market_prices.py
│   └── mining_analysis.py
├── routes/
│   ├── __init__.py
│   ├── market.py
│   └── mining_analysis.py
├── schemas/
│   ├── __init__.py
│   ├── health.py
│   ├── market.py
│   └── mining_analysis.py
├── services/
│   ├── __init__.py
│   ├── api_exceptions.py
│   ├── crud.py
│   ├── db_connection.py
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

2.  **Configure the environment:** Create the `.env` file with `HOST`, `PORT`, `APP_ENV`, `SECRET_KEY`, `ALGORITHM`, `TARGET_TIMEZONE`, `API_URL`, `REQUEST_TIMEOUT_SECONDS`, the tables `DYNAMODB_TABLE_NAME_*` and the market sources (`LBMA_PRICES_URL`, `WESTMETALL_*`, `MARKET_SOURCE_TIMEOUT_SECONDS`).

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
