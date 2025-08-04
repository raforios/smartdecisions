# 📁 File-Handler-Service ☁️

Bienvenido al microservicio de administración de archivos, un componente clave para la interacción con **Amazon S3** dentro de la arquitectura de tu API **SMARTBEAR**. Este servicio facilita la gestión de archivos para procesos de análisis de datos, permitiendo leer, subir y eliminar contenido en tus buckets S3.

---

## 🎯 Propósito Principal

El **File-Handler-Service** está diseñado para ser la interfaz principal para todas las operaciones de archivos en tus buckets S3 de AWS. Sus funcionalidades clave incluyen:

* **Gestión de Archivos en S3:** Permite subir, leer y eliminar archivos de forma programática.
* **Preparación para Análisis de Datos:** Facilita la extracción de información desde archivos almacenados para su posterior procesamiento y análisis.
* **Integración con la API SMARTBEAR:** Actúa como un puente seguro para que otros microservicios interactúen con S3.

---

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

---

## 🚀 ¿Cómo se Usa?

El **File-Handler-Service** interactúa con S3 basándose en los parámetros proporcionados. Este servicio requiere autenticación (a través de un token JWT generado por el Auth-Handler-Service) para todas sus operaciones.

Las solicitudes al servicio deben incluir:

* **Nombre del Bucket S3:** El nombre del bucket donde se encuentra o se gestionará el archivo.
* **Ruta Completa del Archivo:** Incluyendo subcarpetas si las hay (ej., `carpeta1/subcarpeta/nombre_archivo.csv`).
* **Nombre del Archivo:** El nombre específico del archivo a procesar.

Las operaciones principales que este servicio puede realizar son:

* **Lectura de Archivos:** Extraer el contenido de un archivo específico para su procesamiento.
* **Subida de Archivos:** Cargar nuevos archivos al bucket S3 en una ruta definida.
* **Eliminación de Archivos:** Borrar archivos existentes del bucket S3.

```python
# Ejemplo conceptual de uso (no es código ejecutable)

# Suponiendo que ya tienes un 'auth_token' del Auth-Handler-Service
# headers = {"Authorization": f"Bearer {auth_token}"}

# Para leer un archivo:
# payload_read = {
#     "bucket_name": "mi-bucket-smartbear",
#     "file_path": "data/raw_data/",
#     "file_name": "sales.csv"
# }
# response_read = requests.post("URL_FILE_SERVICE/read", json=payload_read, headers=headers)
# print(response_read.json())

# Para subir un archivo:
# payload_upload = {
#     "bucket_name": "mi-bucket-smartbear",
#     "file_path": "data/processed_data/",
#     "file_name": "cleaned_sales.csv",
#     "file_content": "base64_encoded_content_here" # O manejarlo como un archivo multipart
# }
# response_upload = requests.post("URL_FILE_SERVICE/upload", json=payload_upload, headers=headers)

# Para eliminar un archivo:
# payload_delete = {
#     "bucket_name": "mi-bucket-smartbear",
#     "file_path": "temp/",
#     "file_name": "old_report.txt"
# }
# response_delete = requests.delete("URL_FILE_SERVICE/delete", json=payload_delete, headers=headers)
```
---

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

---

## 🚀 Despliegue manual en AWS 

```shell
./build_and_deploy.sh --path /Users/rafael/Work/projects/back/SmartBear/app/services/files 

./build_and_deploy.sh --path /Users/rafael/Work/projects/back/SmartBear/app/services/files --destroy

./build_and_deploy.sh --path /Users/rafael/Work/projects/back/SmartBear/app/services/files --skip-code-update

./build_and_deploy.sh --path /Users/rafael/Work/projects/back/SmartBear/app/services/files --skip-table-creation 
```
---

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
---

## 👤 Creado Por

**Rafael Ríos Bascón**
[raforios@gmail.com](mailto:raforios@gmail.com)

