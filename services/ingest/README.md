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

## Datos que guarda

### Tablas DynamoDB

Se crean con `services/ci/api/create_dynamodb_tables.sh`. El dueño es el
`client` del JWT (o el correo si no lo tiene) y es parte de cada consulta.

| Tabla | Partición | Orden | Qué guarda |
|---|---|---|---|
| `ingest_datasets` | `id` (UUID; igual a `dataset_id`) | — | Un ítem por archivo de ventas: dueño, estado, resumen y punteros a sus archivos en S3 |
| `ingest_clients` | `owner_email` | `id` (código del cliente) | Maestro de clientes (`models/clients.py`) |
| `ingest_sellers` | `owner_email` | `id` (el vendedor como lo escribe el archivo) | Maestro de vendedores y su usuario (`models/sellers.py`) |

**`ingest_datasets`**, atributos del ítem:

| Atributo | Qué es |
|---|---|
| `id`, `dataset_id` | Identificador del conjunto de datos |
| `owner_email` | Dueño |
| `status` | `validated` o `failed` |
| `template_version`, `created_at` | Origen de la carga |
| `total_rows`, `valid_rows`, `error_rows`, `unique_points_of_sale`, `unique_products`, `date_range_start`, `date_range_end`, `errors` | Resumen de la validación de ventas |
| `file_s3_key` | Ventas aceptadas, normalizadas |
| `rejected_s3_key` | Filas apartadas, para descargar y corregir |
| `<contrato>_s3_key`, `<contrato>_summary`, `<contrato>_issues` | Por cada archivo enganchado: `collections`, `stock`, `visits`, `objectives` |

Modelo: `models/ingest.py` (`IngestDataset`).

**`ingest_clients`**: `name`, `tax_id`, `client_type`, `channel`, `zone`,
`city`, `region`, `address`, `latitude`, `longitude`, `phone`, `contact`,
`seller`, `credit_limit`, `cluster`, `supervisor`, `market`, `source`
(`FILE`, `API` o `FIELD`), `created_at`, `updated_at`.

**`ingest_sellers`**: `name`, `user_email` (el usuario con que ingresa al
sistema), `source`, `created_at`, `updated_at`.

### Archivos en S3 (por FILES)

Bucket de FILES, prefijo `ingest/`. Cada archivo es un CSV con los **campos**
de su contrato (columna "Campo"), no con las cabeceras en castellano. La fuente
de verdad es `schemas/ingest.py`; estas tablas salen de ahí.

### Ventas — `ingest/normalized/<uuid>.csv`

| Cabecera (plantilla) | Campo | Tipo | Obligatoria | Regla |
|---|---|---|---|---|
| Fecha | `date` | fecha | sí |  |
| Nro Factura | `order_id` | texto | sí | hasta 64 car. |
| Cliente ID | `pos_id` | texto | sí (la deriva el servicio) | hasta 64 car. |
| Cliente | `pos_name` | texto | no |  |
| Zona | `zone` | texto | no |  |
| Ciudad | `city` | texto | no |  |
| Region | `region` | texto | no |  |
| Canal | `channel` | texto | no |  |
| Vendedor | `seller` | texto | no |  |
| Latitud | `latitude` | número | no | entre -90 y 90 |
| Longitud | `longitude` | número | no | entre -180 y 180 |
| Producto ID | `product_id` | texto | sí (la deriva el servicio) | hasta 64 car. |
| Producto | `product_name` | texto | no |  |
| Categoria | `category` | texto | no |  |
| Cantidad | `quantity` | número | sí | > 0 |
| Precio Unitario | `unit_price` | número | no | ≥ 0 |
| Costo Unitario | `unit_cost` | número | no | ≥ 0 |
| Monto Total | `total_amount` | número | no | ≥ 0 |
| Condicion Venta | `payment_terms` | texto | no | hasta 16 car.; uno de: CONTADO, CREDITO |
| Plazo Dias | `credit_days` | entero | no | ≥ 0 |
| Fecha Vencimiento | `due_date` | fecha | no |  |
| Responsable Cobro | `collector` | texto | no |  |
| Limite Credito | `credit_limit` | número | no | ≥ 0 |

### Cobros — `ingest/collections/<uuid>.csv`

| Cabecera (plantilla) | Campo | Tipo | Obligatoria | Regla |
|---|---|---|---|---|
| Nro Factura | `order_id` | texto | sí | hasta 64 car. |
| Fecha Cobro | `payment_date` | fecha | sí |  |
| Monto Cobrado | `paid_amount` | número | sí | > 0 |
| Medio | `payment_method` | texto | no | hasta 32 car. |
| Responsable Cobro | `collector` | texto | no |  |

### Stock — `ingest/stock/<uuid>.csv`

| Cabecera (plantilla) | Campo | Tipo | Obligatoria | Regla |
|---|---|---|---|---|
| Fecha | `snapshot_date` | fecha | sí |  |
| Producto ID | `product_id` | texto | sí (la deriva el servicio) | hasta 64 car. |
| Producto | `product_name` | texto | no |  |
| Existencia | `on_hand` | número | sí | ≥ 0 |
| Comprometido | `committed` | número | no | ≥ 0 |
| En Transito | `in_transit` | número | no | ≥ 0 |
| Almacen | `warehouse` | texto | no | hasta 64 car. |
| Costo Unitario | `unit_cost` | número | no | ≥ 0 |

### Visitas — `ingest/visits/<uuid>.csv`

| Cabecera (plantilla) | Campo | Tipo | Obligatoria | Regla |
|---|---|---|---|---|
| Fecha | `visit_date` | fecha | sí |  |
| Hora | `visit_time` | texto | no | hasta 8 car. |
| Vendedor | `seller` | texto | sí | hasta 128 car. |
| Cliente ID | `pos_id` | texto | sí (la deriva el servicio) | hasta 64 car. |
| Cliente | `pos_name` | texto | no |  |
| Latitud | `latitude` | número | no | entre -90 y 90 |
| Longitud | `longitude` | número | no | entre -180 y 180 |
| Resultado | `outcome` | texto | no | hasta 16 car.; uno de: VENTA, SIN_VENTA, CERRADO, NO_ENCONTRADO |
| Nro Factura | `order_id` | texto | no | hasta 64 car. |

### Objetivos — `ingest/objectives/<uuid>.csv`

| Cabecera (plantilla) | Campo | Tipo | Obligatoria | Regla |
|---|---|---|---|---|
| Cliente ID | `pos_id` | texto | sí (la deriva el servicio) | hasta 64 car. |
| Cliente | `pos_name` | texto | sí |  |
| Periodo | `period` | texto | sí | hasta 7 car. |
| Objetivo | `target_amount` | número | sí | ≥ 0 |

### Clientes — carga del maestro (va a `ingest_clients`, no a S3)

| Cabecera (plantilla) | Campo | Tipo | Obligatoria | Regla |
|---|---|---|---|---|
| Cliente ID | `id` | texto | sí | hasta 64 car. |
| Cliente | `name` | texto | sí | hasta 150 car. |
| NIT | `tax_id` | texto | no | hasta 40 car. |
| Tipo Negocio | `client_type` | texto | no | hasta 64 car. |
| Canal | `channel` | texto | no | hasta 64 car. |
| Zona | `zone` | texto | no | hasta 100 car. |
| Ciudad | `city` | texto | no | hasta 100 car. |
| Region | `region` | texto | no | hasta 100 car. |
| Direccion | `address` | texto | no | hasta 255 car. |
| Latitud | `latitude` | número | no | entre -90 y 90 |
| Longitud | `longitude` | número | no | entre -180 y 180 |
| Telefono | `phone` | texto | no | hasta 40 car. |
| Contacto | `contact` | texto | no | hasta 150 car. |
| Vendedor | `seller` | texto | no | hasta 128 car. |
| Limite Credito | `credit_limit` | número | no | ≥ 0 |
| Cluster | `cluster` | texto | no | hasta 40 car. |
| Supervisor | `supervisor` | texto | no | hasta 128 car. |
| Mercado | `market` | texto | no | hasta 100 car. |

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
