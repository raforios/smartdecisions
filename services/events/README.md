# EVENTS — Events-Service

Servicio **base** de BearSoft (CLAUDE.md §4 y §7).

## Para qué sirve

Registra **quién cambió qué** (auditoría) y **cada llamada** a los servicios
(uso). Sin él, un servicio es invisible: nadie puede decir quién anuló una
nota. Los servicios no escriben aquí a mano: lo hacen los decoradores del
boilerplate, `@handle_service_errors` (uso) y `@audit_event` (auditoría).

EVENTS no se audita a sí mismo.

## Endpoints y quién puede llamarlos

| Método | Ruta | Quién |
|---|---|---|
| POST | `/v1/events/audit` | Cualquier token válido: el servicio reenvía el de la petición que registra |
| GET | `/v1/events/audit` | `ADMIN`: lista paginada con filtros |
| POST | `/v1/events/usage-log` | Cualquier token válido, igual que la auditoría |
| GET | `/v1/events/usage-log` | `ADMIN`: lista paginada con filtros |

Los roles de lectura están en `schemas/audit.py` (`READ_ROLES`).

## Qué servicios lo llaman

INGEST, ANALYTICS, OPTIMIZATION, MINING_ANALYSIS, QUOTES, AI, FINANCE,
BILLING y PARAMETERS (este último sólo por sus cambios: PUT y DELETE).

No lo llaman AUTH, FILES ni ML_FUNCTIONS: son base técnica, y registrar un
inicio de sesión, un archivo movido o un cálculo no dice nada del negocio
(Rafael, 17-oct-2026). `tools/verification/verify_checks.py` (chequeo
`events`) lo comprueba.

## Variables de entorno

Sólo entorno (CLAUDE.md §5.3):

| Variable | Qué es |
|---|---|
| `HOST`, `PORT`, `APP_ENV` | Servidor local y entorno |
| `SECRET_KEY`, `ALGORITHM` | Verificación del JWT de AUTH |
| `DYNAMODB_TABLE_NAME_AUDIT` | Tabla de auditoría (`audit_records`) |
| `DYNAMODB_TABLE_NAME_USAGE` | Tabla de uso (`usage_logs`) |

## Tablas

| Tabla | Partición | Qué guarda |
|---|---|---|
| `audit_records` | `id` (UUID) | Quién cambió qué: `microservice`, `entity_name`, `entity_id`, `action`, `user_id`, `timestamp`, `old_values`, `new_values` (`models/audit.py`) |
| `usage_logs` | `id` (UUID) | Cada llamada a un servicio: `user_app`, `microservice`, `endpoint`, `method`, `status_code`, `ip_address`, `request_body`, `response_body`, `response_time_ms`, `timestamp` (`models/usage_log.py`) |

## Cómo correrlo y probarlo

`boto3.resource('dynamodb')` no lleva endpoint: corre contra la DynamoDB de
la cuenta y región del perfil AWS activo. Para trabajar en local,
`dynamodb.sh` levanta DynamoDB en Docker (puerto 3100) con `audit_records` y
`usage_logs`, y se exporta `AWS_ENDPOINT_URL_DYNAMODB=http://localhost:3100`:

```bash
cd services/events
python main.py            # puerto del .env (PORT)
python -m pytest -q
pylint --fail-under=10.0 .
```

Se despliega con `services/ci/api/start.sh --redeploy events` (lo despliega
Rafael).

## Qué revisa el CI

`.github/workflows/python-package.yml`, en cada push y pull request a `main`:
instala `requirements.txt`, corre `pylint --fail-under=10.0 .` **sin** el
`.pylintrc` del repositorio y `pytest` **sin `.env`**: un test que importe
algo que lea configuración al importarse rompe el CI. `tests/test_events.py`
prueba el recorte de los cuerpos (`services/payload_limits.py`) y los
esquemas: campos de más ignorados, página de 1 a 100 y lectura sólo `ADMIN`.

## Creado por

**Rafael Ríos Bascón** — [raforios@gmail.com](mailto:raforios@gmail.com)
