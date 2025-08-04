# 🐻 SMARTBEAR API 📈

Bienvenido a la arquitectura de microservicios **SMARTBEAR**, una plataforma robusta y escalable diseñada para el análisis de datos, Machine Learning y la toma de decisiones estratégicas. Esta API actúa como el backend de una aplicación de inteligencia de negocios, proporcionando funcionalidades avanzadas a través de un conjunto de microservicios especializados.

---

## 🎯 Propósito y Visión

**SMARTBEAR** es una solución de backend que habilita a empresas a transformar datos en conocimientos accionables. Su arquitectura de microservicios desacoplada asegura flexibilidad, escalabilidad y una gestión de fallos eficiente. El frontend de la plataforma será construido con **Streamlit**, interactuando con esta API para visualizar datos y resultados de los modelos de Machine Learning.

Los pilares de la plataforma son:

* **Análisis y Predicción:** Utilizar algoritmos de Machine Learning para predecir tendencias, clasificar datos y optimizar procesos.
* **Gestión de Datos:** Proporcionar una administración centralizada y segura de archivos y datos geográficos.
* **Seguridad:** Asegurar que todas las interacciones con los servicios estén autenticadas y autorizadas.

---

## 🏛️ Arquitectura de Microservicios

La API de **SMARTBEAR** se compone de los siguientes microservicios principales, cada uno con una responsabilidad clara y definida.

### 🔒 1. Auth-Handler-Service
El microservicio central de seguridad. Se encarga de la gestión de usuarios por compañía y la emisión de tokens JWT para la autenticación y autorización en toda la plataforma.
- **Tecnologías Clave:** Python 3.13, FastAPI, Docker, AWS Lambda, DynamoDB (para gestión de credenciales), JWT.

### 📁 2. File-Handler-Service
La interfaz principal para interactuar con **Amazon S3**. Permite la gestión programática de archivos para procesos de análisis, incluyendo la lectura, subida y eliminación de datos.
- **Tecnologías Clave:** Python 3.13, FastAPI, Docker, AWS Lambda, Amazon S3, Boto3.

### 🗺️ 3. Localization-Service
El motor de gestión de datos geográficos. Permite la creación de rutas planificadas, el registro de rutas ejecutadas en tiempo real, el control de asistencia por geolocalización y la generación de estadísticas comparativas.
- **Tecnologías Clave:** Python 3.13, FastAPI, Docker, AWS Lambda, MySQL (vía SQLAlchemy).

### 🧠 4. ML-Functions-Service
El motor de cómputo para tareas de Machine Learning. Proporciona endpoints REST para ejecutar algoritmos de regresión lineal, regresión logística y normalización de datos.
- **Tecnologías Clave:** Python 3.13, FastAPI, Docker, AWS Lambda, NumPy, Amazon S3 (para modelos y datos).

---

## 🛠️ Tecnologías Comunes

Todos los microservicios comparten un conjunto de tecnologías comunes que garantizan una arquitectura unificada y eficiente:

* **Lenguaje:** Python 3.13
* **Framework Web:** FastAPI
* **Contenedorización:** Docker
* **Plataforma Serverless:** AWS Lambda
* **Interacción con AWS:** Boto3
* **Seguridad:** JWT para autenticación
* **Despliegue:** Shell Script (`build_and_deploy.sh`)

---

## 🗂️ Estructura del Microservicio

```text
app/
└── frontend/
|   └── layout/
|   │   ├── __init__.py
|   │   ├── menu.py
|   │   └── utils.py
|   ├── pages/
|   │   ├── __init__.py
|   │   ├── content_generator.py
|   │   ├── dashboard.py
|   │   ├── load_file.py
|   │   ├── maps.py
|   │   └── optimization.py
|   ├── services/
|   │   ├── __init__.py
|   │   ├── load_data.py
|   │   └── rest.py
|   ├── utils/
|   │   ├── __init__.py
|   │   ├── create_office_files.py
|   │   ├── data.py
|   │   └── environmnet.py
|   ├── .env
|   ├── .gitignore
|   ├── main.py
|   ├── README.md
|   └── requirements.txt
├── notebooks/
|    └── lib/
|    │   ├── __init__.py
|    │   ├── data.py
|    │   ├── frontend_functions.py
|    │   ├── graph.py
|    │   ├── ml_functions.py
|    │   ├── models.py
|    │   └── rest.py
|    ├── .env
|    ├── .gitignore
|    ├── frontend.ipynb
|    ├── requirements.txt
|    └── routes.ipynb
├── services/
|    └── auth/
|    |  └── controllers/
|    |  │   ├── __init__.py
|    |  │   └── users.py
|    |  ├── routes/
|    |  │   ├── __init__.py
|    |  │   ├── auth.py
|    |  │   └── users.py
|    |  ├── schemas/
|    |  │   ├── __init__.py
|    |  │   ├── auth.py
|    |  │   ├── role.py
|    |  │   └── users.py
|    |  ├── services/
|    |  │   ├── __init__.py
|    |  │   ├── api_exceptions.py
|    |  │   ├── dynamodb.py
|    |  │   ├── exceptions.py
|    |  │   ├── jwt_token.py
|    |  │   ├── logger_config.py
|    |  │   └── security.py
|    |  ├── .dockerignore
|    |  ├── .env
|    |  ├── .gitignore
|    |  ├── deploy.config
|    |  ├── Dockerfile
|    |  ├── main.py
|    |  ├── README.md
|    |  └── requirements.txt
|    └── ci/
|    |  └── build_and_deply.sh
|    └── files/
|    |  └── controllers/
|    |  │   ├── __init__.py
|    |  │   └── files.py
|    |  ├── routes/
|    |  │   ├── __init__.py
|    |  │   └── files.py
|    |  ├── schemas/
|    |  │   ├── __init__.py
|    |  │   └── files.py
|    |  ├── services/
|    |  │   ├── __init__.py
|    |  │   ├── api_exceptions.py
|    |  │   ├── exceptions.py
|    |  │   ├── logger_config.py
|    |  │   └── security.py
|    |  ├── .dockerignore
|    |  ├── .env
|    |  ├── .gitignore
|    |  ├── deploy.config
|    |  ├── Dockerfile
|    |  ├── main.py
|    |  ├── README.md
|    |  └── requirements.txt
|    └── forms/
|    |  └── controllers/
|    |  │   ├── __init__.py
|    |  │   ├── forms.py
|    |  │   └── responses.py
|    |  ├── models/
|    |  │   ├── __init__.py
|    |  │   ├── forms.py
|    |  │   └── responses.py
|    |  ├── routes/
|    |  │   ├── __init__.py
|    |  │   ├── forms.py
|    |  │   └── responses.py
|    |  ├── schemas/
|    |  │   ├── __init__.py
|    |  │   ├── forms.py
|    |  │   └── responses.py
|    |  ├── services/
|    |  │   ├── __init__.py
|    |  │   ├── crud.py
|    |  │   ├── db_connection.py
|    |  │   ├── dynamodb.py
|    |  │   ├── exceptions.py
|    |  │   ├── logger_config.py
|    |  │   └── security.py
|    |  ├── .dockerignore
|    |  ├── .env
|    |  ├── .gitignore
|    |  ├── deploy.config
|    |  ├── Dockerfile
|    |  ├── dynamodb.sh
|    |  ├── main.py
|    |  ├── README.md
|    |  └── requirements.txt
|    └── localization/
|    |  └── controllers/
|    |  │   ├── init.py
|    |  │   └── localization.py
|    |  ├── models/
|    |  │   ├── init.py
|    |  │   └── localization.py
|    |  ├── routes/
|    |  │   ├── init.py
|    |  │   └── localization.py
|    |  ├── schemas/
|    |  │   ├── init.py
|    |  │   └── localization.py
|    |  ├── services/
|    |  │   ├── init.py
|    |  │   ├── api_exceptions.py
|    |  │   ├── crud.py
|    |  │   ├── db_connection.py
|    |  │   ├── exceptions.py
|    |  │   └── localization.py
|    |  │   ├── logger_config.py
|    |  │   └── security.py
|    |  ├── .dockerignore
|    |  ├── .env
|    |  ├── .gitignore
|    |  ├── deploy.config
|    |  ├── Dockerfile
|    |  ├── main.py
|    |  ├── README.md
|    |  └── requirements.txt
|    └── ml_functions/
|    |  └── controllers/
|    |  │   ├── __init__.py
|    |  │   ├── classification.py
|    |  │   ├── common.py
|    |  │   └── prediction.py
|    |  ├── routes/
|    |  │   ├── __init__.py
|    |  │   ├── classification.py
|    |  │   ├── common.py
|    |  │   └── prediction.py
|    |  ├── schemas/
|    |  │   ├── __init__.py
|    |  │   ├── classification.py
|    |  │   ├── common.py
|    |  │   └── prediction.py
|    |  ├── services/
|    |  │   ├── __init__.py
|    |  │   ├── api_exceptions.py
|    |  │   ├── exceptions.py
|    |  │   ├── logger_config.py
|    |  │   ├── machine_learning.py
|    |  │   └── security.py
|    |  ├── .dockerignore
|    |  ├── .env
|    |  ├── .gitignore
|    |  ├── deploy.config
|    |  ├── Dockerfile
|    |  ├── main.py
|    |  ├── README.md
|    |  └── requirements.txt
├── .gitignore
└── README.md

```
---

## 🚀 Despliegue y Ejecución

Cada microservicio puede ser desplegado de forma independiente en **AWS Lambda** utilizando los scripts de shell proporcionados. La configuración se gestiona a través de archivos `.env`.

**Ejemplo de despliegue manual:**

```shell
# Desplegar el microservicio de autenticación
./build_and_deploy.sh --path /ruta/al/proyecto/smartbear/services/auth


```

---

## 👤 Creado Por

**Rafael Ríos Bascón**
[raforios@gmail.com](mailto:raforios@gmail.com)


