# 📊 Finance-Service 💰

The **Financial Analysis** service of SmartDecisions. From amounts aggregated by account —daily, monthly or yearly, in bolivianos— it builds the Income Statement and the Balance Sheet, and projects the coming months in three scenarios.

-----

## 🎯 Main Purpose

The **Finance-Service** turns the amounts of each account into reports and answers for the manager. Its key features:

  * **Chart of Accounts:** A single one, owned by BearSoft; only the `ADMIN` changes it.
  * **Statutory Rates:** VAT (IVA), IT and IUE with the date each applies from; a month is computed with the rate in force that month.
  * **Amount Loads:** By API or by the template, with the load history; each amount can be corrected or removed, and a period emptied.
  * **Report:** Income Statement, taxes, Balance Sheet and ratios by month and year, computed on request; each line says whether it was loaded or calculated.
  * **Projection:** Three scenarios (worst, realistic, best) with the series projected by ML-Functions and percentages the manager can change.
  * **Business Model:** What the client describes about their business, to read their figures.
  * **Currency:** Everything in bolivianos; official dollar and USDT from QUOTES as reference.

-----

## 🛠️ Technologies

  * **Language:** Python 3.14 🐍
  * **Web Framework:** FastAPI ✨
  * **ASGI Server:** Uvicorn 🚀
  * **Database:** AWS DynamoDB (`boto3`)
  * **Template Reading:** through FILES
  * **Data Validation:** Pydantic V2
  * **Cloud Platform:** AWS Lambda (`Mangum`) behind `api.bearsoft.com.bo`

-----

## 🚀 API Endpoints

The API **endpoints**, grouped by feature. All of them require `Authorization: Bearer <jwt>` unless stated otherwise.

### Chart of Accounts and Statutory Rates

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/v1/finance/accounts` | The **chart of accounts**. |
| `POST` | `/v1/finance/accounts` | Adds an **account** to the chart. `ADMIN` only. |
| `PATCH` | `/v1/finance/accounts/{account_code}` | Renames an **account**. `ADMIN` only. |
| `DELETE` | `/v1/finance/accounts/{account_code}` | Removes an **account** with no amounts loaded. `ADMIN` only. |
| `GET` | `/v1/finance/law-parameters` | The **statutory rates**, with the day each one applies from. |
| `POST` | `/v1/finance/law-parameters` | Sets a **rate** from the day it applies. `ADMIN` only. |

### Loads and Amounts

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/v1/finance/loads` | Loads **amounts** by API. `MANAGER`. |
| `POST` | `/v1/finance/loads/file` | Loads **amounts** from the template uploaded to FILES. `MANAGER`. |
| `GET` | `/v1/finance/loads` | The client's **loads**, newest first. |
| `GET` | `/v1/finance/entries` | The client's **amounts**. |
| `PATCH` | `/v1/finance/entries` | Corrects one **amount**. |
| `DELETE` | `/v1/finance/entries` | Removes one **amount**. |
| `DELETE` | `/v1/finance/periods` | Empties a **period**. |

### Report, Projection and Parameters

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/v1/finance/report` | The **financial report**: Income Statement, taxes, Balance Sheet and ratios by month and year. |
| `GET` | `/v1/finance/projection` | How the next months may go, in three **scenarios**. |
| `GET` | `/v1/finance/parameters` | The **parameters** the client can set, next to the suggestion. |
| `PUT` | `/v1/finance/parameters/{parameter_code}` | Sets the value the client chose for a **parameter**. |
| `GET` | `/v1/finance/suggested-parameters` | The values BearSoft **suggests** to every client. |
| `PUT` | `/v1/finance/suggested-parameters` | Sets a **suggested** value. `ADMIN` only. |
| `GET` | `/v1/finance/business-model` | The **business model** the client described. |
| `PUT` | `/v1/finance/business-model` | Saves the client's **business model**. |

### Health

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Service home page. |
| `GET` | `/v1/finance/health` | Service health and configuration check. |
| `GET` | `/v1/finance/health/tables` | State of the service's DynamoDB tables. |

-----

## 🗄️ Stored Data

| Table | Partition key | Sort key | What it holds |
|---|---|---|---|
| `finance_accounts` | `account_code` | — | The chart of accounts |
| `finance_law_parameters` | `parameter_code` | `valid_from` | The statutory rates and since when they apply |
| `finance_loads` | `client` | `load_id` | The load history |
| `finance_entries` | `client` | `entry_key` | The amounts by account and period (index `account_code-index`) |
| `finance_suggested_parameters` | `parameter_code` | — | The values BearSoft suggests |
| `finance_client_parameters` | `client` | `parameter_code` | The values each client chose |
| `finance_business_models` | `client` | — | Each client's business model |
| `finance_parameters` | `code` | — | The service's business values |

The chart of accounts and the rates are seeded from the approved contract (`docs/cambios/smartdecisions/contrato.md`):

```shell
python -m tools.seeds.seed_finance          # dry run
python -m tools.seeds.seed_finance --yes
```

-----

## ⚙️ Business Values

The service's business values live in the `finance_parameters` table (one item per code),
not in `.env`. They are read by `load_parameters`, from the SERVICE PARAMETERS
block at the end of `services/utils.py`, once per container; a value changed in
the table is picked up by the containers that start afterwards. If one is
missing, the service does not start. What each client sets lives in `finance_client_parameters`. Definition: the `finance` rows of
`docs/parametros.md`. Seed:

```shell
python -m tools.seeds.seed_service_parameters finance --yes
```

-----

## 🗂️ Service Structure

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

## 📀 Local Setup

To run the service locally:

1.  **Install the dependencies:**

```shell
pip install -r requirements.txt
```

2.  **Configure the environment:** Create the `.env` file with `HOST`, `PORT`, `APP_ENV`, `SECRET_KEY`, `ALGORITHM`, `TARGET_TIMEZONE`, `ROOT_PATH`, `API_URL`, `BUCKET_NAME`, `BUCKET_PATH`, the tables `DYNAMODB_TABLE_NAME_*` and the timeouts.

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
