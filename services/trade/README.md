# 🛒 Trade-Service 📈

Bienvenido al microservicio de **Trade Marketing**, el corazón transaccional de la arquitectura **SMARTBEAR**. Este servicio gestiona la ejecución en el Punto de Venta (PDV), incluyendo catálogos de productos, control de inventarios, planificación de visitas y el registro detallado de actividades comerciales como ventas, reposiciones e impulsos.

-----

## 🎯 Propósito Principal

El **Trade-Service** tiene como objetivo digitalizar y optimizar la ejecución en campo. Su propósito es permitir que el personal de Trade Marketing (supervisores, repositores, impulsadoras) registre información veraz y en tiempo real sobre lo que sucede en cada tienda. Sus funcionalidades clave incluyen:

  * **Catálogo Maestro:** Gestión centralizada de **Productos** (con generación atómica de SKUs) y **Puntos de Venta** (PDVs), incluyendo la asignación lógica entre ellos.
  * **Control de Inventarios:** Manejo de inventarios locales en cada PDV, con soporte para lotes, fechas de vencimiento y alertas de productos con fecha corta (`Short Date`).
  * **Agenda de Campo (Planning):** Orquesta la planificación de visitas (`Trade Planning`), integrando la asignación de usuarios y PDVs. Soporta visitas planificadas y **Ad-Hoc** (fuera de ruta), así como la justificación de inasistencias.
  * **Gestión de Impulsos:** Registra actividades de promoción y ventas directas, manejando inventarios iniciales y finales por visita (`Inventory Start/End`), promociones tipo "Bandeo" y ventas con evidencia fotográfica.
  * **Reposición (Replenishment):** Controla la reposición de productos en góndola, registrando inventarios detallados, recepciones de mercadería y reportes fotográficos de exhibición ("Foto de Éxito").
  * **Inteligencia de Mercado:** Módulos para registrar precios y actividades de la competencia.
  * **Reportes Avanzados:** Generación de reportes ejecutivos para la toma de decisiones:
    * **Cumplimiento:** KPIs de efectividad de visitas (Planificado vs. Ejecutado).
    * **Alertas de Inventario:** Semáforo de Stockouts y productos por vencer.
    * **Ventas:** Data detallada enriquecida con contexto de usuario y ubicación (integración con Localization).

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

A continuación se listan los principales **endpoints**, organizados por módulos funcionales.

### 1. Catálogos (Productos y PDVs)

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/v1/trade/products` | Crea un nuevo **Producto** generando automáticamente su SKU atómico. |
| `GET` | `/v1/trade/products/{product_id}` | Obtiene el detalle de un producto. |
| `GET` | `/v1/trade/products` | Lista productos con filtros (categoría, nombre). |
| `POST` | `/v1/trade/pos` | Crea un nuevo **Punto de Venta** con su inventario inicial transaccional. |
| `GET` | `/v1/trade/pos` | Lista PDVs con filtros y paginación. |
| `POST` | `/v1/trade/products/pos-assignments` | Asigna un producto a un PDV (Surtido). |

### 2. Planificación (Agenda)

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/v1/trade/planning` | Crea una entrada de **Planificación** (Agenda) vinculando Usuario y PDV. |
| `POST` | `/v1/trade/planning/adhoc` | Registra una visita no planificada (**Ad-Hoc**) con justificación. |
| `PATCH`| `/v1/trade/planning/{planning_id}/workload` | Actualiza la carga laboral (Check-In/Out) y calcula tiempos efectivos. |
| `PATCH`| `/v1/trade/planning/{planning_id}/justify` | Justifica la no-visita o cancelación de una agenda. |

### 3. Impulsos (Promociones)

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/v1/impulses/promotions` | Crea una Promoción (**Bandeo**) con lista de SKUs asociados. |
| `POST` | `/v1/impulses/impulse/visit/{id}/inventory-start` | Registra el inventario inicial al llegar al PDV. |
| `POST` | `/v1/impulses/impulse/visit/{id}/sale` | Registra una **Venta** con detalle de productos y foto de evidencia. |
| `POST` | `/v1/impulses/impulse/visit/{id}/inventory-end` | Registra el inventario final al terminar la visita. |

### 4. Reposición (Replenishment)

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/v1/replenishment/visit/{id}/report` | Registra el reporte de visita (Fotos de éxito y comentarios). |
| `POST` | `/v1/replenishment/visit/{id}/inventory` | Registra el levantamiento de **Inventario en Góndola** (Lotes, Fechas, Stock). |
| `POST` | `/v1/replenishment/visit/{id}/reception` | Registra la recepción de mercadería en el PDV. |
| `POST` | `/v1/replenishment/complementary/competition` | Reporta actividades de la **Competencia** (Precios, Exhibiciones). |

### 5. Reportes y Analytics

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `GET` | `/v1/reports/compliance` | Reporte de **Cumplimiento**: Eficiencia de rutas y carga laboral (KPIs). |
| `GET` | `/v1/reports/inventory-alerts` | Reporte de **Alertas**: Semáforo de Quiebres de Stock y Fechas Cortas. |
| `GET` | `/v1/reports/sales` | Reporte de **Ventas Detallado**: Tabla plana para BI, enriquecida con datos de Localization. |

-----

## 🗂️ Estructura del Microservicio

```txt
trade/
├── controllers/
│   ├── init.py
│   ├── impulses.py
│   ├── pos.py
│   ├── products.py
│   ├── replenishments.py
│   ├── reports.py
│   └── trade.py
├── models/
│   ├── init.py
│   ├── impulses.py
│   ├── pos.py
│   ├── products.py
│   ├── replenishments.py
│   └── trade.py
├── routes/
│   ├── init.py
│   ├── impulses.py
│   ├── pos.py
│   ├── products.py
│   ├── replenishments.py
│   ├── reports.py
│   └── trade.py
├── schemas/
│   ├── init.py
│   ├── impulses.py
│   ├── pos.py
│   ├── products.py
│   ├── replenishments.py
│   ├── reports.py
│   └── trade.py
├── services/
│   ├── init.py
│   ├── api_exceptions.py
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
