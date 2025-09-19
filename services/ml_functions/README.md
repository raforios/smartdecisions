# 🧠 ML-Functions-Service 📈

Bienvenido al microservicio de Machine Learning, un componente fundamental para las operaciones de análisis y predicción dentro de la arquitectura de la API **SMARTBEAR**. Este servicio encapsula algoritmos de aprendizaje automático para ser consumidos fácilmente a través de endpoints REST, facilitando tareas de predicción, clasificación y normalización de datos.

-----

## 🎯 Propósito Principal

El **ML-Functions-Service** está diseñado para ser un motor de cómputo para tareas de Machine Learning. Su propósito es exponer algoritmos de forma segura y escalable, permitiendo a otros servicios de la plataforma realizar análisis complejos sin tener que gestionar la lógica de los modelos internamente. Sus funcionalidades clave incluyen:

  * **Regresión Lineal:** Para entrenar modelos y predecir valores continuos.
  * **Regresión Logística:** Para entrenar modelos y clasificar datos en categorías binarias (0 o 1).
  * **Gradiente Descendente:** El algoritmo de optimización utilizado para encontrar los parámetros óptimos (pesos `w` y sesgo `b`) de los modelos de regresión.
  * **Normalización de Características:** Ofrece funciones comunes como la normalización por **Z-score** para preprocesar los datos de entrada.

-----

## 🛠️ Tecnologías Utilizadas

Este microservicio ha sido desarrollado con un enfoque en la eficiencia y el rendimiento de los cálculos numéricos:

  * **Lenguaje:** Python 3.13 🐍
  * **Framework Web:** FastAPI ✨
  * **Servidor ASGI:** Uvicorn 🚀
  * **Cómputo Numérico:** NumPy (para operaciones matriciales eficientes)
  * **Contenedorización:** Docker 🐳 (para compilación de librerías, empaquetado y despliegue)
  * **Plataforma Cloud:** AWS Lambda ☁️
  * **Autenticación/Autorización:** JWT (JSON Web Tokens) 🔑 (El servicio valida tokens para asegurar los endpoints)

-----

## 🚀 Endpoints de la API

A continuación se listan los endpoints principales de la API, organizados por su funcionalidad.

### Funciones de Predicción (Regresión Lineal)

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/v1/prediction/compute-cost` | Calcula el costo para regresión lineal. |
| `POST` | `/v1/prediction/compute-gradient` | Calcula el gradiente para regresión lineal. |
| `POST` | `/v1/prediction/train-linear-regression` | Entrena un modelo de regresión lineal. |
| `POST` | `/v1/prediction/predict-linear-regression` | Realiza una predicción con un modelo de regresión lineal entrenado. |

### Funciones de Clasificación (Regresión Logística)

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/v1/classification/sigmoid-batch` | Calcula la función sigmoide para una lista de valores. |
| `POST` | `/v1/classification/cost-logistic` | Calcula el costo para regresión logística. |
| `POST` | `/v1/classification/gradient-logistic` | Calcula el gradiente para regresión logística. |
| `POST` | `/v1/classification/train-logistic-regression` | Entrena un modelo de regresión logística. |
| `POST` | `/v1/classification/predict-logistic-classification`| Realiza una clasificación (0 o 1) con un modelo entrenado. |

### Funciones Comunes

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/v1/common/normalize-features` | Normaliza un conjunto de datos usando Z-score. |

-----

## 📦 Dependencias

Las siguientes librerías son esenciales para el funcionamiento del **ML-Functions-Service** y se gestionan a través de `requirements.txt` y Docker:

  * `fastapi`
  * `uvicorn`
  * `pydantic`
  * `pydantic-core`
  * `python-multipart`
  * `mangum`
  * `pandas`
  * `python-jose[cryptography]`
  * `numpy`
  * `python-dotenv`

-----

## 🚀 Despliegue manual en AWS

```shell
./build_and_deploy.sh --path /Users/rafael/Work/projects/back/SmartBear/app/services/ml_functions 

./build_and_deploy.sh --path /Users/rafael/Work/projects/back/SmartBear/app/services/ml_functions --destroy

./build_and_deploy.sh --path /Users/rafael/Work/projects/back/SmartBear/app/services/ml_functions --skip-table-creation

./build_and_deploy.sh --path /Users/rafael/Work/projects/back/SmartBear/app/services/ml_functions --skip-code-update

./build_and_deploy.sh --path /Users/rafael/Work/projects/back/SmartBear/app/services/ml_functions --enable-sqs

```
-----

## 🗂️ Estructura del Microservicio

```text
ml_functions/
└── controllers/
│   ├── __init__.py
│   ├── classification.py
│   ├── common.py
│   └── prediction.py
├── routes/
│   ├── __init__.py
│   ├── classification.py
│   ├── common.py
│   └── prediction.py
├── schemas/
│   ├── __init__.py
│   ├── classification.py
│   ├── common.py
│   └── prediction.py
├── services/
│   ├── __init__.py
│   ├── api_exceptions.py
│   ├── exceptions.py
│   ├── logger_config.py
│   ├── machine_learning.py
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
