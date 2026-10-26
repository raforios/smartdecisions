# Commercial Service

Microservicio backend del producto **SmartDecisions** (de BearSoft): el
**módulo comercial**. Recibe lo que una empresa vende, cobra, compra, tiene en
stock y recorre en la calle —por archivo o por API desde su ERP—, guarda el
maestro de clientes y vendedores, y responde los análisis comerciales y las
rutas.

Une desde el 23-oct-2026 lo que eran INGEST (cargas y maestros), ANALYTICS
(análisis) y OPTIMIZATION (rutas): un solo microservicio con varias partes,
como FINANCE. El plan y la historia viven en
`docs/cambios/smartdecisions/plan.md` (fase 10).

## Reglas que lo gobiernan

- **El dueño es parte de cada consulta.** Es el `client` del JWT (o el correo
  si no lo tiene) y está en la clave de cada tabla: un recurso ajeno responde
  igual que uno inexistente.
- **Dos canales de entrada, los dos obligatorios:** el archivo que el cliente
  llena (sube por FILES a S3 y el servicio lo lee por su clave) y el API que
  consume su ERP. Mismo contrato, mismo validador, mismos códigos.
- **El cliente se describe una sola vez,** en el maestro (`commercial_clients`).
  Una recarga completa los campos vacíos; nunca reescribe una corrección.
- **Devuelve datos y códigos, nunca texto de cara al usuario.** El portal
  traduce cada código.
- **Todo monto viaja en bolivianos, dólar oficial y USDT** (las cotizaciones
  las pide a QUOTES): lo pasado al tipo de su día, lo de hoy al de hoy.
- **Los cálculos generales los pide a ML_FUNCTIONS** con el token del que
  llama (`services/calculations.py`): la proyección de ventas, los niveles de
  la segmentación, las reglas de afinidad (Apriori), el reparto en días y el
  orden de las paradas. Se quedan aquí la serie, las canastas, las paradas y
  cómo se muestra la respuesta. Las calles las da OSRM.
- **Los archivos los toca FILES** (bloque estándar de `services/utils.py`).
  Única lectura directa: la descarga de la plantilla estática.

## Stack

- Python 3.14 + FastAPI + Uvicorn; AWS Lambda (`Mangum`) detrás de
  `api.bearsoft.com.bo/v1/commercial`
- AWS DynamoDB (`boto3`); pandas para leer y validar los archivos
- AUTH (JWT), EVENTS (uso y auditoría), FILES (archivos), QUOTES
  (cotizaciones), ML_FUNCTIONS (cálculos) y OSRM (calles)

## Estructura

Cinco capas; en cada una el archivo principal es `commercial.py` (las cargas) y
los complementos se nombran por lo que hacen: `analytics.py` y sus motores
(`receivables.py`, `stock.py`, `portfolio.py`, `affinity.py`,
`segmentation.py`, `forecast.py`…), `localization*.py` (planes y recorridos),
`optimization.py` (plan desde las ventas), `clients.py`, `sellers.py`,
`daily_stock.py` (stock del día en ruta) y `calculations.py` (lo que se pide a
ML_FUNCTIONS).

## Endpoints

Todos bajo `/v1/commercial` y con `Authorization: Bearer <jwt>`. La
documentación interactiva está en `/v1/commercial/docs`.

| Parte | Endpoints |
|---|---|
| **Cargas por archivo** | `GET /template`, `GET /template/file/{contract}`, `POST /excel`, `POST /excel-from-s3`, `POST /{dataset_id}/{collections,stock,visits,objectives,purchases}`, `GET /datasets`, `GET /{dataset_id}`, `GET /{dataset_id}/rejected`, `GET /{dataset_id}/stock` |
| **Cargas por API (ERP)** | `POST /sales/rows`, `POST /{dataset_id}/sales/rows`, `POST /{dataset_id}/{collections,stock,visits,objectives,purchases}/rows`, y `/from-s3` de cada una |
| **Maestros** | `GET · POST /clients`, `POST /clients/field` (alta en la calle), `GET · PATCH /clients/{client_id}`, `GET /sellers`, `PATCH /sellers/{seller_id}` |
| **Análisis** | `GET /summary`, `/forecast`, `/segmentation`, `/receivables`, `/objectives`, `/stock`, `/portfolio`, `/fx-effect`, `/purchases`, `/stock-history`, `/dashboard`, `/clients/overview` y `/client/{dataset_id}/{client_id}`, todos con `/{dataset_id}` |
| **Oportunidades** | `POST /run/{dataset_id}`, `GET /runs`, `GET /results/{dataset_id}`, `GET /results/{dataset_id}/pdv/{pdv_id}` |
| **Políticas de la empresa** | `GET · PUT /commercial-policy`, `GET · PUT /credit-policy` |
| **Rutas planificadas** | `/routes/planned` (crear, listar, filtrar, importar CSV, inferir del día trabajado), `/routes/planned/{id}` (ver, editar, estado, borrar, paradas), `/routes/planned/{id}/optimization` y `/repeat` |
| **Rutas recorridas** | `/routes/executed` (iniciar, listar, reportar puntos, última posición, cerrar, reabrir) |
| **Comparación y estadísticas** | `GET /routes/comparison/{id}`, `/statistics/route-comparisons/{id}`, `/statistics/sellers/{seller}/points-visited`, `/statistics/day/{day}` |
| **Plan desde las ventas** | `GET /plan/{dataset_id}`, `POST /plan/{dataset_id}/by-seller` |
| **Stock del día en ruta** | `PUT /stock/day`, `POST /stock/day/from-ingest`, `GET /stock/day/{day}` |
| **Ajustes de rutas** | `GET · PUT /settings` (punto de partida y llegada) |
| **Salud** | `GET /health` |

## Datos que guarda

### Tablas DynamoDB

Se crean con `services/ci/api/create_dynamodb_tables.sh`.

| Tabla | Partición | Orden | Qué guarda |
|---|---|---|---|
| `commercial_datasets` | `id` | — | Una carga de ventas: dueño, estado, resumen y punteros a sus archivos en S3 (los de cobros, stock, visitas, objetivos y compras enganchados) |
| `commercial_clients` | `owner_email` | `id` | Maestro de clientes |
| `commercial_sellers` | `owner_email` | `id` | Maestro de vendedores y el usuario con que ingresan |
| `commercial_analytics_runs` | `id` | — | Las corridas de oportunidades |
| `commercial_policies` | `owner_email` | — | Política comercial de la empresa (semáforo de objetivos, bolivianos por punto, parte del costo en dólares) |
| `commercial_credit_policies` | `owner_email` | — | Política de crédito de la empresa (tramos, pérdidas, tasa, plazo) |
| `commercial_planned_routes` | `owner_email` | `id` | Planes de ruta con sus paradas |
| `commercial_executed_routes` | `owner_email` | `id` | Recorridos reales con cada punto reportado |
| `commercial_daily_stock` | `owner_email` | `stock_key` | Stock con que abre el día y lo vendido en ruta |
| `commercial_route_settings` | `owner_email` | — | Punto de partida y llegada de las rutas |
| `commercial_parameters` | `code` | — | Los valores de negocio del servicio (ver abajo) |

### Archivos en S3 (por FILES)

Bucket de FILES, prefijo `commercial/` (`BUCKET_PATH`). Cada archivo es un CSV
con los **campos** de su contrato, no con las cabeceras en castellano. El
contrato es `schemas/commercial.py`: de ahí salen el validador, las plantillas
(`tools/templates/`) y estas tablas. Las filas apartadas van a
`commercial/rejected/` con su código de motivo.

### Ventas — `commercial/normalized/<uuid>.csv`

| Cabecera (plantilla) | Campo | Tipo | Obligatoria | Regla |
|---|---|---|---|---|
| Fecha | `date` | fecha | sí |  |
| Nro Factura | `order_id` | texto | sí | hasta 64 car. |
| Cliente ID | `pos_id` | texto | la deriva el servicio | hasta 64 car. |
| Cliente | `pos_name` | texto | sí |  |
| Zona | `zone` | texto | no |  |
| Ciudad | `city` | texto | no |  |
| Region | `region` | texto | no |  |
| Canal | `channel` | texto | no |  |
| Vendedor | `seller` | texto | no |  |
| Latitud | `latitude` | número | no | entre -90 y 90 |
| Longitud | `longitude` | número | no | entre -180 y 180 |
| Producto ID | `product_id` | texto | la deriva el servicio | hasta 64 car. |
| Producto | `product_name` | texto | sí |  |
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

### Cobros — `commercial/collections/<uuid>.csv`

| Cabecera (plantilla) | Campo | Tipo | Obligatoria | Regla |
|---|---|---|---|---|
| Nro Factura | `order_id` | texto | sí | hasta 64 car. |
| Fecha Cobro | `payment_date` | fecha | sí |  |
| Monto Cobrado | `paid_amount` | número | sí | > 0 |
| Medio | `payment_method` | texto | no | hasta 32 car. |
| Responsable Cobro | `collector` | texto | no |  |

### Stock — `commercial/stock/<uuid>.csv`

| Cabecera (plantilla) | Campo | Tipo | Obligatoria | Regla |
|---|---|---|---|---|
| Fecha | `snapshot_date` | fecha | sí |  |
| Producto ID | `product_id` | texto | la deriva el servicio | hasta 64 car. |
| Producto | `product_name` | texto | sí |  |
| Existencia | `on_hand` | número | sí | ≥ 0 |
| Comprometido | `committed` | número | no | ≥ 0 |
| En Transito | `in_transit` | número | no | ≥ 0 |
| Almacen | `warehouse` | texto | no | hasta 64 car. |
| Costo Unitario | `unit_cost` | número | no | ≥ 0 |
| Precio de Venta | `unit_price` | número | sí | ≥ 0 |

### Compras — `commercial/purchases/<uuid>.csv`

| Cabecera (plantilla) | Campo | Tipo | Obligatoria | Regla |
|---|---|---|---|---|
| Fecha | `purchase_date` | fecha | sí |  |
| Proveedor | `supplier` | texto | sí | hasta 128 car. |
| Producto ID | `product_id` | texto | la deriva el servicio | hasta 64 car. |
| Producto | `product_name` | texto | sí |  |
| Cantidad | `quantity` | número | sí | > 0 |
| Costo Unitario | `unit_cost` | número | sí | ≥ 0 |
| Moneda | `currency` | texto | sí | uno de: BOB, USD, USDT |

### Visitas — `commercial/visits/<uuid>.csv`

| Cabecera (plantilla) | Campo | Tipo | Obligatoria | Regla |
|---|---|---|---|---|
| Fecha | `visit_date` | fecha | sí |  |
| Hora | `visit_time` | texto | no | hasta 8 car. |
| Vendedor | `seller` | texto | sí | hasta 128 car. |
| Cliente ID | `pos_id` | texto | la deriva el servicio | hasta 64 car. |
| Cliente | `pos_name` | texto | sí |  |
| Latitud | `latitude` | número | no | entre -90 y 90 |
| Longitud | `longitude` | número | no | entre -180 y 180 |
| Resultado | `outcome` | texto | no | hasta 16 car.; uno de: VENTA, SIN_VENTA, CERRADO, NO_ENCONTRADO |
| Nro Factura | `order_id` | texto | no | hasta 64 car. |

### Objetivos — `commercial/objectives/<uuid>.csv`

| Cabecera (plantilla) | Campo | Tipo | Obligatoria | Regla |
|---|---|---|---|---|
| Cliente ID | `pos_id` | texto | la deriva el servicio | hasta 64 car. |
| Cliente | `pos_name` | texto | sí |  |
| Periodo | `period` | texto | sí | hasta 7 car. |
| Objetivo | `target_amount` | número | sí | ≥ 0 |

### Clientes — maestro (va a `commercial_clients`, no a S3)

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

## Valores de negocio

Los 86 valores que el servicio usa —umbrales, ventanas, topes, decimales,
pesos de los modelos— viven en su tabla `commercial_parameters`, no en el
`.env` (Rafael, 24-oct-2026: cada microservicio guarda sus parámetros en sus
propias tablas). Los lee el bloque estándar SERVICE PARAMETERS de
`services/utils.py` una vez por contenedor; un valor cambiado en la tabla lo
toman los contenedores que arrancan después, sin redesplegar. Si falta uno, el
servicio no arranca.

- **Definición y valores:** filas `commercial` de `docs/parametros.md`.
- **Siembra:** `python -m tools.seeds.seed_service_parameters commercial --yes`.
- **Lo que cambia por empresa** está en sus políticas (`commercial_policies`,
  `commercial_credit_policies`), que se editan en Parámetros del portal; lo que
  la empresa no registra cae al valor de la tabla.

## Variables de entorno

Sólo entorno (`.env`; el despliegue lo pasa entero al Lambda, así que ningún
valor lleva coma ni llave):

| Variable | Qué es |
|---|---|
| `HOST`, `PORT`, `APP_ENV`, `ROOT_PATH` | Arranque de Uvicorn y prefijo detrás del gateway |
| `SECRET_KEY`, `ALGORITHM` | Validación del JWT de AUTH |
| `TARGET_TIMEZONE` | Zona con que se decide el día (`America/La_Paz`) |
| `API_URL` | Gateway `api.bearsoft.com.bo`: FILES, EVENTS, QUOTES y ML_FUNCTIONS |
| `BUCKET_NAME`, `BUCKET_PATH`, `TEMPLATES_S3_PREFIX` | Bucket de FILES, prefijo de los archivos y de las plantillas |
| `DYNAMODB_TABLE_NAME_*` | Las tablas de arriba; `DYNAMODB_TABLE_NAME_SERVICE_PARAMETERS` es `commercial_parameters` |
| `REQUEST_TIMEOUT_SECONDS`, `FILES_TIMEOUT_SECONDS`, `QUOTES_TIMEOUT_SECONDS` | Esperas de red |
| `OSRM_BASE_URL`, `OSRM_REQUEST_TIMEOUT_SECONDS` | Ruteo por calles |

## Local

```bash
cd services/commercial
python main.py            # puerto 3110, contra las tablas del .env
python -m pytest -q       # los tests no tocan AWS: moto, sembrado desde docs/parametros.md
```

Los tests responden lo que se pide a ML_FUNCTIONS con el propio código de
ML_FUNCTIONS (`tests/conftest.py`), así que no hay una segunda copia de ninguna
fórmula.
