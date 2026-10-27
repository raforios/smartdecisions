# 🧾 Billing-Service 💊

The **billing** service of BearSoft (SmartBilling). It records what a shop buys and sells, and keeps the shelf up to date with every movement. Pharmacies are the first vertical; it is sold alone or with SmartDecisions.

-----

## 🎯 Main Purpose

The **Billing-Service** is a shop's counter system. Its key features:

  * **Catalogue and Batches:** Every product is sold by batch; cost, price and expiry belong to the batch, and the catalogue shows the price of the batch that sells next.
  * **FEFO Sales:** First expiring, first out; a batch with no date sells last. A line can span two batches and each charges its own price: the line keeps which units came from which batch.
  * **Voiding:** A voided note returns its units exactly to the batches they came from, with their cost and expiry.
  * **Purchases:** Supplier delivery notes, which create or top up batches.
  * **Till:** One till per user and day; no sale without today's open till; cash-only, voidable expenses; on closing it stores the expected, the counted and the difference.
  * **Dashboard:** Sold, cost, margin, average ticket, capital on the shelf, batches about to expire and expired, products below minimum and best sellers by amount.
  * **No Overselling:** The stock decrement is a DynamoDB transaction conditioned on what is left in each batch; if two tills sell the last unit, one gets `INSUFFICIENT_STOCK` before printing.

-----

## 🛠️ Technologies

  * **Language:** Python 3.14 🐍
  * **Web Framework:** FastAPI ✨
  * **ASGI Server:** Uvicorn 🚀
  * **Database:** AWS DynamoDB (`boto3`, transactions)
  * **SIAT:** SOAP client with the WSDLs read from `wsdl/`
  * **Data Validation:** Pydantic V2
  * **Cloud Platform:** AWS Lambda (`Mangum`) behind `api.bearsoft.com.bo`

-----

## 🚀 API Endpoints

The API **endpoints**, grouped by feature. All of them require `Authorization: Bearer <jwt>` unless stated otherwise.

### Dashboard and Settings

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/v1/billing/dashboard` | The counter **dashboard**. |
| `GET` | `/v1/billing/settings` | The shop's **settings**. |
| `PUT` | `/v1/billing/settings` | Saves the shop's **settings**. |

### Products and Batches

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/v1/billing/products` | The **catalogue** with availability. |
| `POST` | `/v1/billing/products` | Registers a **product** (SKU). |
| `GET` | `/v1/billing/products/{sku}` | One **product**. |
| `PATCH` | `/v1/billing/products/{sku}` | Edits a **product**. |
| `GET` | `/v1/billing/products/{sku}/lots` | A product's **batches**, in selling order. |
| `PATCH` | `/v1/billing/products/{sku}/lots/{lot_id}` | Re-prices a **batch**. |

### Purchases

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/v1/billing/purchases` | Records a supplier **delivery note**. |
| `GET` | `/v1/billing/purchases` | The **delivery notes** of a period. |
| `GET` | `/v1/billing/purchases/{purchase_id}` | One **delivery note**. |

### Sales

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/v1/billing/sales` | Sells over the **counter**. |
| `GET` | `/v1/billing/sales` | The **sale notes** of a period. |
| `GET` | `/v1/billing/sales/{sale_id}` | One **sale note**, as it prints. |
| `POST` | `/v1/billing/sales/{sale_id}/cancel` | Voids a **note** and returns its units to their batches; an invoice is cancelled at the SIN first, with `reason_code`. |

### Till (`/v1/billing/cash`)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/v1/billing/cash/sessions` | Opens the caller's **till**. |
| `GET` | `/v1/billing/cash/sessions/current` | The caller's open **till**. |
| `GET` | `/v1/billing/cash/sessions` | The shop's **tills**. |
| `GET` | `/v1/billing/cash/sessions/{session_id}` | One **till** and its count. |
| `POST` | `/v1/billing/cash/sessions/{session_id}/expenses` | Takes cash out of the open **till** (expense). |
| `POST` | `/v1/billing/cash/sessions/{session_id}/expenses/{movement_id}/cancel` | Cancels an **expense** of the open till. |
| `POST` | `/v1/billing/cash/sessions/{session_id}/close` | Closes a **till** against the cash counted. |
| `GET` | `/v1/billing/cash/alerts` | The **tills** to close now. |

### SIAT (`/v1/billing/siat`)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/v1/billing/siat/codes` | The **CUIS** and **CUFD** in force for the shop's branch and point of sale; asks the SIN only for the ones missing or expired. |
| `POST` | `/v1/billing/siat/catalogs/sync` | Brings the 17 **SIN catalogues** and stores them (managers). |
| `GET` | `/v1/billing/siat/catalogs/{catalog}` | One stored **catalogue** (`LEGENDS`, `PAYMENT_METHODS`, `UNITS_OF_MEASURE`...). |

### Health

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Service home page. |
| `GET` | `/v1/billing/health` | Service health and configuration check. |
| `GET` | `/v1/billing/health/tables` | State of the service's DynamoDB tables. |

-----

## 🗄️ Stored Data

Every table is partitioned by **owner** (the shop, taken from the token); the owner is part of every key.

| Table | Partition key | Sort key |
|---|---|---|
| `billing_products` | `owner` | `sku` |
| `billing_lots` | `owner` | `lot_key` = `sku#lot_id` |
| `billing_sales` | `owner` | `sale_id` (starts with the timestamp) |
| `billing_purchases` | `owner` | `purchase_id` |
| `billing_cash_sessions` | `owner` | `session_id` (starts with the opening time) |
| `billing_cash_movements` | `owner` | `movement_key` = `session_id#movement` |
| `billing_settings` | `owner` | `setting_key` |
| `billing_parameters` | `code` | — |

**A till:** `user_email`, `status` (`OPEN`, `CLOSED`), `business_day`, `opened_at`, `opening_cash` and, on closing, `closed_at`, `closed_by`, `counted_cash`, `expected_cash`, `difference`, `note`. **An expense:** `expense_type` (`SUPPLIER_PAYMENT`, `SERVICE_PAYMENT`, `PETTY_CASH`), `amount`, `concept`, `purchase_id`, `status` (`ACTIVE`, `CANCELLED`) and who created or cancelled it and when. Payment methods: `EFECTIVO`, `QR`, `TARJETA_DEBITO`, `TARJETA_CREDITO`. Till specification: `docs/cambios/billing-caja/spec.md`.

**SIAT codes and catalogues** live in `billing_settings`: `siat#codes#<branch>#<point_of_sale>` (CUIS, CUFD, control code, validity) and `siat#catalog#<catalogue>` (rows with `code`, `description`, `activity_code`).

**Invoicing a sale.** With `invoicing_enabled` on in the settings, `POST /v1/billing/sales` turns every sale into an invoice sent with `recepcionFactura`. Before any stock moves it requires the buyer's document and document type, the shop's `municipality`, the three SIN codes on every product and a legend of the product's activity in the synced `LEGENDS`. Then it draws the stock down, takes the invoice number (`counter#invoice#<branch>#<point_of_sale>`), builds the CUF with the day's control code and the XML, and sends it. If the SIN refuses it or cannot be reached, the units go back and the sale is not issued. The accepted invoice is stored on the sale as `invoice` (`number`, `cuf`, `cufd`, `issued_at`, `legend`, `address`, `branch`, `point_of_sale`, `state`, `reception_code`, `siat_state`, `qr_url`, `cancellation_reason`); `qr_url` points at `SIAT_QR_URL`. Off, the sale is an internal note as before.

**Cancelling an invoice.** `POST /v1/billing/sales/{sale_id}/cancel` takes an optional body `{"reason_code": <CANCELLATION_REASONS code>}`. An invoiced note requires it and is cancelled with `anulacionFactura` first, with the codes in force; if the SIN refuses, the note stays issued and nothing moves. An internal note needs no body.

Error codes: `SIAT_REFUSED`, `SIAT_ISSUER_INCOMPLETE`, `CATALOG_NOT_SYNCED`, `LEGEND_NOT_FOUND`, `CANCELLATION_REASON_REQUIRED`, `PRODUCT_NOT_HOMOLOGATED`, `BUYER_REQUIRED`, `INSUFFICIENT_STOCK`, `PRODUCT_NOT_FOUND`, `DUPLICATE_LINE`, `DISCOUNTS_DISABLED`, `SALE_ALREADY_CANCELLED`, `SETTINGS_NOT_FOUND`, among others.

-----

## ⚙️ Business Values

The service's business values live in the `billing_parameters` table (one item per code),
not in `.env`. They are read by `load_parameters`, from the SERVICE PARAMETERS
block at the end of `services/utils.py`, once per container; a value changed in
the table is picked up by the containers that start afterwards. If one is
missing, the service does not start. What each shop sets (for example the till-closing alert time) lives in `billing_settings`. Definition: the `billing` rows of
`docs/parametros.md`. Seed:

```shell
python -m tools.seeds.seed_service_parameters billing --yes
```

-----

## 🗂️ Service Structure

```txt
billing/
├── controllers/
│   ├── __init__.py
│   ├── billing.py
│   ├── billing_cash.py
│   └── billing_siat.py
├── models/
│   ├── __init__.py
│   └── billing.py
├── routes/
│   ├── __init__.py
│   ├── billing.py
│   ├── billing_cash.py
│   └── billing_siat.py
├── schemas/
│   ├── __init__.py
│   ├── billing.py
│   ├── billing_cash.py
│   ├── billing_siat.py
│   └── health.py
├── services/
│   ├── __init__.py
│   ├── api_exceptions.py
│   ├── billing.py
│   ├── billing_cash.py
│   ├── billing_invoice_xml.py
│   ├── billing_invoicing.py
│   ├── billing_purchases.py
│   ├── billing_reports.py
│   ├── billing_sales.py
│   ├── billing_siat.py
│   ├── billing_siat_client.py
│   ├── billing_siat_codes.py
│   ├── billing_stock.py
│   ├── crud.py
│   ├── db_connection.py
│   ├── environment.py
│   ├── exceptions.py
│   ├── logger_config.py
│   ├── security.py
│   └── utils.py
├── wsdl/
│   ├── <service>.wsdl          # codigos, facturacion, sincronizacion, operaciones, ajuste, compras
│   ├── <service>_types.wsdl    # the half each one imports, kept on disk
│   └── LEEME.md
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

2.  **Configure the environment:** Create the `.env` file with `HOST`, `PORT`, `APP_ENV`, `SECRET_KEY`, `ALGORITHM`, `TARGET_TIMEZONE`, `ROOT_PATH`, `API_URL`, the tables `DYNAMODB_TABLE_NAME_*` and the SIAT connection (`SIAT_*`).

3.  **Start the API server:**

```shell
python main.py
```

4.  **Run the tests:**

```shell
python -m pytest -q
pylint --fail-under=10.0 .
```

The full check, from the repository root: `python tools/verification/verify_service.py services/billing`.

-----

## 👤 Created By

**Rafael Ríos Bascón**
[raforios@gmail.com](mailto:raforios@gmail.com)
