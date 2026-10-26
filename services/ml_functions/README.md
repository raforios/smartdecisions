# 🧠 ML-Functions-Service 📐

The **Machine Learning and math calculations** service of the BearSoft platform: predictions, projections, classifications and routes. It stores nothing: it receives a complete object with the data of the calculation and returns the result in another object.

-----

## 🎯 Main Purpose

The **ML-Functions-Service** keeps every formula in one place. Its key features:

  * **Series Projection:** Ten models (`NAIVE`, `DAMPED_TREND`, `HOLT_WINTERS`, `LINEAR`, `MOVING_AVERAGE`, `MEAN`, `DRIFT`, `SIMPLE_EXPONENTIAL`, `HOLT`, `THETA`), their weights fitted to the series and measured out of sample against "the next value equals the last one".
  * **Model Comparison:** Each model projects from every point with enough history, and its errors are averaged.
  * **Classifications:** Tiers by rank and association rules (Apriori) with support, confidence and lift.
  * **Routes:** Compact groups of even size (balanced k-means) and visit order (nearest neighbour plus 2-opt on the sphere).
  * **Regressions:** Linear and logistic regression by gradient descent, and Z-score normalization.

-----

## 🛠️ Technologies

  * **Language:** Python 3.14 🐍
  * **Web Framework:** FastAPI ✨
  * **ASGI Server:** Uvicorn 🚀
  * **Numerical Computing:** NumPy
  * **Data Validation:** Pydantic V2
  * **Cloud Platform:** AWS Lambda (`Mangum`) behind `api.bearsoft.com.bo`

-----

## 🚀 API Endpoints

The API **endpoints**, grouped by feature. All of them require `Authorization: Bearer <jwt>` unless stated otherwise.

### Prediction (`/v1/prediction`)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/v1/prediction/forecast` | Projects a **series**. Without `models` it chooses between the damped trend and Holt-Winters; with one it uses it as asked; with several they compete. |
| `POST` | `/v1/prediction/forecast/compare` | Runs several **models** on the same series and ranks them by their mean error. |
| `POST` | `/v1/prediction/compute-cost` | **Linear regression** cost. |
| `POST` | `/v1/prediction/compute-gradient` | **Linear regression** gradient. |
| `POST` | `/v1/prediction/train-linear-regression` | Trains a **linear regression** by gradient descent. |
| `POST` | `/v1/prediction/predict-linear-regression` | Predicts with a trained **linear regression**. |

### Classification (`/v1/classification`)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/v1/classification/tiers` | Splits values into **tiers** by rank (cuts `[0.2, 0.5]`: the top 20 %, the next 30 % and the rest). |
| `POST` | `/v1/classification/association-rules` | **Association rules** (Apriori) of a set of transactions. |
| `POST` | `/v1/classification/sigmoid-batch` | **Sigmoid** of a list of values. |
| `POST` | `/v1/classification/cost-logistic` | **Logistic regression** cost. |
| `POST` | `/v1/classification/gradient-logistic` | **Logistic regression** gradient. |
| `POST` | `/v1/classification/train-logistic-regression` | Trains a **logistic regression**. |
| `POST` | `/v1/classification/predict-logistic-classification` | Classifies (0 or 1) with a trained **logistic regression**. |

### Routing (`/v1/routing`)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/v1/routing/clusters` | Splits **points** (lat, lon) into compact groups of even size; the same seed gives the same groups. |
| `POST` | `/v1/routing/order` | Orders **stops** for an open path starting at the first one. |

### Common (`/v1/common`)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/v1/common/normalize-features` | Normalizes **features** by Z-score. |
| `GET` | `/` | Service home page. |
| `GET` | `/v1/common/health` | Service health and configuration check. |

-----

## 🗄️ Stored Data

None: no tables, no buckets. It does not report to EVENTS.

-----

## 🧪 Continuous Integration

`.github/workflows/python-package.yml`, on every push and pull request to `main`:
installs `requirements.txt`, runs `pylint --fail-under=10.0 .` **without** the
repository `.pylintrc`, and `pytest` **without `.env`**. All its tests are pure and run in CI: `tests/test_forecast.py`, `tests/test_classification.py`, `tests/test_routing.py`, `tests/test_ml.py` and `tests/test_controllers.py`.

-----

## 🗂️ Service Structure

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

## 📀 Local Setup

To run the service locally:

1.  **Install the dependencies:**

```shell
pip install -r requirements.txt
```

2.  **Configure the environment:** Create the `.env` file with `HOST`, `PORT`, `APP_ENV`, `SECRET_KEY`, `ALGORITHM`, `TARGET_TIMEZONE` and `ROOT_PATH`.

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
