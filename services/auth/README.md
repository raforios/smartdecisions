# 🔒 Auth-Handler-Service 🔑

The **authentication and authorization** service of the BearSoft platform. It manages the users of every company and issues the JWT that authenticates every request to the other services.

-----

## 🎯 Main Purpose

The **Auth-Handler-Service** is the source of truth for users, companies and roles. Its key features:

  * **Sign-in:** Checks e-mail and password and issues a JWT carrying `email`, `role` and `client` (the company); records the last sign-in, the previous one and the count.
  * **User Management:** Sign-up (`ADMIN` only), lookup, role and company changes, removal, and changing one's own password.
  * **Company Management:** Creating, changing the tax id or status of, and removing the companies users belong to.
  * **Roles:** Defined in `schemas/role.py`; SmartDecisions uses `ADMIN`, `MANAGER` and `SELLER`, and a new sign-up starts as `REQUESTER`.
  * **Passwords:** Hashed with plain `bcrypt` (`$2b$`), compatible with the older `passlib` hashes.

-----

## 🛠️ Technologies

  * **Language:** Python 3.14 🐍
  * **Web Framework:** FastAPI ✨
  * **ASGI Server:** Uvicorn 🚀
  * **Database:** AWS DynamoDB (`boto3`)
  * **Security:** JWT (`python-jose`) and `bcrypt`
  * **Data Validation:** Pydantic V2
  * **Cloud Platform:** AWS Lambda (`Mangum`) behind `api.bearsoft.com.bo`

-----

## 🚀 API Endpoints

The API **endpoints**, grouped by feature. All of them require `Authorization: Bearer <jwt>` unless stated otherwise.

### Authentication (`/v1/auth`)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/v1/auth/login` | Takes e-mail and password and returns the **JWT**. No token required. |
| `POST` | `/v1/auth/signup` | Creates a **user** as `REQUESTER` with no company. `ADMIN` only. |

### Companies (`/v1/auth/companies`)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/v1/auth/companies` | Every **company**, with how many users it has. `ADMIN` only. |
| `POST` | `/v1/auth/companies` | Adds a **company**. `ADMIN` only. |
| `PATCH` | `/v1/auth/companies/{name}` | Changes a **company**'s tax id or status. `ADMIN` only. |
| `DELETE` | `/v1/auth/companies/{name}` | Removes a **company** with no users. `ADMIN` only. |

### Users (`/v1/users`)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/v1/users/` | Every **user**. `ADMIN` only. |
| `GET` | `/v1/users/me` | The signed-in **user**, with their last and previous sign-in. |
| `GET` | `/v1/users/company` | The **users** of the caller's company. `MANAGER` or `ADMIN`. |
| `POST` | `/v1/users/me/password` | Changes one's own **password**; the current one is required. |
| `GET` | `/v1/users/{email}` | One **user** by e-mail. `ADMIN` only. |
| `PATCH` | `/v1/users/{email}` | Updates a **user**'s name, role, company or status. `ADMIN` only. |
| `DELETE` | `/v1/users/{email}` | Removes a **user**. `ADMIN` only. |

### Health

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Service home page. |
| `GET` | `/v1/auth/health` | Service health and configuration check. |
| `GET` | `/v1/auth/health/tables` | State of the service's DynamoDB tables. |

-----

## 🗄️ Stored Data

| Table | Partition key | What it holds |
|---|---|---|
| `auth-users` | `email` | `first_name`, `last_name`, `hashed_password`, `client`, `role`, `status`, `date_register` and the sign-ins |
| `auth-companies` | `name` | `tax_id`, `active`, `created_at`, `updated_at` |

**The first administrator** is created by writing the item straight into `auth-users`, with the hash from `services/security.py`; from then on, an `ADMIN` signs the others up and promotes them with `PATCH /v1/users/{email}`.

-----

## 🧪 Continuous Integration

`.github/workflows/python-package.yml`, on every push and pull request to `main`:
installs `requirements.txt`, runs `pylint --fail-under=10.0 .` **without** the
repository `.pylintrc`, and `pytest` **without `.env`**. `tests/test_auth.py` imports only schemas and pure functions, so it runs in CI; `tests/test_routes.py` reads configuration and `tests/conftest.py` skips it without `.env`.

-----

## 🗂️ Service Structure

```txt
auth/
├── controllers/
│   ├── __init__.py
│   ├── companies.py
│   └── users.py
├── routes/
│   ├── __init__.py
│   ├── auth.py
│   ├── companies.py
│   └── users.py
├── schemas/
│   ├── __init__.py
│   ├── auth.py
│   ├── companies.py
│   ├── health.py
│   ├── role.py
│   └── users.py
├── services/
│   ├── __init__.py
│   ├── api_exceptions.py
│   ├── companies.py
│   ├── dynamodb.py
│   ├── environment.py
│   ├── exceptions.py
│   ├── jwt_token.py
│   ├── logger_config.py
│   ├── security.py
│   ├── sessions.py
│   └── utils.py
├── tests/
├── .dockerignore
├── .env
├── .gitignore
├── deploy.config
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

2.  **Configure the environment:** Create the `.env` file with `HOST`, `PORT`, `APP_ENV`, `SECRET_KEY`, `ALGORITHM`, `TARGET_TIMEZONE`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `ROOT_PATH` and the tables `TABLE_NAME` and `TABLE_NAME_COMPANIES`.

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
