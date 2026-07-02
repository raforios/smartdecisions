# Optimization Service

Microservicio backend del producto **SmartDecisions** (de BearSoft). Toma los
puntos de clientes georreferenciados de una ruta (`route_id`, `day`) desde
DynamoDB, calcula distancias geodésicas, ejecuta la heurística de ruta óptima
y proyecta el resultado sobre la red vial real usando la **API de OSRM** vía
HTTP (sin librerías geoespaciales pesadas). **Reemplaza** los endpoints
`/api/v1/optimization/*` del monolito legado (`api/routes/optimization.py`).

## Stack

- Python 3.14 + FastAPI + Uvicorn
- AWS Lambda (handler `Mangum`) + API Gateway
- AWS DynamoDB (`boto3`)
- `requests` + API de OSRM para la proyección sobre la red vial real
- `geopy` para distancias geodésicas
- Autenticación JWT delegada al servicio AUTH

## Estructura

```text
optimization/
├── assets/             # Recursos estáticos (placeholder).
├── controllers/        # Orquestación entre rutas y servicios.
├── models/             # TypedDict del item DynamoDB.
├── routes/             # Endpoints FastAPI.
├── schemas/            # Modelos Pydantic V2 (request / response / query).
├── scripts/            # CLI utilitarios (seed CSV → Dynamo).
├── services/           # Lógica de negocio + helpers compartidos.
│   ├── api_exceptions.py # Manejo centralizado de errores (boilerplate).
│   ├── crud.py           # Operaciones genéricas de BD (boilerplate).
│   ├── db_connection.py  # Conexión DynamoDB (boilerplate).
│   ├── environment.py    # Carga de variables de entorno (boilerplate).
│   ├── exceptions.py     # Excepciones del dominio (boilerplate).
│   ├── logger_config.py  # Configuración del logger (boilerplate).
│   ├── security.py       # Validación de tokens JWT (boilerplate).
│   ├── utils.py          # Decoradores y helpers (boilerplate).
│   ├── ml_optimization.py # Algoritmo (port verbatim del monolito).
│   ├── routing.py        # Proyección sobre la red vial vía OSRM (requests).
│   └── route_data.py     # Acceso a t_optimization_routes en Dynamo.
├── tests/              # Tests con pytest.
├── .env.example        # Plantilla de variables de entorno.
├── Dockerfile          # Build para Lambda (paquete liviano, sin geo-libs).
├── deploy.config       # Variables de despliegue.
├── dynamodb.sh         # Provisión local de DynamoDB.
├── main.py             # Entrypoint FastAPI.
└── requirements.txt
```

## Tablas DynamoDB

| Tabla | Partition Key | Sort Key | Notas |
|---|---|---|---|
| `t_optimization_routes` | `route_day_key` (S, formato `"{route_id}#{day}"`) | `client_id` (N) | Reemplaza `routes` (Postgres del monolito). Una sola Query trae todos los puntos de una (ruta, día). |

> Las fechas se calculan en `America/La_Paz` (variable `TARGET_TIMEZONE`).

## Variables de entorno

| Variable | Obligatoria | Descripción |
|---|---|---|
| `HOST`, `PORT` | sí | Bind para Uvicorn. |
| `APP_ENV` | no | `development` / `staging` / `production`. |
| `ROOT_PATH` | no | Prefijo cuando corre detrás de API Gateway. |
| `SECRET_KEY`, `ALGORITHM` | sí | Validación del JWT emitido por AUTH. |
| `TARGET_TIMEZONE` | sí | Por defecto `America/La_Paz`. |
| `DYNAMODB_TABLE_NAME_OPTIMIZATION_ROUTES` | sí | Default: `t_optimization_routes`. |
| `AWS_REGION` | sí | Región de DynamoDB. |
| `OSRM_BASE_URL` | no | Base de la API OSRM. Default: `https://router.project-osrm.org`. |
| `CORS_ALLOWED_ORIGINS` | no | Lista CSV de orígenes exactos adicionales (terceros). Vacío por defecto. |
| `CORS_ALLOWED_ORIGIN_REGEX` | no | Regex de orígenes permitidos. Default cubre `*.bearsoft.com.bo`, `*.cloudfront.net`, `*.mineria.gob.bo` y `localhost`. |

## Endpoints (todos requieren `Authorization: Bearer <jwt>`)

Mismo contrato del monolito legado; solo cambia el prefijo
(`/v1/optimization/*` en lugar de `/api/v1/optimization/*`).

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/v1/optimization/data_model?route_id&day` | Puntos georreferenciados con colores de inicio/medio/fin. |
| `GET` | `/v1/optimization/distances?route_id&day` | Pares ordenados (origin, target, distance). |
| `GET` | `/v1/optimization/optimal_route?route_id&day&dist` | Ruta optimizada proyectada sobre la red vial real (OSRM). |
| `GET` | `/v1/optimization/distance_matrix?route_id&day` | Matriz de distancias geodésicas entre todos los puntos. |
| `GET` | `/v1/optimization/route?route_id&day&dist` | Alias de `/optimal_route` (compatibilidad con el notebook). |

Documentación interactiva: `GET /docs`.

## Reglas de negocio relevantes

1. Los datos de entrada (lat, lon por cliente) se leen una sola vez de Dynamo
   con `services.route_data.get_route_points` y se transforman al DataFrame
   que consume el algoritmo.
2. El orden de visita y las distancias geodésicas son **idénticos** al
   monolito legado; lo que cambia es la proyección vial: ahora cada segmento
   se resuelve contra OSRM y `RouteResponse.route` es la polilínea de calles
   (`[longitud, latitud]`) más `road_distance` (m) y `road_duration` (s).
3. OSRM se consulta por HTTP en runtime (`OSRM_BASE_URL`). El servidor público
   `router.project-osrm.org` tiene rate-limits; en producción evaluar
   levantar una instancia propia de OSRM y apuntar `OSRM_BASE_URL` a ella.

## Ejecución local

```bash
# 1. Levantar DynamoDB local con la tabla requerida.
./dynamodb.sh

# 2. Copiar variables de entorno y completarlas.
cp .env.example .env

# 3. Instalar dependencias y arrancar la API.
pip install -r requirements.txt
python main.py
```

Tests:

```bash
PYTHONPATH=. pytest tests/ -v
```

## Notas de migración

- Datos: el monolito leía `SELECT * FROM routes WHERE route_id = X AND day = Y`
  en Postgres. Acá la misma información vive en `t_optimization_routes` en
  Dynamo bajo la PK compuesta `route_day_key = "{route_id}#{day}"`. Para
  bootstrappear localmente, puede usarse un seed CSV → Dynamo (ver
  `scripts/` cuando se materialice).
- Prefijo de URL: monolito `/api/v1/optimization/*` → microservicio
  `/v1/optimization/*`. Los helpers del notebook (`lib/frontend_functions.py`)
  ya arman ese path.
