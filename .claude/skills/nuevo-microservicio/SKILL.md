---
name: nuevo-microservicio
description: Levanta un microservicio nuevo copiando el patrón del servicio de referencia — cinco capas, boilerplate intacto, un archivo principal por capa. Úsala antes de escribir código de un servicio que no existe.
argument-hint: [nombre] [sql|dynamo]
allowed-tools: Bash(mkdir *), Bash(cp *), Bash(ls *), Bash(diff *), Bash(python3 *), Read, Write
---

Crea el andamiaje de `services/$1/` copiando el patrón existente. **No
escribas lógica de negocio en este paso**; primero la estructura, y se reporta.

## Servicio de referencia

- **DynamoDB** (`$2 = dynamo`, el caso normal): copia de `quotes`.
- **MySQL / PostgreSQL** (`$2 = sql`): copia de `localization` para un solo
  proceso, de `trade` si son varios procesos independientes.

Sin RDS por presupuesto: todo servicio nuevo va a DynamoDB salvo que Rafael diga
lo contrario.

## Las cinco capas, y cómo se nombran

```text
$1/
├── controllers/$1.py    Orquestación entre rutas y servicios
├── models/$1.py         Ítem DynamoDB o entidad SQLAlchemy
├── routes/$1.py         Endpoints FastAPI
├── schemas/$1.py        Pydantic V2, códigos de error en Enum
├── services/
│   ├── $1.py            Módulo principal del dominio
│   ├── $1_utils.py      Acceso a datos
│   └── <boilerplate>    api_exceptions, crud, db_connection, environment,
│                        exceptions, logger_config, security, utils
├── tests/
├── .env  .dockerignore  .gitignore  deploy.config
├── main.py  requirements.txt  README.md
```

**En cada capa el archivo principal se llama como el servicio.** `services/`
puede tener varios archivos, pero uno principal con ese nombre que concentre a
los demás.

**No se crean carpetas nuevas dentro de un microservicio.** Ni `locales/`, ni
`config/`, ni `scripts/`, ni ninguna otra. `scripts/` existe sólo en
`mining_analysis` por la carga quincenal manual, que no tiene alternativa. Si
algo parece no caber en las cinco capas, para y pregunta.

## El andamiaje

```bash
cd services
mkdir -p $1/{controllers,models,routes,schemas,services,tests}
for f in api_exceptions.py crud.py db_connection.py environment.py \
         exceptions.py logger_config.py security.py utils.py; do
  cp quotes/services/$f $1/services/$f
done
for d in controllers models routes schemas services tests; do
  cp quotes/$d/__init__.py $1/$d/__init__.py
done
cp quotes/.dockerignore quotes/.gitignore $1/
```

**El boilerplate se copia idéntico y no se modifica.** Si hace falta una
adición, se consulta primero y va al final del archivo.

**Si el servicio carga archivos**, copia además el bloque de FILES del final
de `finance/services/utils.py` (con sus tres imports) y `finance/schemas/files.py`,
y agrega al `.env` `BUCKET_NAME`, `BUCKET_PATH` y `FILES_TIMEOUT_SECONDS`.
Las llamadas a otros servicios usan una sola variable, `API_URL`, y arman la
ruta `/v1/<servicio>` (CLAUDE.md §5.4); nunca una `*_SERVICE_URL` por servicio.
Habla sólo con FILES: el servicio nuevo no lee tablas, buckets ni código de
otro (`CLAUDE.md` §4).

```bash
for f in api_exceptions.py crud.py environment.py exceptions.py \
         logger_config.py security.py utils.py; do
  diff -q quotes/services/$f $1/services/$f >/dev/null && echo "  $f OK"
done
```

## `.dockerignore` — un bloque común y lo propio al final

El bloque «Common to every service» se copia idéntico (Rafael, 22-oct-2026):
deja fuera el `.env` —o las credenciales viajan dentro del zip del Lambda—,
los tests, las cachés, los `.DS_Store` y los archivos de despliegue. Los
patrones de carpetas internas van con `**/` (`**/__pycache__/`): sin eso sólo
valen en la raíz. Lo propio del servicio va debajo, en «Own to this service».

## `Dockerfile` — no se crea

Todos los servicios se arman con `services/ci/api/Dockerfile.lambda`, y se
corren en local con `services/ci/api/Dockerfile.local` (Rafael, 22-oct-2026).
Un servicio sólo trae su propio `Dockerfile` si necesita algo realmente suyo;
`build_and_deploy.sh` lo usa en ese caso.

## `requirements.txt` — ni más ni menos

Sólo lo que el código del servicio importa, más lo que se usa sin importarse:
`python-multipart` si recibe archivos o formularios, `email-validator` si usa
`EmailStr`, `openpyxl` o `xlrd` si `pandas` lee Excel. Sin versiones. Las
herramientas de prueba van en `services/requirements-dev.txt`, nunca en el
Lambda. Todo debe venir como wheel para Linux y Python 3.14: el `Dockerfile`
común no compila (`--only-binary`).

## `deploy.config`

Copia el de `quotes` y ajusta nombre, memoria y tabla. Para el render de
imágenes hacen falta 1024 MB; para un servicio de sólo datos, 256 alcanzan.

## Orden de trabajo

1. **Schemas** — DTOs y códigos de error en `Enum`.
2. **Models** — si hay persistencia.
3. **Services** — la lógica, nunca en controllers ni routes.
4. **Controller y route** — cablear la entrada HTTP.
5. **Tests** — por cada función nueva en `services/`, y **un
   `tests/test_controllers.py`** que compruebe que cada endpoint devuelve su
   modelo armado. Ese hueco produjo 500 en producción con la suite en verde.
6. **README y `SMARTDECISIONS.md`.**

## Tablas y despliegue

`build_and_deploy.sh` no sabe crear claves compuestas ni admite dos tablas por
servicio. Las tablas se crean con `services/ci/api/create_dynamodb_tables.sh`,
que sí las soporta.

Antes del primer despliegue, el servicio se registra en `services/ci/api`
(`start.sh`, `setup_api_domain.sh`, `update_service_urls.sh`): sin eso
`./start.sh --redeploy <servicio>` no hace nada y termina sin error. Los pasos
están en «Si el microservicio es nuevo» de `services/ci/api/README.md`.

## Al terminar

Reporta la estructura creada, confirma que el boilerplate quedó idéntico, y di
qué falta: la lógica, las tablas y el despliegue de Rafael.
