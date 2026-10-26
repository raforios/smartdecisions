# 💬 AI-Interpretation-Service 🤖

Microservicio de **explicaciones con IA** de la plataforma de BearSoft. Convierte en palabras lo que una pantalla muestra como datos y códigos, desde el punto de vista del experto configurado para esa pantalla.

-----

## 🎯 Propósito Principal

El **AI-Interpretation-Service** explica lo que recibe, y nada más. Sus funcionalidades clave incluyen:

  * **Explicación de una Vista:** Recibe `{view, data}` —el JSON que devolvió el servicio que produjo la pantalla— y devuelve el texto, el rol usado y la versión.
  * **Roles por Vista:** Cada vista tiene versiones de su rol (contexto, misión, reglas, modelo y tokens) en `ai_prompts`; una sola activa por vista, y cada empresa puede tener la suya.
  * **Caché:** Una explicación se guarda y se reutiliza mientras la misma pantalla muestre los mismos datos.
  * **Recorte del Payload:** Una lista larga se recorta a una muestra para que una pantalla grande no sea una factura grande.
  * **Modelo:** Claude Haiku 4.5 por Amazon Bedrock (perfiles `us.`).

-----

## 🛠️ Tecnologías Utilizadas

  * **Lenguaje:** Python 3.14 🐍
  * **Framework Web:** FastAPI ✨
  * **Servidor ASGI:** Uvicorn 🚀
  * **Base de Datos:** AWS DynamoDB (`boto3`)
  * **IA:** Amazon Bedrock (`boto3`, `bedrock-runtime`)
  * **Validación de Datos:** Pydantic V2
  * **Plataforma Cloud:** AWS Lambda (`Mangum`) detrás de `api.bearsoft.com.bo`

-----

## 🚀 Endpoints de la API

A continuación se listan los **endpoints** de la API, agrupados por su funcionalidad. Todos exigen `Authorization: Bearer <jwt>` salvo que se indique otra cosa.

### Explicaciones (`/v1/ai`)

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/v1/ai/explain` | Explica lo que una **vista** está mostrando. |

### Roles (`/v1/ai/roles`)

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `GET` | `/v1/ai/roles` | Las versiones del **rol** de cada vista y cuál está activa. |
| `POST` | `/v1/ai/roles` | Guarda una versión del **rol** de una vista. |
| `GET` | `/v1/ai/roles/{view}/{version}` | Una versión completa del **rol**. |
| `PATCH` | `/v1/ai/roles/{view}/{version}/active` | Activa una versión (retira las otras de esa vista) o la apaga. |
| `DELETE` | `/v1/ai/roles/{view}/{version}` | Elimina una versión del **rol**. Sólo `ADMIN`. |

### Salud

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `GET` | `/` | Página de inicio del servicio. |
| `GET` | `/v1/ai/health` | Salud del servicio y validación de su configuración. |
| `GET` | `/v1/ai/health/tables` | Estado de las tablas DynamoDB del servicio. |

-----

## 🗄️ Datos que guarda

| Tabla | Partición | Orden | Qué guarda |
|---|---|---|---|
| `ai_prompts` | `view` | `version` | El rol de cada vista: `role`, `instructions`, `rules`, `model_id`, `max_tokens`, `active` y la empresa dueña |
| `ai_explanations` | `cache_key` | — | Las explicaciones generadas, para reutilizarlas |
| `ai_parameters` | `code` | — | Los valores de negocio del servicio |

Los fallos viajan como códigos: `EMPTY_PAYLOAD`, `ROLE_NOT_CONFIGURED`, `ROLE_NOT_FOUND`, `MODEL_UNAVAILABLE` y `MODEL_REFUSED`.

-----

## ⚙️ Valores de negocio

Los valores de negocio del servicio viven en la tabla `ai_parameters` (un ítem por
código), no en el `.env`. Los lee `load_parameters`, del bloque SERVICE
PARAMETERS al final de `services/utils.py`, una vez por contenedor; un valor
cambiado en la tabla lo toman los contenedores que arrancan después. Si falta
uno, el servicio no arranca. Definición: filas `ai` de
`docs/parametros.md`. Siembra:

```shell
python -m tools.seeds.seed_service_parameters ai --yes
```

-----

## 🧪 Integración Continua

`.github/workflows/python-package.yml`, en cada push y pull request a `main`:
instala `requirements.txt`, corre `pylint --fail-under=10.0 .` **sin** el
`.pylintrc` del repositorio y `pytest` **sin `.env`**. `tests/conftest.py` deja fuera sin `.env` los tests que leen configuración; corren los de los esquemas y sus reglas.

-----

## 🗂️ Estructura del Microservicio

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

## 📀 Ejecución Local

Para ejecutar el microservicio localmente, sigue los siguientes pasos:

1.  **Instala las dependencias:**

```shell
pip install -r requirements.txt
```

2.  **Configura el entorno:** Crea el archivo `.env` con `HOST`, `PORT`, `APP_ENV`, `SECRET_KEY`, `ALGORITHM`, `TARGET_TIMEZONE`, `ROOT_PATH`, `API_URL`, `REQUEST_TIMEOUT_SECONDS`, las tablas `DYNAMODB_TABLE_NAME_AI_PROMPTS`, `DYNAMODB_TABLE_NAME_AI_EXPLANATIONS` y `DYNAMODB_TABLE_NAME_SERVICE_PARAMETERS`, y `BEDROCK_REGION` y `BEDROCK_ANTHROPIC_VERSION`.

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
