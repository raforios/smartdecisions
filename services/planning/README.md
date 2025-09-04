# 📅 Planning-Service 📝

Bienvenido al microservicio de planificación, un componente clave dentro de la arquitectura de la API **SMARTBEAR**. Este servicio es el centro de control para la gestión y el seguimiento de las planificaciones operativas, permitiendo la asignación de rutas, equipos y materiales a tareas específicas.

---

## 🎯 Propósito Principal

El **Planning-Service** está diseñado para ser el motor de la planificación operativa. Su propósito principal es organizar y gestionar las actividades del personal y los recursos, facilitando el control y la visibilidad de las tareas. Sus funcionalidades clave incluyen:

  * **Gestión de Planificaciones:** Permite la creación, actualización, eliminación y recuperación de planes operativos, incluyendo fechas de inicio y fin, y un estado de seguimiento.
  * **Gestión de Detalles de Planificación:** Facilita la creación, actualización y eliminación de los detalles específicos de cada planificación, como la ruta, el equipo y el servicio asociado.
  * **Control de Materiales:** Facilita el registro de la asignación, el uso y la devolución de materiales específicos para cada tarea planificada.
  * **Consulta por Período y Filtro:** Proporciona endpoints para consultar planificaciones por número de semana, por una fecha específica o a través de un filtro detallado (por ID de compañía, equipo, etc.).

---

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

---

## 🚀 Endpoints de la API

A continuación se listan los endpoints principales de la API, agrupados por su funcionalidad para una mejor referencia.

### Gestión de Planificaciones

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/v1/plannings/` | Crea una nueva planificación. |
| `GET` | `/v1/plannings/filter` | Filtra planificaciones por ID de compañía, equipo, servicio o ruta planificada. |
| `GET` | `/v1/plannings/{planning_id}` | Recupera una planificación específica por su ID, incluyendo sus detalles. |
| `PUT` | `/v1/plannings/{planning_id}` | Actualiza los datos de una planificación existente. |
| `DELETE`| `/v1/plannings/{planning_id}` | Elimina una planificación y sus detalles, solo si está en estado `ACTIVE`. |
| `GET` | `/v1/plannings/weekly/{week_number}` | Recupera todas las planificaciones para un número de semana específico. |
| `GET` | `/v1/plannings/daily/{planning_date}` | Recupera todas las planificaciones activas en una fecha determinada. |

### Gestión de Detalles de Planificación

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/v1/plannings/{planning_id}/details` | Crea un nuevo detalle para una planificación existente. |
| `PATCH`| `/v1/plannings/{planning_id}/details/{planning_detail_id}` | Actualiza un detalle de planificación con datos parciales. |
| `DELETE`| `/v1/plannings/{planning_id}/details/{planning_detail_id}` | Elimina un detalle de planificación. |

### Gestión de Materiales Asignados

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/v1/plannings/{planning_id}/details/{planning_detail_id}/materials` | Asigna un nuevo material a un detalle de planificación. |
| `GET` | `/v1/plannings/{planning_id}/details/{planning_detail_id}/materials` | Recupera todas las asignaciones de material para un detalle de planificación. |
| `PATCH`| `/v1/plannings/{planning_id}/details/{planning_detail_id}/materials/{material_assignment_id}`| Actualiza las cantidades usadas y devueltas para una asignación de material. |
| `DELETE`| `/v1/plannings/{planning_id}/details/{planning_detail_id}/materials/{material_assignment_id}`| Elimina una asignación de material específica. |

---

## 🗂️ Estructura del Microservicio

```txt
planning/
├── controllers/
│   ├── __init__.py
│   └── planning.py
├── models/
│   ├── __init__.py
│   └── planning.py
├── routes/
│   ├── __init__.py
│   └── planning.py
├── schemas/
│   ├── __init__.py
│   └── planning.py
├── services/
│   ├── __init__.py
│   ├── api_exceptions.py
│   ├── crud.py
│   ├── db_connection.py
│   ├── exceptions.py
│   ├── logger_config.py
│   ├── planning.py
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
