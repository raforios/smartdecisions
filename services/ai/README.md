# 💬 AI-Interpretation-Service 🤖

The **AI explanations** service of the BearSoft platform. It turns what a screen shows as data and codes into words, from the point of view of the expert configured for that screen.

-----

## 🎯 Main Purpose

The **AI-Interpretation-Service** explains what it receives, and nothing else. Its key features:

  * **View Explanation:** Takes `{view, data}` —the JSON returned by the service that produced the screen— and returns the text, the role used and its version.
  * **Roles per View:** Each view has versions of its role (context, mission, rules, model and tokens) in `ai_prompts`; one active per view, and each company may have its own.
  * **Cache:** An explanation is stored and reused while the same screen shows the same data.
  * **Payload Trimming:** A long list is trimmed to a sample, so a large screen is not a large bill.
  * **Model:** Claude Haiku 4.5 on Amazon Bedrock (`us.` inference profiles).

-----

## 🛠️ Technologies

  * **Language:** Python 3.14 🐍
  * **Web Framework:** FastAPI ✨
  * **ASGI Server:** Uvicorn 🚀
  * **Database:** AWS DynamoDB (`boto3`)
  * **AI:** Amazon Bedrock (`boto3`, `bedrock-runtime`)
  * **Data Validation:** Pydantic V2
  * **Cloud Platform:** AWS Lambda (`Mangum`) behind `api.bearsoft.com.bo`

-----

## 🚀 API Endpoints

The API **endpoints**, grouped by feature. All of them require `Authorization: Bearer <jwt>` unless stated otherwise.

### Explanations (`/v1/ai`)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/v1/ai/explain` | Explains what a **view** is showing. |

### Roles (`/v1/ai/roles`)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/v1/ai/roles` | The versions of each view's **role** and which one is active. |
| `POST` | `/v1/ai/roles` | Stores a version of a view's **role**. |
| `GET` | `/v1/ai/roles/{view}/{version}` | One full version of a **role**. |
| `PATCH` | `/v1/ai/roles/{view}/{version}/active` | Activates a version (retiring the others of that view) or turns it off. |
| `DELETE` | `/v1/ai/roles/{view}/{version}` | Deletes a version of a **role**. `ADMIN` only. |

### Health

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Service home page. |
| `GET` | `/v1/ai/health` | Service health and configuration check. |
| `GET` | `/v1/ai/health/tables` | State of the service's DynamoDB tables. |

-----

## 🗄️ Stored Data

| Table | Partition key | Sort key | What it holds |
|---|---|---|---|
| `ai_prompts` | `view` | `version` | Each view's role: `role`, `instructions`, `rules`, `model_id`, `max_tokens`, `active` and the owning company |
| `ai_explanations` | `cache_key` | — | Generated explanations, for reuse |
| `ai_parameters` | `code` | — | The service's business values |

Failures travel as codes: `EMPTY_PAYLOAD`, `ROLE_NOT_CONFIGURED`, `ROLE_NOT_FOUND`, `MODEL_UNAVAILABLE` and `MODEL_REFUSED`.

-----

## ⚙️ Business Values

The service's business values live in the `ai_parameters` table (one item per code),
not in `.env`. They are read by `load_parameters`, from the SERVICE PARAMETERS
block at the end of `services/utils.py`, once per container; a value changed in
the table is picked up by the containers that start afterwards. If one is
missing, the service does not start. Definition: the `ai` rows of
`docs/parametros.md`. Seed:

```shell
python -m tools.seeds.seed_service_parameters ai --yes
```

-----

## 🧪 Continuous Integration

`.github/workflows/python-package.yml`, on every push and pull request to `main`:
installs `requirements.txt`, runs `pylint --fail-under=10.0 .` **without** the
repository `.pylintrc`, and `pytest` **without `.env`**. Without `.env`, `tests/conftest.py` skips the tests that read configuration; the schema tests run.

-----

## 🗂️ Service Structure

```txt
ai/
├── controllers/
│   ├── __init__.py
│   └── ai.py
├── models/
│   ├── __init__.py
│   └── ai.py
├── routes/
│   ├── __init__.py
│   └── ai.py
├── schemas/
│   ├── __init__.py
│   ├── ai.py
│   └── health.py
├── services/
│   ├── __init__.py
│   ├── ai.py
│   ├── ai_utils.py
│   ├── api_exceptions.py
│   ├── bedrock_client.py
│   ├── crud.py
│   ├── db_connection.py
│   ├── environment.py
│   ├── exceptions.py
│   ├── logger_config.py
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

2.  **Configure the environment:** Create the `.env` file with `HOST`, `PORT`, `APP_ENV`, `SECRET_KEY`, `ALGORITHM`, `TARGET_TIMEZONE`, `ROOT_PATH`, `API_URL`, `REQUEST_TIMEOUT_SECONDS`, the tables `DYNAMODB_TABLE_NAME_AI_PROMPTS`, `DYNAMODB_TABLE_NAME_AI_EXPLANATIONS` and `DYNAMODB_TABLE_NAME_SERVICE_PARAMETERS`, and `BEDROCK_REGION` and `BEDROCK_ANTHROPIC_VERSION`.

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
