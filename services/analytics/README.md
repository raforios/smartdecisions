# Analytics Service

Microservicio backend del producto **SmartDecisions** (de BearSoft). Es el
motor diferenciador del SaaS: **Afinidad × Drop Size = Oportunidad Comercial
Real** (SMARTDECISIONS.md §2). Toma un dataset ya validado por el servicio
`ingest`, calcula reglas de asociación con un Apriori ligero propio (sin
dependencias pesadas), las pondera por el drop size esperado de cada producto
(en moneda cuando hay precios) y devuelve el **top N de oportunidades por
punto de venta**, rankeadas por impacto monetario.

## Stack

- Python 3.14 + FastAPI + Uvicorn
- AWS Lambda (handler `Mangum`) + API Gateway
- AWS DynamoDB (`boto3`) + AWS S3 (lectura directa del bucket de FILES)
- pandas + Apriori ligero propio (frequent itemsets + `association_rules`)
- Autenticación JWT delegada al servicio AUTH

## Estructura

```text
analytics/
├── assets/             # Recursos estáticos (placeholder).
├── controllers/        # Orquestación entre rutas y servicios.
├── models/             # TypedDict del item DynamoDB.
├── routes/             # Endpoints FastAPI.
├── schemas/            # Modelos Pydantic V2 (Opportunity, summary, responses).
├── scripts/            # CLI utilitarios.
├── services/           # Lógica de negocio + helpers compartidos.
│   ├── api_exceptions.py # Manejo centralizado (boilerplate).
│   ├── crud.py           # Operaciones genéricas (boilerplate).
│   ├── db_connection.py  # Conexión DynamoDB (boilerplate).
│   ├── environment.py    # Carga de env vars (boilerplate).
│   ├── exceptions.py     # Excepciones (boilerplate).
│   ├── logger_config.py  # Logger (boilerplate).
│   ├── security.py       # JWT validation (boilerplate).
│   ├── utils.py          # Decoradores y helpers (boilerplate).
│   ├── affinity_engine.py # Motor afinidad × drop size.
│   ├── analytics_runs.py  # Persistencia en t_analytics_runs.
│   └── dataset_loader.py  # Lee metadata desde t_ingest_datasets + descarga de S3.
├── tests/              # Tests con pytest.
├── .env                # Variables de entorno (no commit).
├── Dockerfile          # Build para Lambda.
├── deploy.config       # Variables de despliegue.
├── dynamodb.sh         # Provisión local de DynamoDB.
├── main.py             # Entrypoint FastAPI.
└── requirements.txt
```

## Tablas DynamoDB

| Tabla | Partition Key | Sort Key | Notas |
|---|---|---|---|
| `t_analytics_runs` | `dataset_id` (S) | `run_id` (S, UUIDv4) | El sort key permite múltiples runs por dataset (re-tuneo de umbrales sin perder historial). |

> Las fechas se calculan en `America/La_Paz` (`TARGET_TIMEZONE`).

Tablas leídas:
- `t_ingest_datasets` — el servicio `ingest` la mantiene; analytics solo hace
  `get_item` para resolver `file_s3_key`.

## Variables de entorno

| Variable | Obligatoria | Descripción |
|---|---|---|
| `HOST`, `PORT` | sí | Bind para Uvicorn. |
| `APP_ENV` | no | `development` / `staging` / `production`. |
| `ROOT_PATH` | no | Prefijo cuando corre detrás de API Gateway. |
| `SECRET_KEY`, `ALGORITHM` | sí | Validación del JWT emitido por AUTH. |
| `TARGET_TIMEZONE` | sí | Por defecto `America/La_Paz`. |
| `DYNAMODB_TABLE_NAME_ANALYTICS_RUNS` | sí | Default: `t_analytics_runs`. |
| `DYNAMODB_TABLE_NAME_INGEST_DATASETS` | sí | Default: `t_ingest_datasets`. Lectura cross-service. |
| `AWS_REGION` | sí | Región. |
| `FILES_BUCKET_NAME` | sí | Bucket S3 donde `ingest` deja los `.xlsx`/`.csv`. Analytics hace `get_object` directo. |
| `AFFINITY_MIN_SUPPORT` | no | Apriori support threshold (default `0.01`). |
| `AFFINITY_MIN_LIFT` | no | `association_rules` lift threshold (default `1.0`). |
| `AFFINITY_TOP_N_PER_PDV` | no | Máximo de oportunidades por PdV (default `10`). |
| `CORS_ALLOWED_ORIGINS` | no | Lista CSV de orígenes exactos adicionales (terceros). Vacío por defecto. |
| `CORS_ALLOWED_ORIGIN_REGEX` | no | Regex de orígenes permitidos. Default cubre `*.bearsoft.com.bo`, `*.cloudfront.net`, `*.mineria.gob.bo` y `localhost`. |

## Endpoints (todos requieren `Authorization: Bearer <jwt>`)

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/v1/analytics/run/{dataset_id}` | Ejecuta el pipeline sobre el dataset ingestado y persiste el resultado. |
| `GET` | `/v1/analytics/results/{dataset_id}` | Recupera el run más reciente (summary + opportunities). |
| `GET` | `/v1/analytics/results/{dataset_id}/pdv/{pdv_id}` | Filtra las oportunidades a un único punto de venta. |

Documentación interactiva: `GET /docs`.

## Output: `Opportunity`

Cada item devuelto representa una **acción comercial concreta** para un PdV:

```json
{
  "pdv_id": "PDV-007",
  "pdv_name": "Tienda Doña Rosa",
  "recommended_product_id": "SKU-B200",
  "recommended_product_name": "Yogurt Natural 1L",
  "based_on_products": ["SKU-A100"],
  "support": 0.18,
  "confidence": 0.62,
  "lift": 2.4,
  "expected_drop_size_units": 6.0,
  "expected_drop_size_amount": 90.0,
  "opportunity_score": 133.92,
  "rationale": "Quienes compran Galleta Integral 200g tienden a comprar Yogurt Natural 1L (lift 2.4). Drop size esperado en Tienda Doña Rosa: 6.0 unidades / $90.00."
}
```

`opportunity_score = lift × confidence × expected_drop_size_amount` (o
`_units` cuando no hay precios en el dataset). Es la métrica que ranquea
las oportunidades — alineada con el principio "output accionable en $"
de SMARTDECISIONS.md §10.

## Reglas de negocio relevantes

1. **No re-validamos el Excel**: confiamos en que `ingest` lo aceptó. El
   loader solo lo lee con `pd.read_excel` / `pd.read_csv`.
2. Solo se generan oportunidades para productos que el PdV **aún no compra**
   (los antecedentes deben ser subconjunto de su set actual, los consecuentes
   no pueden estar en él).
3. Cuando un mismo producto aparece como consecuente de varias reglas para
   el mismo PdV, conservamos la regla con el mayor `opportunity_score` y
   descartamos el resto.
4. `total_expected_value` del summary se devuelve solo cuando todas las
   oportunidades incluidas tienen precio; si parte del dataset no tiene
   `precio_unitario`, ranqueamos por unidades y omitimos el agregado en $.

## Ejecución local

```bash
# 1. Levantar DynamoDB local con la tabla requerida.
./dynamodb.sh

# 2. Completar .env (FILES_BUCKET_NAME apuntando a tu bucket real).

# 3. Instalar dependencias y arrancar la API.
pip install -r requirements.txt
python main.py
```

Tests:

```bash
PYTHONPATH=. pytest tests/ -v
```
