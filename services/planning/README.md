# 📅 Planning-Service 📝

Bienvenido al microservicio de planificación, un componente clave dentro de la arquitectura de la API **SMARTBEAR**. Este servicio es el centro de control para la gestión y el seguimiento de las planificaciones operativas, permitiendo la asignación de rutas, equipos y materiales a tareas específicas.

-----

## 🎯 Propósito Principal

El **Planning-Service** está diseñado para ser el motor de la planificación operativa. Su propósito principal es organizar y gestionar las actividades del personal y los recursos, facilitando el control y la visibilidad de las tareas. Sus funcionalidades clave incluyen:

  * **Gestión de Planificaciones:** Permite la creación, almacenamiento y recuperación de planes operativos, incluyendo fechas de inicio y fin, y un estado de seguimiento.
  * **Asignación de Rutas y Equipos:** Vincula cada planificación a una ruta predefinida (gestionada por el microservicio de `LOCALIZATION`) y a un equipo de trabajo.
  * **Control de Materiales:** Facilita el registro de la asignación y el uso de materiales específicos para cada tarea planificada.
  * **Consulta por Período:** Proporciona endpoints para consultar planificaciones por número de semana o por una fecha específica.

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

A continuación se listan los endpoints principales de la API, que facilitan la interacción con el servicio.

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/v1/plannings/` | Crea una nueva planificación. |
| `GET` | `/v1/plannings/{planning_id}` | Recupera una planificación específica por su ID, incluyendo sus detalles. |
| `PUT` | `/v1/plannings/{planning_id}` | Actualiza los datos de una planificación existente. |
| `GET` | `/v1/plannings/weekly/{week_number}` | Recupera todas las planificaciones para un número de semana específico. |
| `GET` | `/v1/plannings/daily/{planning_date}` | Recupera todas las planificaciones activas en una fecha determinada. |

-----

## 🗂️ Estructura del Microservicio

```txt
planning/
└── controllers/
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
│   └── security.py
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
