# Ingest Service

Microservicio backend del producto **SmartDecisions** (de BearSoft). Recibe el
Excel de ventas del usuario final, valida su estructura contra la plantilla
canónica (`template_ventas_v1.xlsx`), almacena el archivo crudo en S3 vía
FILES y persiste los metadatos del dataset en DynamoDB para que las capas de
análisis (afinidad × drop size, predicción, rutas) lo consuman después.

## Stack

- Python 3.14 + FastAPI + Uvicorn
- AWS Lambda (handler `Mangum`) + API Gateway
- AWS DynamoDB (`boto3`)
- pandas + pandera para la validación tabular
- Autenticación JWT delegada al servicio AUTH

## Estructura

```text
ingest/
├── controllers/        # Orquestación entre rutas y servicios.
├── models/             # TypedDict del item DynamoDB.
├── routes/             # Endpoints FastAPI.
├── schemas/            # Modelos Pydantic V2 (request / response).
├── services/           # ingest.py (dominio), ingest_utils.py (Dynamo/S3/FILES)
│                       # y los componentes del boilerplate.
├── tests/              # Tests con pytest.
├── .env.example        # Plantilla de variables de entorno.
├── Dockerfile          # Build para Lambda.
├── deploy.config       # Variables de despliegue.
├── dynamodb.sh         # Provisión local de DynamoDB.
├── main.py             # Entrypoint FastAPI.
└── requirements.txt
```

## Tablas DynamoDB

| Tabla | Partition Key | Sort Key | Notas |
|---|---|---|---|
| `t_ingest_datasets` | `dataset_id` (S, UUIDv4) | — | Un item por archivo ingestado. Guarda summary + lista de errores. |

> Las fechas se calculan en `America/La_Paz` (variable `TARGET_TIMEZONE`).

## Variables de entorno

| Variable | Obligatoria | Descripción |
|---|---|---|
| `HOST`, `PORT` | sí | Bind para Uvicorn. |
| `APP_ENV` | no | `development` / `staging` / `production`. |
| `ROOT_PATH` | no | Prefijo cuando corre detrás de API Gateway. |
| `SECRET_KEY`, `ALGORITHM` | sí | Validación del JWT emitido por AUTH. |
| `TARGET_TIMEZONE` | sí | Por defecto `America/La_Paz`. |
| `DYNAMODB_TABLE_NAME_INGEST_DATASETS` | sí | Tabla de metadatos. Default: `t_ingest_datasets`. |
| `AWS_REGION` | sí | Región de DynamoDB. |
| `FILES_SERVICE_URL` | sí | URL base del servicio FILES para subir el archivo a S3. |
| `AUTH_SERVICE_URL` | no | Para validaciones cruzadas (no usado aún). |
| `EVENTS_SERVICE_URL` | no | Para auditoría futura. |
| `CORS_ALLOWED_ORIGINS` | no | Lista CSV de orígenes exactos adicionales (terceros). Vacío por defecto. |
| `MAX_ISSUES_ON_RESPONSE` | no | Cuántos errores viajan en la respuesta JSON. Default: `100`. |
| `CSV_CONTENT_TYPE` | no | MIME de los CSV que escribe el servicio. Default: `text/csv`. |
| `TEMPLATE_S3_KEY` | no | Key de la plantilla en el bucket. Default: `ingest/templates/template_ventas_v1.xlsx`. |
| `CORS_ALLOWED_ORIGIN_REGEX` | no | Regex de orígenes permitidos. Default cubre `*.bearsoft.com.bo`, `*.cloudfront.net`, `*.mineria.gob.bo` y `localhost`. |

## Endpoints (todos requieren `Authorization: Bearer <jwt>`)

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/v1/ingest/template` | Metadata de la plantilla: versión, columnas obligatorias y opcionales, URL de descarga. |
| `GET` | `/v1/ingest/template/file` | Descarga directa de `template_ventas_v1.xlsx`. |
| `POST` | `/v1/ingest/excel` | Sube y valida un archivo `.xlsx` o `.csv`. Si pasa, lo guarda en S3 vía FILES y devuelve el `dataset_id`. |
| `GET` | `/v1/ingest/{dataset_id}` | Estado del dataset previamente ingestado. |

Documentación interactiva: `GET /docs` (Swagger UI).

## Contrato de la plantilla v1

| Columna | Tipo | Obligatoria | Notas |
|---|---|---|---|
| `id_pedido` | texto/int | sí | Agrupa productos de una misma venta/visita. |
| `fecha` | fecha | sí | ISO `aaaa-mm-dd` o `dd/mm/aaaa`. |
| `id_punto_venta` | texto/int | sí | Identificador del PdV / cliente. |
| `id_producto` | texto/int | sí | SKU. |
| `cantidad` | número | sí | Unidades. Debe ser > 0. |
| `nombre_pdv` | texto | no | Solo UI. |
| `zona` | texto | no | Análisis de rutas / regional. |
| `nombre_producto` | texto | no | Solo UI. |
| `precio_unitario` | número | no | Necesario para Drop Size en moneda. |
| `monto_total` | número | no | Si falta, se calcula `cantidad × precio_unitario`. |

Reglas de validación (`pandera.DataFrameSchema`):
- `cantidad > 0`.
- `precio_unitario >= 0` y `monto_total >= 0`.
- Textos no vacíos y ≤ 64 caracteres en los campos clave.
- Fechas parseables a `datetime64[ns]`.

Errores: respuesta con `status: 'failed'` + lista `errors[]` indicando `row`,
`column`, `value`, `rule` y mensaje en español apto para usuario no técnico.

## Contrato de columnas

`schemas/ingest.py` → `SALES_COLUMNS` es la **única** definición del formato:
nombre canónico, encabezado de la plantilla, si es obligatoria y sus reglas de
valor. De ahí se derivan el mapeo de encabezados, el schema de pandera y las
listas de obligatorias/opcionales. **No hay ningún otro lugar donde se declaren
columnas**; agregar una es agregar una línea ahí.

## Textos y configuración

1. **El backend no devuelve texto.** Responde datos y códigos (`ValidationRule`,
   `IngestError`); los interpreta el frontend o la capa de IA. El archivo de
   filas rechazadas lleva una columna `rule_codes`, no frases.
2. **Nada de valores mágicos.** Lo configurable se lee del entorno con
   `load_and_validate_env_vars` del boilerplate, en el módulo que lo usa.

## Reglas de negocio relevantes

1. La política de almacenamiento (S3) la dicta FILES; este servicio nunca
   habla a S3 directo.
2. Solo se sube a S3 si el archivo pasa la validación (`status='validated'`).
   Los rechazados se persisten en Dynamo con la lista de errores para que el
   usuario pueda revisarlos sin re-subir.
3. `monto_total` se deriva automáticamente cuando hay `cantidad` y
   `precio_unitario` pero falta el total.
4. La plantilla `.xlsx` es un **archivo estático** guardado en el bucket por
   defecto (`TEMPLATE_S3_KEY`). El servicio no la genera: el formato está
   definido y lo cumple el cliente. Si el formato cambia, cambian también la
   lógica y las reglas de negocio, y el archivo se repone en el bucket.

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

La plantilla `.xlsx` es un archivo estático en el bucket (`TEMPLATE_S3_KEY`);
el servicio no la genera.

Tests:

```bash
PYTHONPATH=. pytest tests/ -v
```
