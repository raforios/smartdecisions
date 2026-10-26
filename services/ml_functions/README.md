# 🧠 ML-Functions-Service 📐

Microservicio de **cálculos de Machine Learning y matemáticos** de la plataforma de BearSoft: predicciones, proyecciones, clasificaciones y rutas. No guarda nada: recibe un objeto completo con los datos del cálculo y devuelve el resultado en otro objeto.

-----

## 🎯 Propósito Principal

El **ML-Functions-Service** concentra las fórmulas en un solo lugar. Sus funcionalidades clave incluyen:

  * **Proyección de Series:** Diez modelos (`NAIVE`, `DAMPED_TREND`, `HOLT_WINTERS`, `LINEAR`, `MOVING_AVERAGE`, `MEAN`, `DRIFT`, `SIMPLE_EXPONENTIAL`, `HOLT`, `THETA`) con sus pesos ajustados a la serie y medidos fuera de muestra contra «el próximo valor igual al último».
  * **Comparación de Modelos:** Cada modelo proyecta desde cada punto con historia suficiente y se promedian sus errores.
  * **Clasificaciones:** Niveles por puesto en un ranking y reglas de asociación (Apriori) con soporte, confianza y lift.
  * **Rutas:** Grupos compactos de tamaño parejo (k-means equilibrado) y orden de visita (vecino más cercano y 2-opt sobre la esfera).
  * **Regresiones:** Lineal y logística por gradiente descendente, y normalización Z-score.

-----

## 🛠️ Tecnologías Utilizadas

  * **Lenguaje:** Python 3.14 🐍
  * **Framework Web:** FastAPI ✨
  * **Servidor ASGI:** Uvicorn 🚀
  * **Cálculo Numérico:** NumPy
  * **Validación de Datos:** Pydantic V2
  * **Plataforma Cloud:** AWS Lambda (`Mangum`) detrás de `api.bearsoft.com.bo`

-----

## 🚀 Endpoints de la API

A continuación se listan los **endpoints** de la API, agrupados por su funcionalidad. Todos exigen `Authorization: Bearer <jwt>` salvo que se indique otra cosa.

### Proyección (`/v1/prediction`)

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/v1/prediction/forecast` | Proyecta una **serie**. Sin `models` elige entre tendencia amortiguada y Holt-Winters; con uno lo usa tal cual; con varios compiten. |
| `POST` | `/v1/prediction/forecast/compare` | Corre varios **modelos** sobre la misma serie y los ordena por su error promedio. |
| `POST` | `/v1/prediction/compute-cost` | Costo de la **regresión lineal**. |
| `POST` | `/v1/prediction/compute-gradient` | Gradiente de la **regresión lineal**. |
| `POST` | `/v1/prediction/train-linear-regression` | Entrena la **regresión lineal** por gradiente descendente. |
| `POST` | `/v1/prediction/predict-linear-regression` | Predice con una **regresión lineal** entrenada. |

### Clasificación (`/v1/classification`)

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/v1/classification/tiers` | Reparte valores en **niveles** por su puesto en el ranking (cortes `[0.2, 0.5]`: el 20 % de arriba, el 30 % siguiente y el resto). |
| `POST` | `/v1/classification/association-rules` | **Reglas de asociación** (Apriori) de un conjunto de transacciones. |
| `POST` | `/v1/classification/sigmoid-batch` | **Sigmoide** de una lista de valores. |
| `POST` | `/v1/classification/cost-logistic` | Costo de la **regresión logística**. |
| `POST` | `/v1/classification/gradient-logistic` | Gradiente de la **regresión logística**. |
| `POST` | `/v1/classification/train-logistic-regression` | Entrena la **regresión logística**. |
| `POST` | `/v1/classification/predict-logistic-classification` | Clasifica (0 o 1) con una **regresión logística** entrenada. |

### Rutas (`/v1/routing`)

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/v1/routing/clusters` | Reparte **puntos** (lat, lon) en grupos compactos de tamaño parejo; la misma semilla da los mismos grupos. |
| `POST` | `/v1/routing/order` | Ordena **paradas** para un recorrido abierto que empieza en la primera. |

### Comunes (`/v1/common`)

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/v1/common/normalize-features` | Normaliza **características** por Z-score. |
| `GET` | `/` | Página de inicio del servicio. |
| `GET` | `/v1/common/health` | Salud del servicio y validación de su configuración. |

-----

## 🗄️ Datos que guarda

Ninguno: no tiene tablas ni buckets. No reporta a EVENTS.

-----

## 🧪 Integración Continua

`.github/workflows/python-package.yml`, en cada push y pull request a `main`:
instala `requirements.txt`, corre `pylint --fail-under=10.0 .` **sin** el
`.pylintrc` del repositorio y `pytest` **sin `.env`**. Todos sus tests son puros y corren en el CI: `tests/test_forecast.py`, `tests/test_classification.py`, `tests/test_routing.py`, `tests/test_ml.py` y `tests/test_controllers.py`.

-----

## 🗂️ Estructura del Microservicio

```txt
ml_functions/
├── controllers/
│   ├── __init__.py
│   ├── classification.py
│   ├── common.py
│   ├── prediction.py
│   └── routing.py
├── routes/
│   ├── __init__.py
│   ├── classification.py
│   ├── common.py
│   ├── prediction.py
│   └── routing.py
├── schemas/
│   ├── __init__.py
│   ├── base.py
│   ├── classification.py
│   ├── common.py
│   ├── prediction.py
│   └── routing.py
├── services/
│   ├── __init__.py
│   ├── api_exceptions.py
│   ├── classification.py
│   ├── environment.py
│   ├── exceptions.py
│   ├── forecast.py
│   ├── forecast_bench.py
│   ├── logger_config.py
│   ├── machine_learning.py
│   ├── routing.py
│   ├── security.py
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

## 📀 Ejecución Local

Para ejecutar el microservicio localmente, sigue los siguientes pasos:

1.  **Instala las dependencias:**

```shell
pip install -r requirements.txt
```

2.  **Configura el entorno:** Crea el archivo `.env` con `HOST`, `PORT`, `APP_ENV`, `SECRET_KEY`, `ALGORITHM`, `TARGET_TIMEZONE` y `ROOT_PATH`.

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
