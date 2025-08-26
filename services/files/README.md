# 📁 File-Handler-Service ☁️

Bienvenido al microservicio de administración de archivos, un componente clave para la interacción con **Amazon S3** dentro de la arquitectura de tu API **SMARTBEAR**. Este servicio facilita la gestión de archivos para procesos de análisis de datos, permitiendo leer, subir y eliminar contenido en tus buckets S3.

-----

## 🎯 Propósito Principal

El **File-Handler-Service** está diseñado para ser la interfaz principal para todas las operaciones de archivos en tus buckets S3 de AWS. Sus funcionalidades clave incluyen:

  * **Gestión de Archivos en S3:** Permite subir, leer, listar y eliminar archivos de forma programática.
  * **Preparación para Análisis de Datos:** Facilita la extracción de información desde archivos almacenados para su posterior procesamiento y análisis.
  * **Integración con la API SMARTBEAR:** Actúa como un puente seguro para que otros microservicios interactúen con S3.
  * **Generación de URLs Pre-firmadas:** Permite crear enlaces seguros y temporales para que los clientes finales puedan subir archivos directamente a S3 sin exponer credenciales.

-----

## 🛠️ Tecnologías Utilizadas

Este microservicio ha sido desarrollado con un enfoque en la eficiencia y la integración con la nube:

  * **Lenguaje:** Python 3.13 🐍 (Versión estable y soportada en AWS Lambda)
  * **Framework Web:** FastAPI ✨
  * **Servidor ASGI:** Uvicorn 🚀
  * **Autenticación/Autorización:** JWT (JSON Web Tokens) 🔑 (Para asegurar el acceso al microservicio)
  * **Contenedorización:** Docker 🐳 (para compilación de librerías, empaquetado y despliegue)
  * **Plataforma Cloud:** AWS Lambda ☁️ (como servicio de ejecución sin servidor)
  * **Almacenamiento de Objetos:** Amazon S3 🗄️ (Como sistema de almacenamiento principal para archivos)
  * **Interacción con AWS:** Boto3 (SDK oficial de AWS para Python para interactuar con S3 y otros servicios)

-----

## 🚀 Endpoints de la API

A continuación se listan los endpoints principales de la API, organizados por su funcionalidad.

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `GET` | `/v1/s3/read/{bucket_name}/{file_key}` | Lee y procesa un archivo (CSV, Excel, TXT) desde un bucket S3. |
| `POST` | `/v1/s3/upload` | Sube un archivo directamente al servicio para que este lo almacene en S3. |
| `DELETE` | `/v1/s3/delete` | Elimina un archivo específico de un bucket S3. |
| `POST` | `/v1/s3/list-files` | Lista los archivos en un bucket S3, con la opción de un prefijo. |
| `POST` | `/v1/s3/upload-presigned` | Genera una URL pre-firmada para subir archivos directamente a S3 desde el cliente. |

-----

## 📦 Dependencias

Las siguientes librerías son esenciales para el funcionamiento del **File-Handler-Service** y se gestionan a través de `requirements.txt` y Docker:

  * `fastapi`
  * `uvicorn`
  * `pydantic`
  * `pydantic-core`
  * `python-multipart`
  * `boto3`
  * `mangum`
  * `pandas`
  * `python-jose[cryptography]`
  * `openpyxl`
  * `python-dotenv`

-----

## 🚀 Despliegue manual en AWS

```shell
./build_and_deploy.sh --path /Users/rafael/Work/projects/back/SmartBear/app/services/files 

./build_and_deploy.sh --path /Users/rafael/Work/projects/back/SmartBear/app/services/files --destroy

./build_and_deploy.sh --path /Users/rafael/Work/projects/back/SmartBear/app/services/files --skip-code-update

./build_and_deploy.sh --path /Users/rafael/Work/projects/back/SmartBear/app/services/files --skip-table-creation 
```

-----

## 🗂️ Estructura del Microservicio

```text
files/
└── controllers/
│   ├── __init__.py
│   └── files.py
├── routes/
│   ├── __init__.py
│   └── files.py
├── schemas/
│   ├── __init__.py
│   └── files.py
├── services/
│   ├── __init__.py
│   ├── api_exceptions.py
│   ├── exceptions.py
│   ├── logger_config.py
│   ├── security.py
│   └── utils.py
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
