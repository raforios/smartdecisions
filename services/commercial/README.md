# 🛍️ Commercial-Service 📈

The **commercial module** service of SmartDecisions. It receives what a company sells, collects, buys, holds in stock and covers on the street —by file or by API from its ERP—, keeps the client and seller master data, and answers the commercial analyses and the routes.

-----

## 🎯 Main Purpose

The **Commercial-Service** brings loads, analyses and routes together in one service. Its key features:

  * **File and API Loads:** Sales, payments, stock, purchases, visits and objectives, with the same contract, the same validator and the same error codes on both channels; invalid rows are set aside with their reason and the rest goes in. Files go through FILES.
  * **Master Data:** Clients and sellers, described once; a reload fills the empty fields and never overwrites a correction. A seller can register a client on the street.
  * **Analyses:** Commercial summary, volume source, demand forecast, segmentation, portfolio health, objectives, receivables, stock of the day, inventory history, purchases and exchange-rate effect.
  * **Opportunities:** Affinity × drop size: association rules between products and the expected sale of recommending each one to each point of sale.
  * **Routes:** Plans (imported, inferred from the day worked or built from sales), live routes with their position, plan against route comparison, order optimization and the stock of the day on the route.
  * **Three Currencies:** Every amount in bolivianos, official dollar and USDT (rates from QUOTES): the past at its own day's rate, today at today's.
  * **Calculations:** The projection, the segmentation tiers, the affinity rules, the split into days and the stop order are computed by ML-Functions; the streets, by OSRM.
  * **Ownership:** The owner (the JWT `client`) is part of every table key; someone else's resource answers like a missing one.

-----

## 🛠️ Technologies

  * **Language:** Python 3.14 🐍
  * **Web Framework:** FastAPI ✨
  * **ASGI Server:** Uvicorn 🚀
  * **Database:** AWS DynamoDB (`boto3`)
  * **Data Processing:** pandas 🐼, `openpyxl`
  * **Routing:** OSRM (`requests`)
  * **Data Validation:** Pydantic V2
  * **Cloud Platform:** AWS Lambda (`Mangum`) behind `api.bearsoft.com.bo`

-----

## 🚀 API Endpoints

The API **endpoints**, grouped by feature. All of them require `Authorization: Bearer <jwt>` unless stated otherwise.

### File Loads

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/v1/commercial/template` | Metadata of the sales **template**. |
| `GET` | `/v1/commercial/template/file/{contract}` | Downloads the **template** of a contract. |
| `POST` | `/v1/commercial/excel` | Uploads and validates a **sales file**, Excel or CSV. |
| `POST` | `/v1/commercial/excel-from-s3` | Loads a large **sales file** already uploaded to S3. |
| `POST` | `/v1/commercial/{dataset_id}/collections` | Uploads the **payments** of a sales load. |
| `POST` | `/v1/commercial/{dataset_id}/stock` | Uploads the **stock snapshot** of a sales load. |
| `POST` | `/v1/commercial/{dataset_id}/purchases` | Uploads the **purchases** of a sales load. |
| `POST` | `/v1/commercial/{dataset_id}/visits` | Uploads the sales force **visits**. |
| `POST` | `/v1/commercial/{dataset_id}/objectives` | Uploads the monthly **objectives**. |
| `GET` | `/v1/commercial/{dataset_id}/stock` | The **stock snapshot** of one day. |
| `GET` | `/v1/commercial/datasets` | Your own **loads**, newest first. |
| `GET` | `/v1/commercial/{dataset_id}` | Status of a **load**. |
| `GET` | `/v1/commercial/{dataset_id}/rejected` | Downloads the **rejected rows** with their reason. |

### API Loads (ERP)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/v1/commercial/sales/rows` | Creates a **sales load** from an ERP. |
| `POST` | `/v1/commercial/{dataset_id}/sales/rows` | Adds **sales lines** from an ERP. |
| `POST` | `/v1/commercial/{dataset_id}/collections/rows` | Pushes the **payments** from an ERP. |
| `POST` | `/v1/commercial/{dataset_id}/stock/rows` | Pushes the day's **stock** from an ERP. |
| `POST` | `/v1/commercial/{dataset_id}/purchases/rows` | Pushes the **purchases** from an ERP. |
| `POST` | `/v1/commercial/{dataset_id}/visits/rows` | Pushes the day's **visits** from an ERP. |
| `POST` | `/v1/commercial/{dataset_id}/objectives/rows` | Pushes the monthly **objectives** from an ERP. |
| `POST` | `/v1/commercial/{dataset_id}/collections/from-s3` | Loads a **payments** file already staged in S3. |
| `POST` | `/v1/commercial/{dataset_id}/stock/from-s3` | Loads a **stock** file already staged in S3. |
| `POST` | `/v1/commercial/{dataset_id}/purchases/from-s3` | Loads a **purchases** file already staged in S3. |
| `POST` | `/v1/commercial/{dataset_id}/visits/from-s3` | Loads a **visits** file already staged in S3. |
| `POST` | `/v1/commercial/{dataset_id}/objectives/from-s3` | Loads an **objectives** file already staged in S3. |

### Master Data

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/v1/commercial/clients` | Pushes the **client master** from an ERP. |
| `POST` | `/v1/commercial/clients/field` | Registers a **client** on the street. |
| `GET` | `/v1/commercial/clients` | The company's **clients**. |
| `GET` | `/v1/commercial/clients/{client_id}` | One **client**. |
| `PATCH` | `/v1/commercial/clients/{client_id}` | Corrects a **client**. |
| `GET` | `/v1/commercial/sellers` | The company's **sellers**. |
| `PATCH` | `/v1/commercial/sellers/{seller_id}` | Links a **seller** to a user, or renames them. |

### Analyses

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/v1/commercial/summary/{dataset_id}` | **Commercial summary**: KPIs, rankings, distributions and trend. |
| `GET` | `/v1/commercial/forecast/{dataset_id}` | **Demand forecast**: linear trend or moving average, total or by category. |
| `GET` | `/v1/commercial/segmentation/{dataset_id}` | Client value **segmentation** (High, Medium, Low). |
| `GET` | `/v1/commercial/portfolio/{dataset_id}` | **Portfolio health**: coverage, churn and clients at risk. |
| `GET` | `/v1/commercial/objectives/{dataset_id}` | **Objective attainment**: traffic light, gap and points. |
| `GET` | `/v1/commercial/receivables/{dataset_id}` | **Receivables**: aging, recoverability and collection agenda. |
| `GET` | `/v1/commercial/stock/{dataset_id}` | **Stock of the day**: coverage, stockout risk and tied-up capital. |
| `GET` | `/v1/commercial/stock-history/{dataset_id}` | **Inventory over time**. |
| `GET` | `/v1/commercial/purchases/{dataset_id}` | **Cost of purchases**. |
| `GET` | `/v1/commercial/fx-effect/{dataset_id}` | **Exchange-rate effect** on sales, margin and restocking. |
| `GET` | `/v1/commercial/dashboard/{dataset_id}` | **Main dashboard**: the salient figure of each area. |
| `GET` | `/v1/commercial/clients/overview/{dataset_id}` | The **clients** of a load, largest first. |
| `GET` | `/v1/commercial/client/{dataset_id}/{client_id}` | The **card** of one client. |

### Opportunities

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/v1/commercial/run/{dataset_id}` | Runs the **affinity × drop size engine** on a load. |
| `GET` | `/v1/commercial/runs` | Your own **runs**, newest first. |
| `GET` | `/v1/commercial/results/{dataset_id}` | The latest **run** of a load. |
| `GET` | `/v1/commercial/results/{dataset_id}/pdv/{pdv_id}` | The **opportunities** of one point of sale. |

### Company Policies

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/v1/commercial/commercial-policy` | The **commercial policy** applied to the company's attainment. |
| `PUT` | `/v1/commercial/commercial-policy` | Sets the company's **commercial policy**. |
| `GET` | `/v1/commercial/credit-policy` | The **credit policy** applied to the company's book. |
| `PUT` | `/v1/commercial/credit-policy` | Sets the company's **credit policy**. |

### Planned Routes

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/v1/commercial/routes/planned` | Creates a **planned route** with its stops. |
| `GET` | `/v1/commercial/routes/planned` | Lists the company's **planned routes**. |
| `POST` | `/v1/commercial/routes/planned/filter` | Filters the **planned routes**. |
| `POST` | `/v1/commercial/routes/planned/bulk-upload` | Imports **planned routes** from a CSV. |
| `POST` | `/v1/commercial/routes/planned/infer` | Builds the **plan** from what a seller visited on a day. |
| `GET` | `/v1/commercial/routes/planned/{planned_route_id}` | One **planned route** with its stops. |
| `PATCH` | `/v1/commercial/routes/planned/{planned_route_id}` | Updates the header of a **planned route**. |
| `PATCH` | `/v1/commercial/routes/planned/{planned_route_id}/status` | Changes the status of a **planned route** (`IN CREATION`, `ACTIVE`, `INACTIVE`). |
| `DELETE` | `/v1/commercial/routes/planned/{planned_route_id}` | Deletes a **planned route** still in creation. |
| `POST` | `/v1/commercial/routes/planned/{planned_route_id}/points` | Adds a **stop** to a route in creation. |
| `PATCH` | `/v1/commercial/routes/planned/{planned_route_id}/points/{planned_point_id}` | Edits a **stop** of a route in creation. |
| `DELETE` | `/v1/commercial/routes/planned/{planned_route_id}/points/{planned_point_id}` | Removes a **stop** from a route in creation. |
| `GET` | `/v1/commercial/routes/planned/{planned_route_id}/optimization` | In what **order** the route was worth doing, measured on the streets. |
| `POST` | `/v1/commercial/routes/planned/{planned_route_id}/repeat` | Runs a **route** again on another day, in its current or optimized order. |

### Plan from Sales

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/v1/commercial/plan/{dataset_id}` | **Visit plan** derived from a sales load: clients split into days and ordered. |
| `POST` | `/v1/commercial/plan/{dataset_id}/by-seller` | One **plan per seller**, from each seller's own portfolio. |

### Executed Routes

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/v1/commercial/routes/executed` | A seller **starts** a route. |
| `GET` | `/v1/commercial/routes/executed` | Lists the **executed routes**. |
| `POST` | `/v1/commercial/routes/executed/points` | Reports a **position** or a **visit** on an open route. |
| `GET` | `/v1/commercial/routes/executed/last-location` | Where each **seller** last reported from. |
| `GET` | `/v1/commercial/routes/executed/{executed_route_id}` | One **executed route** with every reported point. |
| `PATCH` | `/v1/commercial/routes/executed/{executed_route_id}` | A seller **ends** a route. |
| `PATCH` | `/v1/commercial/routes/executed/{executed_route_id}/reopen` | Reopens a route closed by mistake, the same day. |

### Comparison and Statistics

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/v1/commercial/routes/comparison/{planned_route_id}` | The **plan** and its executions with their points. |
| `GET` | `/v1/commercial/statistics/route-comparisons/{planned_route_id}` | Scores every **execution** of a plan. |
| `GET` | `/v1/commercial/statistics/sellers/{seller}/points-visited` | Every **point** a seller reported in a period. |
| `GET` | `/v1/commercial/statistics/day/{day}` | What the **field** did on one day. |

### Stock of the Day on the Route

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `PUT` | `/v1/commercial/stock/day` | Loads the opening **stock** of a day. |
| `POST` | `/v1/commercial/stock/day/from-ingest` | Opens the day from the **stock file** already loaded. |
| `GET` | `/v1/commercial/stock/day/{day}` | What is left of the day's **stock**, per SKU. |

### Route Settings

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/v1/commercial/settings` | The routes' **start and end point**. |
| `PUT` | `/v1/commercial/settings` | Sets the routes' **start and end point**. |

### Health

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Service home page. |
| `GET` | `/v1/commercial/health` | Service health and configuration check. |
| `GET` | `/v1/commercial/health/tables` | State of the service's DynamoDB tables. |

-----

## 🗄️ Stored Data

| Table | Partition key | Sort key | What it holds |
|---|---|---|---|
| `commercial_datasets` | `id` | — | A sales load: owner, status, summary and pointers to its files in S3 (the payments, stock, purchases, visits and objectives attached) |
| `commercial_clients` | `owner_email` | `id` | Client master data |
| `commercial_sellers` | `owner_email` | `id` | Seller master data and the user they sign in with |
| `commercial_analytics_runs` | `id` | — | The opportunity runs |
| `commercial_policies` | `owner_email` | — | The company's commercial policy (objective traffic light, bolivianos per point, share of cost in dollars) |
| `commercial_credit_policies` | `owner_email` | — | The company's credit policy (aging buckets, losses, rate, term) |
| `commercial_planned_routes` | `owner_email` | `id` | Route plans with their stops |
| `commercial_executed_routes` | `owner_email` | `id` | Executed routes with every reported point |
| `commercial_daily_stock` | `owner_email` | `stock_key` | The stock a day opens with and what was sold on the route |
| `commercial_route_settings` | `owner_email` | — | The routes' start and end point |
| `commercial_parameters` | `code` | — | The service's business values |

-----

## 📂 Files in S3

FILES bucket, prefix `commercial/`. Each file is a CSV with the **fields** of its contract, not the Spanish template headers. The contract is `schemas/commercial.py`: the validator, the templates (`tools/templates/`) and these tables come from it. Set-aside rows go to `commercial/rejected/` with their reason code.

#### Sales — `commercial/normalized/<uuid>.csv`

| Template header | Field | Type | Required | Rule |
|---|---|---|---|---|
| Fecha | `date` | date | yes |  |
| Nro Factura | `order_id` | text | yes | up to 64 chars |
| Cliente ID | `pos_id` | text | derived by the service | up to 64 chars |
| Cliente | `pos_name` | text | yes |  |
| Zona | `zone` | text | no |  |
| Ciudad | `city` | text | no |  |
| Region | `region` | text | no |  |
| Canal | `channel` | text | no |  |
| Vendedor | `seller` | text | no |  |
| Latitud | `latitude` | number | no | between -90 and 90 |
| Longitud | `longitude` | number | no | between -180 and 180 |
| Producto ID | `product_id` | text | derived by the service | up to 64 chars |
| Producto | `product_name` | text | yes |  |
| Categoria | `category` | text | no |  |
| Cantidad | `quantity` | number | yes | > 0 |
| Precio Unitario | `unit_price` | number | no | ≥ 0 |
| Costo Unitario | `unit_cost` | number | no | ≥ 0 |
| Monto Total | `total_amount` | number | no | ≥ 0 |
| Condicion Venta | `payment_terms` | text | no | up to 16 chars; one of: CONTADO, CREDITO |
| Plazo Dias | `credit_days` | integer | no | ≥ 0 |
| Fecha Vencimiento | `due_date` | date | no |  |
| Responsable Cobro | `collector` | text | no |  |
| Limite Credito | `credit_limit` | number | no | ≥ 0 |

#### Payments — `commercial/collections/<uuid>.csv`

| Template header | Field | Type | Required | Rule |
|---|---|---|---|---|
| Nro Factura | `order_id` | text | yes | up to 64 chars |
| Fecha Cobro | `payment_date` | date | yes |  |
| Monto Cobrado | `paid_amount` | number | yes | > 0 |
| Medio | `payment_method` | text | no | up to 32 chars |
| Responsable Cobro | `collector` | text | no |  |

#### Stock — `commercial/stock/<uuid>.csv`

| Template header | Field | Type | Required | Rule |
|---|---|---|---|---|
| Fecha | `snapshot_date` | date | yes |  |
| Producto ID | `product_id` | text | derived by the service | up to 64 chars |
| Producto | `product_name` | text | yes |  |
| Existencia | `on_hand` | number | yes | ≥ 0 |
| Comprometido | `committed` | number | no | ≥ 0 |
| En Transito | `in_transit` | number | no | ≥ 0 |
| Almacen | `warehouse` | text | no | up to 64 chars |
| Costo Unitario | `unit_cost` | number | no | ≥ 0 |
| Precio de Venta | `unit_price` | number | yes | ≥ 0 |

#### Purchases — `commercial/purchases/<uuid>.csv`

| Template header | Field | Type | Required | Rule |
|---|---|---|---|---|
| Fecha | `purchase_date` | date | yes |  |
| Proveedor | `supplier` | text | yes | up to 128 chars |
| Producto ID | `product_id` | text | derived by the service | up to 64 chars |
| Producto | `product_name` | text | yes |  |
| Cantidad | `quantity` | number | yes | > 0 |
| Costo Unitario | `unit_cost` | number | yes | ≥ 0 |
| Moneda | `currency` | text | yes | one of: BOB, USD, USDT |

#### Visits — `commercial/visits/<uuid>.csv`

| Template header | Field | Type | Required | Rule |
|---|---|---|---|---|
| Fecha | `visit_date` | date | yes |  |
| Hora | `visit_time` | text | no | up to 8 chars |
| Vendedor | `seller` | text | yes | up to 128 chars |
| Cliente ID | `pos_id` | text | derived by the service | up to 64 chars |
| Cliente | `pos_name` | text | yes |  |
| Latitud | `latitude` | number | no | between -90 and 90 |
| Longitud | `longitude` | number | no | between -180 and 180 |
| Resultado | `outcome` | text | no | up to 16 chars; one of: VENTA, SIN_VENTA, CERRADO, NO_ENCONTRADO |
| Nro Factura | `order_id` | text | no | up to 64 chars |

#### Objectives — `commercial/objectives/<uuid>.csv`

| Template header | Field | Type | Required | Rule |
|---|---|---|---|---|
| Cliente ID | `pos_id` | text | derived by the service | up to 64 chars |
| Cliente | `pos_name` | text | yes |  |
| Periodo | `period` | text | yes | up to 7 chars |
| Objetivo | `target_amount` | number | yes | ≥ 0 |

#### Clients — master data (goes to `commercial_clients`, not to S3)

| Template header | Field | Type | Required | Rule |
|---|---|---|---|---|
| Cliente ID | `id` | text | yes | up to 64 chars |
| Cliente | `name` | text | yes | up to 150 chars |
| NIT | `tax_id` | text | no | up to 40 chars |
| Tipo Negocio | `client_type` | text | no | up to 64 chars |
| Canal | `channel` | text | no | up to 64 chars |
| Zona | `zone` | text | no | up to 100 chars |
| Ciudad | `city` | text | no | up to 100 chars |
| Region | `region` | text | no | up to 100 chars |
| Direccion | `address` | text | no | up to 255 chars |
| Latitud | `latitude` | number | no | between -90 and 90 |
| Longitud | `longitude` | number | no | between -180 and 180 |
| Telefono | `phone` | text | no | up to 40 chars |
| Contacto | `contact` | text | no | up to 150 chars |
| Vendedor | `seller` | text | no | up to 128 chars |
| Limite Credito | `credit_limit` | number | no | ≥ 0 |
| Cluster | `cluster` | text | no | up to 40 chars |
| Supervisor | `supervisor` | text | no | up to 128 chars |
| Mercado | `market` | text | no | up to 100 chars |

-----

## ⚙️ Business Values

The service's business values live in the `commercial_parameters` table (one item per code),
not in `.env`. They are read by `load_parameters`, from the SERVICE PARAMETERS
block at the end of `services/utils.py`, once per container; a value changed in
the table is picked up by the containers that start afterwards. If one is
missing, the service does not start. What each company sets lives in its policies (`commercial_policies`, `commercial_credit_policies`); what the company does not set takes the table value. Definition: the `commercial` rows of
`docs/parametros.md`. Seed:

```shell
python -m tools.seeds.seed_service_parameters commercial --yes
```

-----

## 🗂️ Service Structure

```txt
commercial/
├── controllers/
│   ├── __init__.py
│   ├── analytics.py
│   ├── channels.py
│   ├── client_card.py
│   ├── clients.py
│   ├── collections.py
│   ├── commercial.py
│   ├── common.py
│   ├── daily_stock.py
│   ├── dashboard.py
│   ├── localization.py
│   ├── objectives.py
│   ├── optimization.py
│   ├── optimization_settings.py
│   ├── policies.py
│   ├── purchases.py
│   ├── purchases_load.py
│   ├── sellers.py
│   ├── stock.py
│   └── visits.py
├── models/
│   ├── __init__.py
│   ├── analytics.py
│   ├── clients.py
│   ├── commercial.py
│   ├── daily_stock.py
│   ├── localization.py
│   ├── optimization.py
│   ├── optimization_settings.py
│   └── sellers.py
├── routes/
│   ├── __init__.py
│   ├── analytics.py
│   ├── areas.py
│   ├── channels.py
│   ├── clients.py
│   ├── commercial.py
│   ├── common.py
│   ├── daily_stock.py
│   ├── localization.py
│   ├── optimization.py
│   ├── optimization_settings.py
│   └── sellers.py
├── schemas/
│   ├── __init__.py
│   ├── analytics.py
│   ├── channels.py
│   ├── client.py
│   ├── clients.py
│   ├── commercial.py
│   ├── daily_stock.py
│   ├── dashboard.py
│   ├── files.py
│   ├── fx_effect.py
│   ├── health.py
│   ├── localization.py
│   ├── objectives.py
│   ├── optimization.py
│   ├── optimization_settings.py
│   ├── purchases.py
│   ├── receivables.py
│   ├── route_optimization.py
│   ├── sellers.py
│   └── stock.py
├── services/
│   ├── __init__.py
│   ├── affinity.py
│   ├── analytics.py
│   ├── analytics_utils.py
│   ├── api_exceptions.py
│   ├── calculations.py
│   ├── client_card.py
│   ├── clients.py
│   ├── collections.py
│   ├── commercial.py
│   ├── commercial_utils.py
│   ├── common.py
│   ├── concentration.py
│   ├── crud.py
│   ├── currency.py
│   ├── daily_stock.py
│   ├── dashboard.py
│   ├── day_statistics.py
│   ├── db_connection.py
│   ├── efficiency.py
│   ├── environment.py
│   ├── exceptions.py
│   ├── forecast.py
│   ├── fx_effect.py
│   ├── growth.py
│   ├── load_contract.py
│   ├── load_files.py
│   ├── localization.py
│   ├── localization_executed.py
│   ├── localization_sources.py
│   ├── localization_stats.py
│   ├── logger_config.py
│   ├── margin.py
│   ├── month.py
│   ├── objectives.py
│   ├── objectives_load.py
│   ├── optimization.py
│   ├── optimization_settings.py
│   ├── portfolio.py
│   ├── purchases.py
│   ├── purchases_load.py
│   ├── receivables.py
│   ├── receivables_fx.py
│   ├── receivables_views.py
│   ├── route_optimization.py
│   ├── routing.py
│   ├── security.py
│   ├── segmentation.py
│   ├── sellers.py
│   ├── stock.py
│   ├── stock_history.py
│   ├── stock_load.py
│   ├── utils.py
│   ├── visits.py
│   └── volume.py
├── tests/
├── .dockerignore
├── .env
├── .gitignore
├── deploy.config
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

2.  **Configure the environment:** Create the `.env` file with `HOST`, `PORT`, `APP_ENV`, `SECRET_KEY`, `ALGORITHM`, `TARGET_TIMEZONE`, `ROOT_PATH`, `API_URL`, `BUCKET_NAME`, `BUCKET_PATH`, `TEMPLATES_S3_PREFIX`, the tables `DYNAMODB_TABLE_NAME_*`, the timeouts and `OSRM_BASE_URL`.

3.  **Start the API server:**

```shell
python main.py
```

4.  **Run the tests:**

```shell
python -m pytest -q
pylint --fail-under=10.0 .
```

The tests never touch AWS: `tests/conftest.py` seeds the business values table in moto from `docs/parametros.md` and answers the ML-Functions calls with ML-Functions' own code.

-----

## 👤 Created By

**Rafael Ríos Bascón**
[raforios@gmail.com](mailto:raforios@gmail.com)
