# 📜 Events-Service 📊

The **audit and usage-log** service of the BearSoft platform. It records who changed what, and every call the services receive.

-----

## 🎯 Main Purpose

The **Events-Service** is the memory of what happens on the platform. Its key features:

  * **Audit Trail:** Records every data change with the service, entity, action, user, and the values before and after.
  * **Usage Log:** Records every request with its endpoint, method, status code, response time and trimmed bodies.
  * **Paginated Queries:** Filters by service, entity, user and dates, 1 to 100 records per page.
  * **Activity:** Recent activity of the services for the `ADMIN`, and each user's latest changes.

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

The API **endpoints**, grouped by feature. All of them require `Authorization: Bearer <jwt>` unless stated otherwise.

### Audit (`/v1/events/audit`)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/v1/events/audit` | Creates an **audit record**. Any valid token. |
| `GET` | `/v1/events/audit` | Lists **audit records** with filters and pagination. `ADMIN` only. |

### Usage Log (`/v1/events/usage-log`)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/v1/events/usage-log` | Creates a **usage log**. Any valid token. |
| `GET` | `/v1/events/usage-log` | Lists **usage logs** with filters and pagination. `ADMIN` only. |

### Activity

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/v1/events/activity` | Recent activity of the given services. `ADMIN` only. |
| `GET` | `/v1/events/my-changes` | The signed-in user's latest **changes**. |

### Health

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Service home page. |
| `GET` | `/v1/events/health` | Service health and configuration check. |
| `GET` | `/v1/events/health/tables` | State of the service's DynamoDB tables. |

-----

## 🗄️ Stored Data

| Table | Partition key | What it holds |
|---|---|---|
| `audit_records` | `id` (UUID) | `microservice`, `entity_name`, `entity_id`, `action`, `user_id`, `timestamp`, `old_values`, `new_values` (`models/audit.py`) |
| `usage_logs` | `id` (UUID) | `user_app`, `microservice`, `endpoint`, `method`, `status_code`, `ip_address`, `request_body`, `response_body`, `response_time_ms`, `timestamp` (`models/usage_log.py`) |

-----

## 🧪 Continuous Integration

`.github/workflows/python-package.yml`, on every push and pull request to `main`:
installs `requirements.txt`, runs `pylint --fail-under=10.0 .` **without** the
repository `.pylintrc`, and `pytest` **without `.env`**. `tests/test_events.py` tests the body trimming (`services/payload_limits.py`) and the schemas.

-----

## 🗂️ Service Structure

```txt
events/
├── controllers/
│   ├── __init__.py
│   ├── activity.py
│   ├── audit.py
│   └── usage_log.py
├── models/
│   ├── __init__.py
│   ├── audit.py
│   └── usage_log.py
├── routes/
│   ├── __init__.py
│   ├── activity.py
│   ├── audit.py
│   └── usage_log.py
├── schemas/
│   ├── __init__.py
│   ├── activity.py
│   ├── audit.py
│   ├── health.py
│   └── usage_log.py
├── services/
│   ├── __init__.py
│   ├── activity.py
│   ├── activity_summary.py
│   ├── api_exceptions.py
│   ├── audit.py
│   ├── crud.py
│   ├── db_connection.py
│   ├── environment.py
│   ├── exceptions.py
│   ├── logger_config.py
│   ├── payload_limits.py
│   ├── security.py
│   ├── usage_log.py
│   └── utils.py
├── tests/
├── .dockerignore
├── .env
├── .gitignore
├── deploy.config
├── dynamodb.sh
├── favicon.ico
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

2.  **Configure the environment:** Create the `.env` file with `HOST`, `PORT`, `APP_ENV`, `SECRET_KEY`, `ALGORITHM`, `TARGET_TIMEZONE`, `ROOT_PATH` and the tables `DYNAMODB_TABLE_NAME_AUDIT` and `DYNAMODB_TABLE_NAME_USAGE`.

3.  **Start the API server:**

```shell
python main.py
```

4.  **Run the tests:**

```shell
python -m pytest -q
pylint --fail-under=10.0 .
```

To work against a local DynamoDB, `dynamodb.sh` starts it in Docker (port 3100) with both tables; then export `AWS_ENDPOINT_URL_DYNAMODB=http://localhost:3100`.

-----

## 👤 Created By

**Rafael Ríos Bascón**
[raforios@gmail.com](mailto:raforios@gmail.com)
