# 🗺️ Localization-Service 🧭

Bienvenido al microservicio de localización, un componente esencial dentro de la arquitectura de la API **SMARTBEAR**. Este servicio es el centro de control para la gestión y el análisis de todos los datos geográficos, permitiendo el seguimiento de rutas, el control de asistencia y la obtención de información estadística clave.

-----

## 🎯 Propósito Principal

El **Localization-Service** está diseñado para ser la fuente de verdad para la información de ubicación. Su propósito principal es gestionar y analizar datos espaciales, facilitando la toma de decisiones y el control operacional. Sus funcionalidades clave incluyen:

  * **Gestión de Rutas Planificadas:** Permite la creación, almacenamiento y recuperación de rutas predefinidas por el usuario, estableciendo trayectos con puntos específicos de latitud y longitud. También incluye filtros avanzados para facilitar la búsqueda, así como la actualización y eliminación de registros.
  * **Creación Dinámica de Rutas:** Registra y genera "rutas ejecutadas" en tiempo real a partir de los datos de localización enviados continuamente desde la aplicación móvil. El inicio de una ruta ejecutada está validado para garantizar que la ruta planificada asociada se encuentre en estado `ACTIVE`.
  * **Registro de Asistencia:** Procesa los **`check-in`** y **`check-out`** del personal en puntos geográficos asignados, vinculando la asistencia a las rutas planificadas. Este proceso también valida que la ruta planificada se encuentre en estado `ACTIVE`.
  * **Análisis y Estadísticas:** Proporciona **endpoints** para obtener análisis comparativos detallados entre las rutas planificadas y las ejecutadas, así como estadísticas de puntos visitados por usuario en un rango de fechas.
  * **Carga Masiva:** Permite la importación de datos de rutas planificadas a gran escala a través de archivos CSV, simplificando la creación de múltiples registros.

-----

## 🛠️ Tecnologías Utilizadas

Este microservicio ha sido desarrollado con un enfoque en el rendimiento, la robustez y la integración con la nube:

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

A continuación se listan los **endpoints** principales de la API, agrupados por su funcionalidad para una mejor referencia.

### Rutas Planificadas

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/v1/localization/routes/planned` | Crea una nueva **ruta planificada** con sus puntos asociados. |
| `GET` | `/v1/localization/routes/planned` | Recupera una lista de todas las **rutas planificadas**. |
| `GET` | `/v1/localization/routes/planned/filter` | Filtra **rutas planificadas** por código, nombre, estado, o ID de compañía. |
| `GET` | `/v1/localization/routes/planned/{planned_route_id}` | Recupera una **ruta planificada** específica y sus puntos por su ID. |
| `PATCH`| `/v1/localization/routes/planned/{planned_route_id}` | Actualiza campos específicos de una **ruta planificada** (ej. nombre, descripción, código). |
| `PATCH`| `/v1/localization/routes/planned/{planned_route_id}/status` | Actualiza el estado de una **ruta planificada** (`ACTIVE`, `INACTIVE`, `IN CREATION`). |
| `DELETE`| `/v1/localization/routes/planned/{planned_route_id}` | Elimina una **ruta planificada** y sus puntos. |
| `POST` | `/v1/localization/routes/planned/{planned_route_id}/points`| Añade un nuevo punto a una **ruta planificada**. |
| `DELETE`| `/v1/localization/routes/planned/{planned_route_id}/points/{planned_point_id}`| Elimina un punto específico de una **ruta planificada**. |
| `POST`| `/v1/localization/routes/planned/bulk-upload` | Carga masivamente rutas planificadas a partir de un archivo CSV. |

### Rutas Ejecutadas

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/v1/localization/routes/executed` | Inicia una nueva **ruta ejecutada**, opcionalmente vinculada a una ruta planificada. |
| `POST` | `/v1/localization/routes/executed/points` | Registra un nuevo punto de localización para una **ruta ejecutada**. |
| `PATCH`| `/v1/localization/routes/executed/{executed_route_id}` | Actualiza el tiempo de finalización (`end_time`) de una **ruta ejecutada**. |

### Asistencia

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/v1/localization/attendances` | Registra un nuevo `check-in` o actualiza un registro de asistencia. |
| `PATCH`| `/v1/localization/attendances/{attendance_id}` | Actualiza un registro de asistencia con el tiempo de salida (`check-out`). |

### Estadísticas y Análisis

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `GET` | `/v1/localization/statistics/users/{user_id}/points-visited`| Obtiene estadísticas de puntos visitados para un usuario en un rango de fechas. |
| `GET` | `/v1/localization/statistics/route-comparisons/{planned_route_id}`| Compara una **ruta planificada** con las **rutas ejecutadas** asociadas para obtener datos estadísticos. |
| `GET` | `/v1/localization/routes/comparison/{planned_route_id}` | Obtiene una comparación detallada entre una **ruta planificada** y sus **rutas ejecutadas** para visualización. |

-----

## 🗂️ Estructura del Microservicio

```txt
localization/
├── controllers/
│   ├── init.py
│   └── localization.py
├── models/
│   ├── init.py
│   └── localization.py
├── routes/
│   ├── init.py
│   └── localization.py
├── schemas/
│   ├── init.py
│   └── localization.py
├── services/
│   ├── init.py
│   ├── api_exceptions.py
│   ├── crud.py
│   ├── db_connection.py
│   ├── exceptions.py
│   ├── localization.py
│   ├── logger_config.py
│   ├── security.py
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

Para ejecutar el microservicio localmente, sigue los siguientes pasos:

1.  **Instala las dependencias:**

    ```shell
    pip install -r requirements.txt
    ```

2.  **Configura la base de datos:** Asegúrate de que tienes un servidor MySQL en ejecución y que las variables de conexión están correctamente configuradas en el archivo `.env`.

3.  **Ejecuta el servidor de la API:**

    ```shell
    python main.py
    ```

    O si el entorno lo requiere:

    ```shell
    python3 main.py
    ```

-----

## 👤 Creado Por

**Rafael Ríos Bascón**
[raforios@gmail.com](mailto:raforios@gmail.com)
