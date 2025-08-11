# 🗺️ Localization-Service 🧭

Bienvenido al microservicio de localización, un componente esencial dentro de la arquitectura de la API **SMARTBEAR**. Este servicio es el centro de control para la gestión y el análisis de todos los datos geográficos, permitiendo el seguimiento de rutas, el control de asistencia y la obtención de información estadística clave.

---

## 🎯 Propósito Principal

El **Localization-Service** está diseñado para ser la fuente de verdad para la información de ubicación. Su propósito principal es gestionar y analizar datos espaciales, facilitando la toma de decisiones y el control operacional. Sus funcionalidades clave incluyen:

* **Gestión de Rutas Planificadas:** Permite la creación, almacenamiento y recuperación de rutas predefinidas por el usuario, estableciendo trayectos con puntos específicos de latitud y longitud.
* **Creación Dinámica de Rutas:** Registra y genera "rutas ejecutadas" en tiempo real a partir de los datos de localización enviados continuamente desde la aplicación móvil.
* **Registro de Asistencia:** Procesa los **`check-in`** y **`check-out`** del personal en puntos geográficos asignados, vinculando la asistencia a las rutas planificadas.
* **Análisis y Estadísticas:** Proporciona endpoints para obtener análisis comparativos entre las rutas planificadas y las ejecutadas, así como estadísticas detalladas sobre los puntos visitados por usuario en un rango de fechas.

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

A continuación se listan los endpoints principales de la API, que facilitan la interacción con el servicio.

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/v1/localization/routes/planned` | Crea una nueva ruta planificada con sus puntos asociados. |
| `GET` | `/v1/localization/routes/planned/{planned_route_id}` | Recupera una ruta planificada específica y sus puntos por su ID. |
| `POST` | `/v1/localization/routes/executed` | Inicia una nueva ruta ejecutada, opcionalmente vinculada a una ruta planificada. |
| `POST` | `/v1/localization/routes/executed/points` | Registra un nuevo punto de localización para una ruta ejecutada en curso. |
| `GET` | `/v1/localization/statistics/users/{user_id}/points-visited` | Obtiene estadísticas de puntos visitados para un usuario en un rango de fechas. |
| `GET` | `/v1/localization/statistics/route-comparisons/{planned_route_id}` | Compara una ruta planificada con las rutas ejecutadas asociadas. |
| `POST` | `/v1/localization/attendances` | Registra o actualiza un registro de asistencia (check-in/check-out). |

---

## 🗂️ Estructura del Microservicio

```txt
localization/
└── controllers/
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
│   └── localization.py
│   ├── logger_config.py
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

---

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

---

## 👤 Creado Por

**Rafael Ríos Bascón**
[raforios@gmail.com](mailto:raforios@gmail.com)