# 🛒 Trade-Service 📈

Bienvenido al microservicio de **Trade Marketing**, el corazón transaccional de la arquitectura **SMARTBEAR**. Este servicio gestiona la ejecución en el Punto de Venta (PDV), incluyendo catálogos de productos, control de inventarios, planificación de visitas y el registro detallado de actividades comerciales como ventas, reposiciones, merchandising y evidencia fotográfica.

-----

## 🎯 Propósito Principal

El **Trade-Service** tiene como objetivo digitalizar y optimizar la ejecución en campo. Su propósito es permitir que el personal de Trade Marketing (supervisores, repositores, impulsadoras) registre información veraz y en tiempo real sobre lo que sucede en cada tienda. Sus funcionalidades clave incluyen:

* **Catálogo Maestro:** Gestión centralizada de **Productos** (con generación atómica de SKUs) y **Puntos de Venta** (PDVs), incluyendo la asignación lógica entre ellos.
* **Control de Inventarios:** Manejo de inventarios locales en cada PDV, con soporte para lotes, fechas de vencimiento y alertas de productos con fecha corta (`Short Date`).
* **Agenda de Campo (Planning):** Orquesta la planificación de visitas (`Trade Planning`), integrando la asignación de usuarios y PDVs. Soporta visitas planificadas y **Ad-Hoc** (fuera de ruta), así como la justificación de inasistencias.
* **Gestión de Impulsos:** Registra actividades de promoción y ventas directas, manejando inventarios iniciales y finales por visita (`Inventory Start/End`) y ventas con evidencia fotográfica.
* **Reposición y Merchandising:** Controla la reposición de productos en góndola, registrando inventarios, recepciones y "Fotos de Éxito". Además, gestiona actividades complementarias como **Bandeos**, **Puntos Promocionales** y **Reportes de Competencia**.
* **Reportes Avanzados:** Generación de reportes ejecutivos para la toma de decisiones:
    * **Cumplimiento:** KPIs de efectividad de visitas (Planificado vs. Ejecutado).
    * **Alertas de Inventario:** Semáforo de Stockouts y productos por vencer.
    * **Ventas:** Data detallada enriquecida con contexto de usuario y ubicación (integración con Localization).
    * **Merchandising:** Consolidado de actividades de visibilidad y competencia.
    * **Galería Fotográfica:** Repositorio centralizado de toda la evidencia visual capturada en campo.

-----

## 🛠️ Tecnologías Utilizadas

Este microservicio ha sido desarrollado con un enfoque en el rendimiento, la robustez y la integración con la nube, escalable y orientada a eventos:

  * **Lenguaje:** Python 3.13 🐍
  * **Framework Web:** FastAPI ✨
  * **Servidor ASGI:** Uvicorn 🚀
  * **ORM:** SQLAlchemy
  * **Base de Datos:** MySQL
  * **Validación de Datos:** Pydantic
  * **Contenedorización:** Docker 🐳
  * **Plataforma Cloud:** AWS Lambda y AWS CLI (para el despliegue a través de un script shell)

-----

## 🚀 Endpoints de la API

A continuación se listan los **endpoints** vigentes, organizados por módulos funcionales y prefijos reales de la API.

### 1. Catálogo Productos (`/v1/products`)
| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/v1/products` | Crea un **Producto** con generación atómica de SKU (alimenta `t_products` y `t_sku_sequencer`). |
| `GET` | `/v1/products` | Lista productos con filtros y paginación. |
| `GET` | `/v1/products/{id}` | Obtiene detalle de un producto. |
| `PATCH` | `/v1/products/{id}` | Actualiza información de un producto. |
| `DELETE` | `/v1/products/{id}` | Elimina un producto. |
| `POST` | `/v1/products/bulk-upload` | Carga masiva de productos desde CSV. |
| `POST` | `/v1/products/sku-equivalencies` | Crea mapeo de equivalencia con sistemas externos (`t_sku_equivalencies`). |
| `GET` | `/v1/products/sku-equivalencies` | Lista equivalencias de SKU. |
| `POST` | `/v1/products/sku-equivalencies/bulk-upload` | Carga masiva de equivalencias. |
| `POST` | `/v1/products/pos-assignments` | Asigna un producto a un POS - Surtido (`t_trade_product_assignments_pos`). |
| `GET` | `/v1/products/pos-assignments` | Lista asignaciones de productos a POS. |
| `POST` | `/v1/products/pos-assignments/bulk-upload` | Carga masiva de asignaciones. |

### 2. Catálogo POS (`/v1/pos`)
| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/v1/pos` | Crea un **POS** con inventario inicial (`t_points_of_sale`). |
| `GET` | `/v1/pos` | Lista POS con filtros y paginación. |
| `GET` | `/v1/pos/{id}` | Obtiene detalle de un POS. |
| `PUT` | `/v1/pos/{id}` | Actualiza información de un POS. |
| `DELETE` | `/v1/pos/{id}` | Elimina un POS. |
| `POST` | `/v1/pos/bulk-upload` | Carga masiva de POS desde CSV. |
| `POST` | `/v1/pos/{id}/inventory` | Agrega un ítem de inventario local (`t_pos_inventory`). |
| `GET` | `/v1/pos/{id}/inventory` | Lista el inventario actual de un POS. |
| `PATCH` | `/v1/pos/inventory/{id}` | Actualiza un ítem de inventario (Stock/Lote). |
| `DELETE` | `/v1/pos/inventory/{id}` | Elimina un ítem de inventario. |
| `POST` | `/v1/pos/inventory/bulk-upload` | Carga masiva de inventario (CSV). |

### 3. Common Utils (`/v1/common`)
| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/v1/common/photos/upload` | Sube una foto asociada a cualquier entidad (`t_trade_photos`). |
| `DELETE` | `/v1/common/photos/{id}` | Elimina una foto por ID. |

### 4. Planificación y Agenda (`/v1/trade`)
| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/v1/trade/planning` | Crea una entrada de planificación vinculada a POS (`t_trade_planning`). |
| `GET` | `/v1/trade/planning` | Lista planificaciones con filtros. |
| `GET` | `/v1/trade/planning/{id}` | Obtiene detalle de una planificación. |
| `PUT` | `/v1/trade/planning/{id}` | Actualiza información de planificación. |
| `DELETE` | `/v1/trade/planning/{id}` | Elimina una planificación. |
| `POST` | `/v1/trade/planning/adhoc` | Registra una visita fuera de ruta (Ad-Hoc). |
| `PATCH` | `/v1/trade/planning/{id}/justify` | Justifica la no-asistencia o cancelación. |
| `POST` | `/v1/trade/attendances/check-in` | Registro de entrada (Check-In) al POS (`t_trade_attendances`). |
| `PATCH` | `/v1/trade/attendances/{id}/check-out` | Registro de salida (Check-Out) y cálculo de duración. |

### 5. Impulsos y Ventas (`/v1/impulses`)
| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/v1/impulses/promotions` | Crea una promoción/bandeo - Catálogo (`t_trade_promotions`). |
| `GET` | `/v1/impulses/promotions` | Lista promociones registradas. |
| `POST` | `/v1/impulses/visit/{attendance_id}/inventory-start` | Inventario inicial de visita (`t_trade_impulse_inventory_start`). |
| `POST` | `/v1/impulses/visit/{attendance_id}/sale` | Registro de venta con evidencia (`t_trade_impulse_sales`). Acepta campo opcional `observations`. |
| `POST` | `/v1/impulses/visit/{attendance_id}/inventory-end` | Inventario final de visita (`t_trade_impulse_inventory_end`). |
| `GET` | `/v1/impulses/sales` | **(2026-05-28)** Listado de ventas filtrable por `company_id`, `client_company_id`, `pos_id`, `user_id`, `date_from`, `date_to`, todos opcionales. |
| `GET` | `/v1/pos/{pos_id}/stock` | **(2026-05-28)** Stock disponible por producto en el PDV. Si la visita más reciente está abierta usa `inventory_start - sum(ventas)`; si está cerrada usa `inventory_end`. |
| `GET` | `/v1/pos/{pos_id}/inventory/latest` | Último inventario registrado para el PDV (start o end). |

### 6. Reposición y Complementarios (`/v1/replenishment`)
| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/v1/replenishment/visit/{id}/report` | Reporte de éxito de reposición (`t_trade_replenishment_reports`). |
| `POST` | `/v1/replenishment/visit/{id}/inventory` | Inventario detallado en góndola (`t_trade_replenishment_inventory`). |
| `POST` | `/v1/replenishment/visit/{id}/reception` | Registro de recepción de mercadería (`t_trade_replenishment_receptions`). |
| `POST` | `/v1/replenishment/complementary/visit/{id}/bandeo` | Reporte de Bandeos (`t_trade_complementary_bandeo_header`). |
| `POST` | `/v1/replenishment/complementary/visit/{id}/promo-point` | Implementación de Punto Promocional (`t_trade_complementary_promo_point`). |
| `POST` | `/v1/replenishment/complementary/competition` | Reporte general de competencia (`t_trade_complementary_competition`). |

### 7. Reportes y Analytics (`/v1/reports`)
| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `GET` | `/v1/reports/compliance` | KPI de cumplimiento (Planificado vs Ejecutado). |
| `GET` | `/v1/reports/inventory-alerts` | Alertas de stock (Quiebres y Fechas Cortas). |
| `GET` | `/v1/reports/sales` | Data plana de ventas enriquecida para BI. |
| `GET` | `/v1/reports/merchandising` | Consolidado de Bandeos, Competencia y Puntos Promocionales. |
| `GET` | `/v1/reports/photographic` | Galería centralizada de evidencias fotográficas. |
| `GET` | `/v1/reports/attendance` | Reporte de asistencia, duración y geofencing. |

-----

## 📷 Convención de paths S3 para fotos

Las subidas de archivos pasan por el microservicio **FILES** (`POST /v1/s3/upload`),
que recibe `bucket_name` + `file_path`. Para mantener la galería ordenada y
permitir filtros por PDV/visita, usar **siempre** estas convenciones cuando
se suban archivos asociados a una venta o reposición:

| Caso | `file_path` a enviar al FILES service |
| :--- | :--- |
| Venta de impulso (foto del ticket / evidencia) | `trade/sales/impulses/{pos_id}/{attendance_id}/` |
| Reposición / reporte de éxito | `trade/sales/replenishments/{pos_id}/{attendance_id}/` |
| Recepción de mercadería (factura, remito) | `trade/replenishments/receptions/{pos_id}/{attendance_id}/` |
| Inventario inicial / final | `trade/inventories/{pos_id}/{attendance_id}/` |
| Fotos de PDV (alta del PDV) | `trade/pos/{pos_id}/` |
| Bandeos / puntos promocionales / competencia | `trade/merchandising/{pos_id}/{attendance_id}/` |

> **Cliente confirmado el 2026-05-28** (Binaria iter 3). El `bucket_name` por
> defecto es el del entorno (`BUCKET_NAME` en `.env`). El backend solo
> persiste la `file_key` devuelta por FILES; el path lo controla el frontend
> al armar la subida.

-----

## 🗂️ Estructura del Microservicio

```txt
trade/
├── controllers/
│   ├── init.py
│   ├── common.py
│   ├── impulses.py
│   ├── pos.py
│   ├── products.py
│   ├── replenishments.py
│   ├── reports.py
│   └── trade.py
├── models/
│   ├── init.py
│   ├── common.py
│   ├── impulses.py
│   ├── pos.py
│   ├── products.py
│   ├── replenishments.py
│   └── trade.py
├── routes/
│   ├── init.py
│   ├── common.py
│   ├── impulses.py
│   ├── pos.py
│   ├── products.py
│   ├── replenishments.py
│   ├── reports.py
│   └── trade.py
├── schemas/
│   ├── init.py
│   ├── common.py
│   ├── impulses.py
│   ├── pos.py
│   ├── products.py
│   ├── replenishments.py
│   ├── reports.py
│   └── trade.py
├── services/
│   ├── init.py
│   ├── api_exceptions.py
│   ├── common.py
│   ├── crud.py
│   ├── db_connection.py
│   ├── environment.py
│   ├── exceptions.py
│   ├── impulses.py
│   ├── logger_config.py
│   ├── pos.py
│   ├── products.py
│   ├── replenishments.py
│   ├── reports.py
│   ├── security.py
│   ├── trade.py
│   └── utils.py
├── .dockerignore
├── .env
├── .gitignore
├── deploy.config
├── Dockerfile
├── main.py
├── README.md
└── requirements.txt
```

-----

## 📀 Ejecución Local

Para desplegar el servicio en tu entorno de desarrollo:

1.  **Instala las dependencias:**

```shell
pip install -r requirements.txt
```

2.  **Configura las Variables de Entorno:** Asegúrate de tener el archivo `.env` con las credenciales de base de datos y las URLs de los microservicios externos (`LOCALIZATION_SERVICE_URL`, `FILES_SERVICE_URL`).

3.  **Ejecuta el servidor:**

```shell
python main.py
```

*La API estará disponible en `http://localhost:3000/docs`.*

-----

## 👤 Creado Por

**Rafael Ríos Bascón**
[raforios@gmail.com](mailto:raforios@gmail.com)
