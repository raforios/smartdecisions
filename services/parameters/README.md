# PARAMETERS — Parameters Service

Servicio **base** de BearSoft desde el 17-oct-2026 (CLAUDE.md §4 y §5.3).

## Para qué sirve

Guarda los **valores de negocio que se cambian sin redesplegar**: decimales,
medidas, unidades, umbrales, cuentas y, en general, lo que antes estaba en el
`.env` de cada servicio (Rafael, 17-oct-2026). El `.env` queda sólo para el
entorno: URLs, tablas, credenciales, región y timeouts de red.

Lo propio del dominio de un servicio **no** va aquí: se queda en sus tablas
(por ejemplo, las tasas de ley y los parámetros de cada cliente de FINANCE).

Cada parámetro tiene un **alcance** —`global` para lo que usa más de un
servicio, o el nombre del servicio que lo lee (`finance`)—, un tipo
(`NUMBER`, `TEXT` o `LIST`), un valor y una descripción de qué gobierna. La
definición única de todos está en `docs/parametros.md`.

## Endpoints y quién puede llamarlos

| Método | Ruta | Quién |
|---|---|---|
| GET | `/v1/parameters/{scope}` | Cualquier usuario autenticado (un servicio reenvía el token de quien llama) |
| GET | `/v1/parameters` | `ADMIN`: todos los alcances |
| PUT | `/v1/parameters/{scope}/{code}` | `ADMIN`: crea o reemplaza un valor |
| DELETE | `/v1/parameters/{scope}/{code}` | `ADMIN` |

Los cambios (PUT y DELETE) se auditan en EVENTS: un decimal o una cuenta que
movió un reporte es un valor que alguien escribió, y tiene que poder decirse
quién. Las lecturas no se registran (Rafael, 17-oct-2026): todos los servicios
leen aquí y un registro por lectura no dice nada del negocio.

## Qué servicios lo llaman

- **FINANCE** lee los alcances `finance` y `global` con el bloque PARAMETERS
  del final de su `services/utils.py` (`read_parameters`,
  `required_parameters`), y guarda lo leído `PARAMETERS_CACHE_SECONDS`: cambiar
  un valor no exige desplegar nada. Un valor que falta da `PARAMETER_MISSING`.
- Los demás servicios con valores de negocio en el `.env` se pasan aquí uno
  por uno, después del Análisis Financiero.

Ningún servicio lee la tabla: siempre por HTTP.

## Variables de entorno

Sólo entorno (CLAUDE.md §5.3):

| Variable | Qué es |
|---|---|
| `HOST`, `PORT`, `APP_ENV` | Servidor local y entorno |
| `SECRET_KEY`, `ALGORITHM` | Verificación del JWT de AUTH |
| `API_URL` | Gateway `api.bearsoft.com.bo`, para llegar a EVENTS |
| `REQUEST_TIMEOUT_SECONDS` | Timeout de las llamadas a EVENTS |
| `DYNAMODB_TABLE_NAME_PARAMETERS_VALUES` | Tabla de valores (`parameters_values`) |

## Tablas

`parameters_values`, partición `scope` y orden `code`. La crea
`services/ci/api/create_dynamodb_tables.sh` y la siembra
`tools/seeds/seed_parameters.py` desde `docs/parametros.md`.

## Cómo correrlo y probarlo

```bash
cd services/parameters
python main.py            # puerto del .env (PORT)
python -m pytest -q
pylint --fail-under=10.0 .
```

Los tests de la tabla corren contra DynamoDB simulada con `moto`, que no se
despliega: se instala sólo en el entorno local.

Se despliega con `services/ci/api/start.sh --redeploy parameters` (lo
despliega Rafael).

## Qué revisa el CI

`.github/workflows/python-package.yml`, en cada push y pull request a `main`:
instala `requirements.txt`, corre `pylint --fail-under=10.0 .` **sin** el
`.pylintrc` del repositorio y `pytest` **sin `.env`**.

- Sin `.env` corre sólo `tests/test_schemas.py`: las reglas de tipo y el valor
  de cada tipo, que no leen configuración.
- `tests/conftest.py` deja fuera `test_parameters.py` y `test_controllers.py`
  cuando no hay configuración, porque importan módulos que la leen al
  importarse; con `.env` corren todos.

## Creado por

**Rafael Ríos Bascón** — [raforios@gmail.com](mailto:raforios@gmail.com)
