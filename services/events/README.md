# 🔔 Events-Service 📊

Bienvenido al microservicio de gestión de eventos, una pieza fundamental en la arquitectura de la API **SMARTBEAR**. Este servicio es el centro neurálgico para la recolección, el registro y el monitoreo de eventos críticos del sistema, proporcionando una fuente única de verdad para la auditoría y la trazabilidad del uso de la API.

-----

## 🎯 Propósito Principal

El **Events-Service** está diseñado para ser la columna vertebral de la observabilidad y la seguridad de la plataforma. Su propósito principal es capturar y centralizar información sobre cambios de datos y actividad de usuarios, lo que facilita la auditoría, la depuración y el análisis del rendimiento. Sus funcionalidades clave incluyen:

  * **Auditoría de Datos:** Proporciona un registro inmutable de las modificaciones (creación, actualización y eliminación) en las tablas de la base de datos de otros microservicios.
  * **Registro de Uso:** Captura detalles de cada llamada a la API, incluyendo el usuario, el microservicio accedido, la dirección IP, el tiempo de respuesta y el estado de la petición.
  * **Análisis y Reportes:** Actúa como una fuente de datos centralizada que permite generar reportes detallados sobre el comportamiento del sistema y el uso de los usuarios.

-----

## 🛠️ Tecnologías Utilizadas

Este microservicio comparte el mismo enfoque en rendimiento y robustez que el resto de tu arquitectura, utilizando las siguientes tecnologías:

  * **Lenguaje:** Python 3.13 🐍
  * **Framework Web:** FastAPI ✨
  * **Servidor ASGI:** Uvicorn 🚀
  * **AWS SDK:** Boto3 (para la gestión de datos)
  * **Base de Datos:** AWS DynamoDB
  * **Validación de Datos:** Pydantic
  * **Contenedorización:** Docker 🐳
  * **Plataforma Cloud:** AWS Lambda y AWS CLI (para el despliegue a través de un script shell)

-----

## 🚀 Endpoints de la API

A continuación se listan los endpoints principales de la API, agrupados por su funcionalidad para una mejor referencia.

### Gestión de Eventos

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/v1/events/audit` | Registra un evento de auditoría sobre una modificación de datos. |
| `GET` | `/v1/events/audit` | Obtiene una lista paginada de registros de auditoría con filtros opcionales. |
| `POST` | `/v1/events/usage-log` | Registra un evento de uso de la API. |
| `GET` | `/v1/events/usage-log` | Obtiene una lista paginada de registros de uso con filtros opcionales. |

-----

## 🗂️ Estructura del Microservicio

```txt
events/
├── controllers/
│   ├── __init__.py
│   ├── audit.py
│   └── usage_log.py
├── models/
│   ├── __init__.py
│   ├── audit.py
│   └── usage_log.py
├── routes/
│   ├── __init__.py
│   ├── audit.py
│   └── usage_log.py
├── schemas/
│   ├── __init__.py
│   ├── audit.py
│   └── usage_log.py
├── services/
│   ├── __init__.py
│   ├── api_exceptions.py
│   ├── audit.py
│   ├── crud.py
│   ├── db_connection.py
│   ├── environment.py
│   ├── exceptions.py
│   ├── logger_config.py
│   ├── security.py
│   ├── usage_log.py
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

2.  **Configura la base de datos:** Asegúrate de que tienes una instancia de **DynamoDB local** en ejecución (por ejemplo, con **Docker**) y que las variables de conexión están correctamente configuradas en el archivo `.env`.

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
