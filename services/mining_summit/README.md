# Mining Summit Service

Microservicio backend para el evento **"La Cumbre Minera"**. Provee endpoints
JWT-protegidos para registrar participantes, marcar asistencia diaria y
generar reportes (listados y agregaciones estadísticas) que alimentan al
frontend Vanilla JS publicado en S3 + CloudFront.

## Stack

- Python 3.14 + FastAPI + Uvicorn
- AWS Lambda (handler `Mangum`)
- AWS DynamoDB (`boto3`)
- Autenticación JWT delegada al servicio AUTH (validación de Bearer token).

## Estructura

```text
mining_summit/
├── controllers/        # Orquestación entre rutas y servicios.
├── models/             # TypedDict de items DynamoDB.
├── routes/             # Endpoints FastAPI.
├── schemas/            # Modelos Pydantic V2 (request / response / query).
├── services/           # Lógica de negocio + helpers compartidos.
├── tests/              # Tests con pytest.
├── .env                # Variables locales.
├── Dockerfile          # Build para Lambda.
├── deploy.config       # Variables de despliegue.
├── dynamodb.sh         # Provisión local de DynamoDB.
├── main.py             # Entrypoint FastAPI.
└── requirements.txt
```

## Tablas DynamoDB

| Tabla | Partition Key | Sort Key | Notas |
|---|---|---|---|
| `mining_summit_participants` | `ci` (S) | — | CI único por participante. |
| `mining_summit_attendances` | `ci` (S) | `attendance_date` (S, `YYYY-MM-DD`) | El composite key garantiza una asistencia por persona por día. |

> Las fechas se calculan en `America/La_Paz` (variable `TARGET_TIMEZONE`).

## Variables de entorno

| Variable | Obligatoria | Descripción |
|---|---|---|
| `HOST`, `PORT` | sí | Bind para Uvicorn. |
| `APP_ENV` | no | `development` / `staging` / `production`. |
| `ROOT_PATH` | no | Prefijo cuando corre detrás de API Gateway. |
| `SECRET_KEY`, `ALGORITHM` | sí | Validación del JWT emitido por AUTH. |
| `TARGET_TIMEZONE` | sí | Por defecto `America/La_Paz`. |
| `DYNAMODB_REGION` | sí | Región de DynamoDB. |
| `DYNAMODB_ENDPOINT_URL` | no | Endpoint local (`http://localhost:3100`). |
| `DYNAMODB_TABLE_NAME_PARTICIPANTS` | sí | Nombre de la tabla de participantes. |
| `DYNAMODB_TABLE_NAME_ATTENDANCES` | sí | Nombre de la tabla de asistencias. |
| `CORS_ALLOWED_ORIGINS` | no | Lista CSV de orígenes exactos adicionales (terceros). Vacío por defecto. |
| `CORS_ALLOWED_ORIGIN_REGEX` | no | Regex de orígenes permitidos. Default cubre `*.bearsoft.com.bo`, `*.cloudfront.net`, `*.mineria.gob.bo` y `localhost`. |

## Endpoints (todos requieren `Authorization: Bearer <jwt>`)

### Participantes

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/v1/mining-summit/participants` | Registra un participante y crea su primera asistencia. |
| `GET` | `/v1/mining-summit/participants` | Lista paginada con filtros (`department`, `company`, `registered_from`, `registered_to`). |
| `GET` | `/v1/mining-summit/participants/{ci}` | Detalle por CI. |

### Asistencias

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/v1/mining-summit/attendances` | Registra asistencia. Si el CI no existe, crea al participante on-the-fly (requiere `first_name` y `last_name`). |
| `GET` | `/v1/mining-summit/attendances` | Lista filtrable por `ci`, `date_from`, `date_to`. |

### Reportes

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/v1/mining-summit/reports/stats?group_by=department\|company` | Conteo y porcentaje por dimensión, listo para el chart del frontend. |

## Reglas de negocio relevantes

1. `ci` es la clave única del participante.
2. Al registrar un participante se crea automáticamente su primera asistencia
   con la fecha y hora de Bolivia.
3. Una asistencia por CI por día (idempotencia garantizada por la composite key).
   Un segundo POST en el mismo día responde **409 Conflict**.
4. El registro de asistencia auto-crea al participante si el CI no existe,
   siempre que el payload incluya `first_name` y `last_name`.
5. Los reportes estadísticos agrupan por `department` o `company`, ubicando
   los valores ausentes bajo la etiqueta **"Sin especificar"**.

## Ejecución local

```bash
# 1. Levantar DynamoDB local con las tablas requeridas.
./dynamodb.sh

# 2. Instalar dependencias y arrancar la API.
pip install -r requirements.txt
python main.py
```

La documentación interactiva queda disponible en `http://localhost:3010/docs`.
