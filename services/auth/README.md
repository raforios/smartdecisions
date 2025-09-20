# 🐻 Auth-Handler-Service 🔒

Bienvenido al microservicio de autenticación, una pieza fundamental para la seguridad de la API **SMARTBEAR**, un conjunto de microservicios diseñados para Machine Learning. Este servicio garantiza que solo los usuarios autorizados tengan acceso a las funcionalidades de la API.

---

## 🎯 Propósito Principal

El **Auth-Handler-Service** actúa como el punto de control de acceso central para toda la API SMARTBEAR. Su objetivo principal es:

* **Proveer seguridad robusta:** Asegurando que solo las solicitudes válidas y autenticadas accedan a los demás microservicios.
* **Gestión de Usuarios por Compañía:** Permite registrar, activar e inactivar usuarios, administrándolos por cada compañía que utilice el servicio SMARTBEAR.
* **Emisión de Tokens JWT:** Genera tokens JWT (JSON Web Tokens) que son esenciales para la autenticación y autorización en toda la API.

---

## 🛠️ Tecnologías Utilizadas

Este microservicio ha sido desarrollado utilizando un stack moderno y eficiente para garantizar escalabilidad y rendimiento:

* **Lenguaje:** Python 3.13 🐍 (Versión estable y soportada en AWS Lambda)
* **Framework Web:** FastAPI ✨
* **Servidor ASGI:** Uvicorn 🚀
* **Autenticación/Autorización:** JWT (JSON Web Tokens) 🔑
* **Contenedorización:** Docker 🐳 (para compilación de librerías, empaquetado y despliegue)
* **Plataforma Cloud:** AWS Lambda ☁️ (como servicio de ejecución sin servidor)
* **Gestión de Credenciales/Seguridad:** Passlib, Bcrypt, Python-jose[cryptography]
* **Correo Electrónico:** Email-validator (para validación de formatos de email en el registro)
* **Interacción con AWS:** Boto3 (SDK oficial de AWS para Python)

---

## 🗺️ API Endpoints

The **Auth-Handler-Service** exposes the following programmatic API endpoints for authentication and user management.

| Method | Path | Description | Authentication |
| :--- | :--- | :--- | :--- |
| `POST` | `/v1/auth/login` | Authenticates a user and returns an access JWT token. | `None` |
| `POST` | `/v1/auth/signup` | Registers a new user and returns their email and a confirmation message. | `None` |
| `GET` | `/v1/users/` | Retrieves a list of all users. | `JWT Token` |
| `GET` | `/v1/users/{email}` | Retrieves a single user's details by their email address. | `JWT Token` |
| `PATCH` | `/v1/users/{email}` | Updates a user's information by their email address. | `JWT Token` |
| `DELETE` | `/v1/users/{email}` | Deletes a user by their email address. | `JWT Token` |

---

## 🚀 ¿Cómo se Usa?

El **Auth-Handler-Service** no expone una interfaz pública directa para el usuario final. Su función es interna y programática:

1.  **Administración Interna:** Se utiliza para la gestión de usuarios (registro, activación, inactivación) por parte de los administradores del sistema o a través de herramientas internas.
2.  **Generación de Tokens:** Los microservicios clientes o las aplicaciones que necesitan interactuar con la API SMARTBEAR deben primero solicitar un TOKEN JWT a este microservicio de autenticación.
3.  **Autorización de Invocaciones:** Una vez obtenido el TOKEN JWT, este debe ser incluido en las cabeceras de cada solicitud a cualquier otro microservicio de la API SMARTBEAR. El token es validado por los microservicios receptores para permitir o denegar el acceso.

```python
# Ejemplo conceptual de cómo un cliente obtendría y usaría el token (no es código ejecutable)

# Paso 1: Obtener el token de autenticación
# response = requests.post("URL_AUTH_SERVICE/login", json={"username": "...", "password": "..."})
# auth_token = response.json()["access_token"]

# Paso 2: Usar el token en las solicitudes a otros microservicios SMARTBEAR
# headers = {"Authorization": f"Bearer {auth_token}"}
# ml_response = requests.get("URL_ML_SERVICE/predict", headers=headers)

```
-----

## 📦 Dependencias

Las siguientes librerías son esenciales para el funcionamiento del **Auth-Handler-Service** y se gestionan a través de `requirements.txt` y Docker:

  * `fastapi`
  * `uvicorn`
  * `pydantic`
  * `pydantic-core`
  * `python-multipart`
  * `boto3`
  * `mangum`
  * `pandas`
  * `passlib==1.7.4`
  * `bcrypt==4.0.1`
  * **`python-jose`**
  * `email-validator`
  * `python-dotenv`

-----

## 🚀 Despliegue manual en AWS

```shell
./build_and_deploy.sh --path /Users/rafael/Work/projects/back/SmartBear/app/services/auth 

./build_and_deploy.sh --path /Users/rafael/Work/projects/back/SmartBear/app/services/auth --destroy

./build_and_deploy.sh --path /Users/rafael/Work/projects/back/SmartBear/app/services/auth --skip-code-update

./build_and_deploy.sh --path /Users/rafael/Work/projects/back/SmartBear/app/services/auth --skip-table-creation 
```
-----

## 🗂️ Estructura del Microservicio

```text
auth/
└── controllers/
│   ├── __init__.py
│   └── users.py
├── routes/
│   ├── __init__.py
│   ├── auth.py
│   └── users.py
├── schemas/
│   ├── __init__.py
│   ├── auth.py
│   ├── role.py
│   └── users.py
├── services/
│   ├── __init__.py
│   ├── api_exceptions.py
│   ├── dynamodb.py
│   ├── environment.py
│   ├── exceptions.py
│   ├── jwt_token.py
│   ├── logger_config.py
│   └── security.py
├── .dockerignore
├── .env
├── .gitignore
├── deploy.config
├── Dockerfile
├── main.py
├── README.md
└── requirements.txt
```
-----

## 👤 Creado Por

**Rafael Ríos Bascón**
[raforios@gmail.com](mailto:raforios@gmail.com)

-----
