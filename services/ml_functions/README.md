# ML_FUNCTIONS — ML-Functions-Service

Servicio **base** de BearSoft desde el 17-oct-2026 (CLAUDE.md §4).

## Para qué sirve

Es el **centro de cálculos y fórmulas**: predicciones, proyecciones,
clasificaciones. Un cálculo común vive aquí una sola vez y cada servicio lo
pide por HTTP, como pide autenticación a AUTH, en vez de guardar su copia de
la fórmula.

No guarda nada ni lee configuración de negocio: los parámetros de cada modelo
(por ejemplo `alpha`, `beta`, `phi` de la proyección) los manda quien llama,
que los lee de PARAMETERS. ML_FUNCTIONS no reporta a EVENTS: un cálculo no
dice nada del negocio (Rafael, 17-oct-2026).

## Endpoints y quién puede llamarlos

Todos son `POST` y exigen un token válido de AUTH, de cualquier rol.

**Proyección de series**

| Ruta | Qué hace |
|---|---|
| `/v1/prediction/forecast` | Proyecta una serie con tendencia amortiguada (Holt) y mide el modelo sobre la propia serie junto al error de «el próximo valor igual al último» |

**Regresión lineal**

| Ruta | Qué hace |
|---|---|
| `/v1/prediction/compute-cost` | Costo de la regresión lineal |
| `/v1/prediction/compute-gradient` | Gradiente de la regresión lineal |
| `/v1/prediction/train-linear-regression` | Entrena el modelo por gradiente descendente |
| `/v1/prediction/predict-linear-regression` | Predice con un modelo entrenado |

**Regresión logística**

| Ruta | Qué hace |
|---|---|
| `/v1/classification/sigmoid-batch` | Sigmoide de una lista de valores |
| `/v1/classification/cost-logistic` | Costo de la regresión logística |
| `/v1/classification/gradient-logistic` | Gradiente de la regresión logística |
| `/v1/classification/train-logistic-regression` | Entrena el modelo |
| `/v1/classification/predict-logistic-classification` | Clasifica (0 o 1) con un modelo entrenado |

**Comunes**

| Ruta | Qué hace |
|---|---|
| `/v1/common/normalize-features` | Normaliza por Z-score |

## Qué servicios lo llaman

- **FINANCE**: `/v1/prediction/forecast` para la proyección
  (`services/finance/services/projection.py`).
- ANALYTICS, MINING_ANALYSIS y QUOTES tienen todavía su propia copia de sus
  proyecciones; se pasan aquí después del Análisis Financiero.

## Variables de entorno

Sólo entorno (CLAUDE.md §5.3):

| Variable | Qué es |
|---|---|
| `HOST`, `PORT`, `APP_ENV` | Servidor local y entorno |
| `SECRET_KEY`, `ALGORITHM` | Verificación del JWT de AUTH |

## Tablas y buckets

Ninguno: sólo calcula.

## Cómo correrlo y probarlo

```bash
cd services/ml_functions
python main.py            # puerto del .env (PORT)
python -m pytest -q
pylint --fail-under=10.0 .
```

Se despliega con `services/ci/api/start.sh --redeploy ml_functions` (lo
despliega Rafael).

## Qué revisa el CI

`.github/workflows/python-package.yml`, en cada push y pull request a `main`:
instala `requirements.txt`, corre `pylint --fail-under=10.0 .` **sin** el
`.pylintrc` del repositorio y `pytest` **sin `.env`**. Por eso los tests
importan sólo esquemas y funciones puras: `tests/test_forecast.py` prueba
`services/forecast.py` (`damped_trend`, `backtest`) y `ForecastRequest`.
`tests/test_ml.py` prueba las regresiones con resultados conocidos: costo y
gradiente en la recta exacta, el descenso que recupera `y = 2x + 1` y un
plano de dos variables, Z-score, sigmoide y la clasificación logística.

## Creado por

**Rafael Ríos Bascón** — [raforios@gmail.com](mailto:raforios@gmail.com)
