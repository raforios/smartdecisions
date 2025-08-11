# 📝 Forms-Service 📋

Bienvenido al microservicio de gestión de formularios, un componente clave dentro de la arquitectura de la API **SMARTBEAR**. Este servicio es el centro de control para la definición, captura, validación y gestión del ciclo de vida de formularios paramétricos utilizados para encuestas y otros fines.

---

## 🎯 Propósito Principal

El **Forms-Service** está diseñado para ser la interfaz principal para toda la gestión de formularios dinámicos y sus respuestas. Su propósito es facilitar la creación de formularios complejos con flujos lógicos y un sistema de revisión integrado. Sus funcionalidades clave incluyen:

* **Definición de Formularios Paramétricos:** Permite crear formularios con preguntas, opciones de respuesta y reglas de flujo complejas, todo gestionado desde la base de datos.
* **Gestión del Ciclo de Vida del Formulario:** Proporciona un proceso de revisión que permite actualizar el estado de los formularios completados (ej. `Revisado`, `Aprobado`).
* **Registro Temporal de Respuestas:** Almacena las respuestas de los usuarios de manera temporal, procesando las preguntas una por una y solo persistiendo los datos de manera definitiva cuando el formulario se finaliza.
* **Gestión de Flujos Lógicos:** Permite la navegación controlada a través de las preguntas del formulario, respetando saltos condicionales basados en las respuestas del usuario.

---

## 🛠️ Tecnologías Utilizadas

Este microservicio ha sido desarrollado con un enfoque en la flexibilidad, la eficiencia y la integración con la nube:

* **Lenguaje:** Python 3.13 🐍
* **Framework Web:** FastAPI ✨
* **Servidor ASGI:** Uvicorn 🚀
* **ORM:** SQLAlchemy
* **Base de Datos:** MySQL (Para la información permanente de formularios y respuestas)
* **Base de Datos Temporal:** DynamoDB (Para el almacenamiento temporal de las respuestas de la sesión)
* **Validación de Datos:** Pydantic
* **Contenerización:** Docker 🐳
* **Plataforma Cloud:** AWS Lambda y AWS CLI (para el despliegue a través de un script shell)

---

## 🚀 Endpoints de la API

A continuación se listan los endpoints principales de la API, que facilitan la interacción con el servicio.

### Gestión de Formularios

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/v1/forms/` | Crea un nuevo encabezado de formulario con sus preguntas. |
| `GET` | `/v1/forms/{form_id}` | Recupera un formulario completo por su ID. |
| `GET` | `/v1/forms/` | Obtiene una lista paginada de todos los encabezados de formulario. |
| `PUT` | `/v1/forms/{form_id}` | Actualiza un encabezado de formulario existente. |
| `DELETE`| `/v1/forms/{form_id}` | Elimina un formulario y toda su información asociada. |
| `POST` | `/v1/forms/{form_id}/questions/` | Crea una nueva pregunta para un formulario específico. |
| `GET` | `/v1/forms/questions/{question_id}` | Recupera una pregunta específica por su ID. |
| `PUT` | `/v1/forms/questions/{question_id}` | Actualiza una pregunta existente. |
| `DELETE`| `/v1/forms/questions/{question_id}` | Elimina una pregunta y su información asociada. |

### Gestión de Respuestas y Sesiones

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/v1/form-responses/start-session` | Inicia una nueva sesión para responder un formulario. |
| `POST` | `/v1/form-responses/submit-answer` | Envía una respuesta y obtiene la siguiente pregunta. |
| `POST` | `/v1/form-responses/get-question-to-modify` | Recupera una pregunta anterior para modificar su respuesta. |
| `PUT` | `/v1/form-responses/update-answer-in-session` | Actualiza la respuesta de una pregunta en una sesión activa. |
| `POST` | `/v1/form-responses/finalize-session` | Finaliza una sesión y guarda las respuestas en la base de datos permanente. |
| `GET` | `/v1/form-responses/{form_response_id}` | Obtiene una respuesta de formulario completa por su ID. |
| `GET` | `/v1/form-responses/` | Obtiene una lista paginada de todas las respuestas de formularios. |
| `PUT` | `/v1/form-responses/{form_response_id}/status` | Actualiza el estado de una respuesta de formulario completada. |

---

## 🗂️ Estructura del Microservicio

```text
forms/
└── controllers/
│   ├── __init__.py
│   ├── forms.py
│   └── responses.py
├── models/
│   ├── __init__.py
│   ├── forms.py
│   └── responses.py
├── routes/
│   ├── __init__.py
│   ├── forms.py
│   └── responses.py
├── schemas/
│   ├── __init__.py
│   ├── forms.py
│   └── responses.py
├── services/
│   ├── __init__.py
│   ├── crud.py
│   ├── db_connection.py
│   ├── dynamodb.py
│   ├── exceptions.py
│   ├── logger_config.py
│   └── security.py
├── .dockerignore
├── .env
├── .gitignore
├── deploy.config
├── Dockerfile
├── dynamodb.sh
├── main.py
├── README.md
└── requirements.txt
```
---

## 📀 Ejecución Local

Para ejecutar el microservicio localmente, sigue los siguientes pasos:

0.  **Configura DynamoDB para manejo de Caché:**

    ```shell
    # DynamoDB Local con Docker
    docker run -p 3100:8000 amazon/dynamodb-local
    ./dynamodb.sh
    ```

1.  **Instala las dependencias:**
    ```shell
    pip install -r requirements.txt
    ```

2.  **Configura las bases de datos:**
    * Asegúrate de tener un servidor MySQL en ejecución y que las variables de conexión estén correctamente configuradas en el archivo `.env`.
    * Asegúrate de tener una instancia local de DynamoDB en ejecución (puedes usar Docker como en el ejemplo del otro microservicio) y que las configuraciones sean correctas.

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

