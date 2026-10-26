# 🧾 Billing-Service 💊

Microservicio de **facturación** de BearSoft (SmartBilling). Registra lo que un comercio compra y lo que vende, y mantiene la estantería al día con cada movimiento. El primer vertical son las farmacias; se vende solo o junto a SmartDecisions.

-----

## 🎯 Propósito Principal

El **Billing-Service** es el sistema de mostrador de un comercio. Sus funcionalidades clave incluyen:

  * **Catálogo y Lotes:** Cada producto se vende por lote; el costo, el precio y el vencimiento son del lote, y el catálogo muestra el precio del lote que sale próximo.
  * **Venta FEFO:** Sale primero lo que vence antes; un lote sin fecha se vende al final. Una línea puede abarcar dos lotes y cada uno cobra su precio: la línea guarda qué unidades salieron de qué lote.
  * **Anulación:** Una nota anulada devuelve sus unidades exactamente a los lotes de los que salieron, con su costo y su vencimiento.
  * **Compras:** Notas de ingreso por proveedor, que crean o completan lotes.
  * **Caja:** Una caja por usuario y día; no se vende sin caja abierta de hoy; egresos sólo en efectivo y anulables; al cerrar se guardan lo esperado, lo contado y la diferencia.
  * **Tablero:** Vendido, costo, margen, ticket promedio, capital en estantería, lotes por vencer y vencidos, productos bajo mínimo y los más vendidos por monto.
  * **Sin Sobreventa:** El descuento de stock es una transacción de DynamoDB condicionada a lo que queda en cada lote; si dos cajas venden la última unidad, una recibe `INSUFFICIENT_STOCK` antes de imprimir.

-----

## 🛠️ Tecnologías Utilizadas

  * **Lenguaje:** Python 3.14 🐍
  * **Framework Web:** FastAPI ✨
  * **Servidor ASGI:** Uvicorn 🚀
  * **Base de Datos:** AWS DynamoDB (`boto3`, transacciones)
  * **SIAT:** cliente SOAP con los WSDL leídos de `wsdl/`
  * **Validación de Datos:** Pydantic V2
  * **Plataforma Cloud:** AWS Lambda (`Mangum`) detrás de `api.bearsoft.com.bo`

-----

## 🚀 Endpoints de la API

A continuación se listan los **endpoints** de la API, agrupados por su funcionalidad. Todos exigen `Authorization: Bearer <jwt>` salvo que se indique otra cosa.

### Tablero y Configuración

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `GET` | `/v1/billing/dashboard` | El **tablero** del mostrador. |
| `GET` | `/v1/billing/settings` | La **configuración** del comercio. |
| `PUT` | `/v1/billing/settings` | Guarda la **configuración** del comercio. |

### Productos y Lotes

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `GET` | `/v1/billing/products` | El **catálogo** con su disponibilidad. |
| `POST` | `/v1/billing/products` | Registra un **producto** (SKU). |
| `GET` | `/v1/billing/products/{sku}` | Un **producto**. |
| `PATCH` | `/v1/billing/products/{sku}` | Edita un **producto**. |
| `GET` | `/v1/billing/products/{sku}/lots` | Los **lotes** de un producto, en orden de venta. |
| `PATCH` | `/v1/billing/products/{sku}/lots/{lot_id}` | Cambia el precio de un **lote**. |

### Compras

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/v1/billing/purchases` | Registra una **nota de ingreso** de un proveedor. |
| `GET` | `/v1/billing/purchases` | Las **notas de ingreso** de un período. |
| `GET` | `/v1/billing/purchases/{purchase_id}` | Una **nota de ingreso**. |

### Ventas

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/v1/billing/sales` | Vende en el **mostrador**. |
| `GET` | `/v1/billing/sales` | Las **notas de venta** de un período. |
| `GET` | `/v1/billing/sales/{sale_id}` | Una **nota de venta**, como se imprime. |
| `POST` | `/v1/billing/sales/{sale_id}/cancel` | Anula una **nota** y devuelve sus unidades a sus lotes. |

### Caja (`/v1/billing/cash`)

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/v1/billing/cash/sessions` | Abre la **caja** de quien llama. |
| `GET` | `/v1/billing/cash/sessions/current` | La **caja** abierta de quien llama. |
| `GET` | `/v1/billing/cash/sessions` | Las **cajas** del comercio. |
| `GET` | `/v1/billing/cash/sessions/{session_id}` | Una **caja** y su arqueo. |
| `POST` | `/v1/billing/cash/sessions/{session_id}/expenses` | Saca efectivo de la **caja** abierta (egreso). |
| `POST` | `/v1/billing/cash/sessions/{session_id}/expenses/{movement_id}/cancel` | Anula un **egreso** de la caja abierta. |
| `POST` | `/v1/billing/cash/sessions/{session_id}/close` | Cierra una **caja** contra el efectivo contado. |
| `GET` | `/v1/billing/cash/alerts` | Las **cajas** que hay que cerrar ahora. |

### Salud

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `GET` | `/` | Página de inicio del servicio. |
| `GET` | `/v1/billing/health` | Salud del servicio y validación de su configuración. |
| `GET` | `/v1/billing/health/tables` | Estado de las tablas DynamoDB del servicio. |

-----

## 🗄️ Datos que guarda

Todas las tablas se particionan por **dueño** (el comercio, tomado del token); el dueño es parte de cada clave.

| Tabla | Partición | Orden |
|---|---|---|
| `billing_products` | `owner` | `sku` |
| `billing_lots` | `owner` | `lot_key` = `sku#lot_id` |
| `billing_sales` | `owner` | `sale_id` (empieza con la marca de tiempo) |
| `billing_purchases` | `owner` | `purchase_id` |
| `billing_cash_sessions` | `owner` | `session_id` (empieza con la hora de apertura) |
| `billing_cash_movements` | `owner` | `movement_key` = `session_id#movimiento` |
| `billing_settings` | `owner` | `setting_key` |
| `billing_parameters` | `code` | — |

**Una caja:** `user_email`, `status` (`OPEN`, `CLOSED`), `business_day`, `opened_at`, `opening_cash` y, al cerrar, `closed_at`, `closed_by`, `counted_cash`, `expected_cash`, `difference`, `note`. **Un egreso:** `expense_type` (`SUPPLIER_PAYMENT`, `SERVICE_PAYMENT`, `PETTY_CASH`), `amount`, `concept`, `purchase_id`, `status` (`ACTIVE`, `CANCELLED`) y quién y cuándo lo creó o anuló. Medios de pago: `EFECTIVO`, `QR`, `TARJETA_DEBITO`, `TARJETA_CREDITO`. Especificación de la caja: `docs/cambios/billing-caja/spec.md`.

Códigos de error: `INSUFFICIENT_STOCK`, `PRODUCT_NOT_FOUND`, `DUPLICATE_LINE`, `DISCOUNTS_DISABLED`, `SALE_ALREADY_CANCELLED`, `SETTINGS_NOT_FOUND`, entre otros.

-----

## ⚙️ Valores de negocio

Los valores de negocio del servicio viven en la tabla `billing_parameters` (un ítem por
código), no en el `.env`. Los lee `load_parameters`, del bloque SERVICE
PARAMETERS al final de `services/utils.py`, una vez por contenedor; un valor
cambiado en la tabla lo toman los contenedores que arrancan después. Si falta
uno, el servicio no arranca. Lo de cada comercio (por ejemplo la hora de la alerta de cierre de caja) está en `billing_settings`. Definición: filas `billing` de
`docs/parametros.md`. Siembra:

```shell
python -m tools.seeds.seed_service_parameters billing --yes
```

-----

## 🗂️ Estructura del Microservicio

```txt
billing/
├── controllers/
│   ├── __init__.py
│   ├── billing.py
│   └── billing_cash.py
├── models/
│   ├── __init__.py
│   └── billing.py
├── routes/
│   ├── __init__.py
│   ├── billing.py
│   └── billing_cash.py
├── schemas/
│   ├── __init__.py
│   ├── billing.py
│   ├── billing_cash.py
│   └── health.py
├── services/
│   ├── __init__.py
│   ├── api_exceptions.py
│   ├── billing.py
│   ├── billing_cash.py
│   ├── billing_invoice_xml.py
│   ├── billing_purchases.py
│   ├── billing_reports.py
│   ├── billing_sales.py
│   ├── billing_siat.py
│   ├── billing_siat_client.py
│   ├── billing_stock.py
│   ├── crud.py
│   ├── db_connection.py
│   ├── environment.py
│   ├── exceptions.py
│   ├── logger_config.py
│   ├── security.py
│   └── utils.py
├── wsdl/
│   ├── codigos.wsdl
│   ├── facturacion.wsdl
│   ├── LEEME.md
│   └── sincronizacion.wsdl
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

## 📀 Ejecución Local

Para ejecutar el microservicio localmente, sigue los siguientes pasos:

1.  **Instala las dependencias:**

```shell
pip install -r requirements.txt
```

2.  **Configura el entorno:** Crea el archivo `.env` con `HOST`, `PORT`, `APP_ENV`, `SECRET_KEY`, `ALGORITHM`, `TARGET_TIMEZONE`, `ROOT_PATH`, `API_URL`, las tablas `DYNAMODB_TABLE_NAME_*` y la conexión al SIAT (`SIAT_*`).

3.  **Ejecuta el servidor de la API:**

```shell
python main.py
```

4.  **Ejecuta las pruebas:**

```shell
python -m pytest -q
pylint --fail-under=10.0 .
```

La verificación completa: `python tools/verification/verify_service.py services/billing` desde la raíz del repositorio.

-----

## 👤 Creado Por

**Rafael Ríos Bascón**
[raforios@gmail.com](mailto:raforios@gmail.com)
