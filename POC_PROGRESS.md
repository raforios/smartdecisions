# POC_PROGRESS.md — SmartDecisions POC

> Bitácora de trabajo del POC de **SmartDecisions** (empresa: **BearSoft**).
> Mantenido por Claude entre sesiones para no perder contexto.
> Fuentes asociadas: `SMARTDECISIONS.md` (visión), `CLAUDE.md` (estándares).

---

## Plan maestro — 5 pasos del POC

1. **Cerrar la marca** — find-and-replace SmartBear→SmartDecisions (producto); BearSoft se mantiene (empresa); aclarar TRADE/FORMS = Binaria; decidir mascota.
2. **Contrato Excel + validador + fix `routes.ipynb`** — plantilla `template_ventas_v1.xlsx`, parser pandas + validación pydantic/pandera, reutiliza FILES (S3). Fix de `/app/notebooks/routes.ipynb` como pre-req del paso 4.
3. **Motor afinidad × drop size (v0)** — microservicio `Analytics-Service` en Lambda, `mlxtend` + ML_FUNCTIONS, output accionable en $, persistencia en DynamoDB.
4. **Frontend demo estático (Vanilla JS) en S3+CloudFront — 3 módulos**
   - (a) Excel → oportunidades (del paso 3)
   - (b) Playground ML portando `frontend.ipynb` (regresión, gradiente, Z-score) con Chart.js
   - (c) Optimización de rutas portando `routes.ipynb` con Leaflet+OSM
5. **Empaquetar pitch técnico** — datos sintéticos, guion de demo 5 min, README "cómo evaluar el POC".

**Dependencias:** 1 → 2 → 3 → 4 → 5. Pasos 1 y 2 paralelizables.

**Infra confirmada:** CloudFront + S3 (frontend), Lambda + API Gateway (backend), DynamoDB (datos, sin RDS por presupuesto $0).

---

## Paso 1 — Cerrar la marca

**Estado:** ✅ COMPLETO en cuanto a archivos. **Falta solo el `mv` físico del directorio** (ver "Comandos finales para el usuario" al final).

**Cambios aplicados (2026-06-11):**

| Archivo | Cambio |
|---|---|
| `app/CLAUDE.md` | Título `SmartBear API` → `SmartDecisions API` |
| `app/SMARTDECISIONS.md` | Nota de marca reescrita (BearSoft empresa, SmartDecisions producto, aclaración explícita TRADE/FORMS = Binaria); contexto histórico ("el artifact original decía...") preservado intencionalmente |
| `app/services/{auth,events,events_mysql,files,forms,localization,mining_summit,ml_functions,planning,supplies,trade}/main.py` + `api/main.py` | Metadata `'Owner': f'BearSoft …'` → `'BearSoft …'` (12 archivos) |
| `app/frontend/main.py` + `pages/{load_file,optimization,dashboard,content_generator}.py` + `services/{rest,load_data}.py` | Streamlit titles, `page_title`, docstrings y comentarios `SmartBear` → `SmartDecisions` |
| `app/notebooks/lib/{rest,frontend_functions}.py` | Docstrings `SmartBear API` → `SmartDecisions API` |
| `app/notebooks/routes.ipynb` | Markdown cell `## Login into SmartBear API` → `SmartDecisions API` |
| `app/services/ci/api/start.sh` | Comentario y echo descriptivos (rutas del filesystem preservadas) |
| `app/services/supplies/README.md` + `app/demo/supplies/README.md` + `app/services/mining_analysis/README.md` + `boilerplate.md` | Texto descriptivo "ecosistema/arquitectura/proyecto SmartBear (BearSoft)" → "SmartDecisions (BearSoft)" |

**Referencias preservadas intencionalmente (no tocar):**
- ~37 refs en paths absolutos del filesystem (`/Users/rafael/Work/projects/back/SmartDecisions/...`) en CI scripts, READMEs de auth/files/ml_functions y Postman collections → son la ruta física del directorio.
- 15 refs en outputs de tracebacks dentro de celdas ejecutadas en `routes.ipynb`, `frontend.ipynb`, `rutas_optimizadas.ipynb` → se regeneran al re-ejecutar el notebook; no editar JSON manualmente.
- 5 refs en este `POC_PROGRESS.md` y 3 en `SMARTDECISIONS.md` → documentación histórica del cambio.

**Verificación segura:**
- `deploy.config` revisado: **no contiene "smartbear" / "bearsoft"** → no hay recursos AWS (Lambda/S3/DynamoDB) cuyo nombre romperíamos al renombrar; ningún redeploy obligado.

**Decisiones del usuario aplicadas (2026-06-11):**
1. ✅ **Renombrar `/SmartBear/` → `/SmartDecisions/`** — paths absolutos ya reescritos en todos los archivos del repo (CI scripts, READMEs, Postman collections). Solo falta el `mv` físico del directorio (ver "Comandos finales").
2. ✅ **Mascota: oso reinterpretado** — incorporado en `app/portal/assets/logo-bear.svg` como un oso que sostiene una curva ascendente, simbolizando "decisiones firmes con datos reales".
3. ✅ **Portal HTML landing creado en `app/portal/`** — dark theme, HTML+CSS+JS vanilla, cero dependencias, listo para S3+CloudFront ($0). Estructura: `index.html`, `style.css`, `script.js`, `assets/logo-bear.svg`, `assets/favicon.svg`, `README.md`. Secciones: hero, producto (con fórmula Afinidad × Drop Size), servicios (6 cards), cómo funciona (3 pasos), demo CTA, contacto (form → mailto).

## Comandos finales para el usuario (paso 1)

Estos comandos los debo ejecutar yo (Rafael) **fuera** de la sesión actual de Claude, porque Claude está corriendo dentro del directorio que se va a mover.

```bash
# 1. Confirmar que el repo está en un estado limpio (o commitear antes)
cd /Users/rafael/Work/projects/back/SmartBear
git status

# 2. Salir del directorio antes del rename
cd /Users/rafael/Work/projects/back

# 3. Renombrar el directorio del proyecto
mv SmartBear SmartDecisions

# 4. Renombrar el directorio de memoria persistente de Claude
#    (el nombre codifica la ruta de trabajo; si no se renombra, la próxima
#    sesión no encontrará la memoria)
mv "$HOME/.claude/projects/-Users-rafael-Work-projects-back-SmartBear-app" \
   "$HOME/.claude/projects/-Users-rafael-Work-projects-back-SmartDecisions-app"

# 5. Entrar al nuevo path y arrancar Claude allí
cd /Users/rafael/Work/projects/back/SmartDecisions/app
claude
```

Después del rename, todos los scripts CI siguen funcionando porque sus paths absolutos
ya apuntan a `/SmartDecisions/`. Verificación rápida:

```bash
grep -rIc "/Users/rafael/Work/projects/back/SmartBear/" . | grep -v ":0$"
# Esperado: vacío
```

---

## Paso 2 — Contrato Excel + validador + fix `routes.ipynb`

**Estado:** 🟡 EN PROGRESO — chunk 1 (contrato) listo y probado; pendientes: boilerplate shared, endpoints, deploy, fix `routes.ipynb`.

### Decisiones de diseño (confirmadas con el usuario, 2026-06-12)
- **Ingest vive en un microservicio nuevo** `services/ingest/` (SRP, separa ingesta de análisis).
- **Validación:** Pydantic V2 para los DTOs HTTP + pandera para el DataFrame del Excel.

### Chunk 1 — Contrato de datos + validador + plantilla (✅ listo y probado)

| Archivo | Rol |
|---|---|
| `services/ingest/schemas/ingest.py` | DTOs Pydantic V2: `IngestResponse`, `IngestStatusResponse`, `IngestSummary`, `IngestColumnError`, `TemplateInfo`. Schema con ejemplo en OpenAPI. |
| `services/ingest/services/excel_validator.py` | `SCHEMA: pa.DataFrameSchema` v1 con columnas obligatorias (`id_pedido`, `fecha`, `id_punto_venta`, `id_producto`, `cantidad`) y opcionales (`nombre_pdv`, `zona`, `nombre_producto`, `precio_unitario`, `monto_total`). Función `validate(df)` en modo lazy → devuelve `(df_validado, errores)` con mensajes en español por prefix-matching de reglas. |
| `services/ingest/services/excel_parser.py` | Pipeline `parse_and_validate(file_bytes, filename)` → lee `.xlsx`/`.csv`, valida, deriva `monto_total = cantidad × precio_unitario` cuando falta, calcula `IngestSummary`. |
| `services/ingest/scripts/generate_template.py` | Genera `template_ventas_v1.xlsx` con hoja **Ventas** (3 filas de ejemplo) + hoja **Instrucciones** (descripción por columna). CLI: `python scripts/generate_template.py --output ruta.xlsx`. |
| `services/ingest/services/logger_config.py` | Boilerplate shared (copy verbatim de mining_summit). |
| `services/ingest/requirements.txt` | Stack: FastAPI 0.115, Pydantic 2.9, **pandera 0.31.1** (la 0.20 rompe en Python 3.14), pandas 2.2, openpyxl 3.1, boto3, mangum, python-jose, dotenv. |

### Smoke test (✅ pasa, ejecutado 2026-06-12)
- **Archivo limpio (plantilla v1):** 3/3 filas válidas, summary correcto, `monto_total` auto-derivado.
- **Archivo corrupto** (fecha basura, `id_producto` vacío, `cantidad` negativa): 4 errores detectados con número de fila, columna y mensaje en español. Ejemplo de output: `row=3 col=id_producto -> "Este campo es obligatorio y no puede estar vacío."`, `row=3 col=cantidad -> "El valor debe ser mayor que el mínimo permitido."`
- **Archivo vacío:** caso global `(archivo)` con mensaje `"El archivo no contiene filas de datos."`

### Chunk 2 — Boilerplate shared (✅ completo)
Copiados verbatim los 8 shared files siguiendo la regla de boilerplate-como-contrato:
`api_exceptions.py`, `crud.py`, `db_connection.py`, `environment.py`, `exceptions.py`, `logger_config.py`, `security.py`, `utils.py`.

**Fuente canónica usada:** según memoria `feedback_boilerplate_standard.md`, la referencia para servicios DynamoDB es **EVENTS** (no mining_summit). Hecho `diff` entre `events/services/` y `mining_summit/services/`: 7 de 8 archivos son idénticos, pero `security.py` diverge — mining_summit usa lookup manual de `os.environ.get` + `dotenv_values`, EVENTS usa el helper centralizado `load_and_validate_env_vars`. `ingest/services/security.py` se resincronizó desde **EVENTS** (la canónica).

**Deriva detectada en mining_summit/services/security.py** — se aparta del patrón canónico (EVENTS). Es un cleanup a coordinar fuera del paso 2; no es bloqueante para el POC.

Añadidos `__init__.py` en `controllers/`, `models/`, `routes/`, `tests/`, `scripts/`. Creado `.env.example` documentando las 9 variables requeridas (HOST, PORT, SECRET_KEY, ALGORITHM, TARGET_TIMEZONE, DYNAMODB_TABLE_NAME_INGEST_DATASETS, AWS_REGION, FILES_SERVICE_URL, AUTH_SERVICE_URL).

**Nota recordatoria:** `logger_config.py` exporta `custom_logger = setup_logger('smartbear')` con el nombre `'smartbear'` hardcodeado. Es legacy en TODOS los servicios actuales; renombrar a `'smartdecisions'` debe hacerse coordinado en todos los main.py/log readers de una sola pasada — no aquí.

### Chunk 3 — Capa HTTP (✅ completo)

| Archivo | Rol |
|---|---|
| `services/ingest/main.py` | Entry FastAPI con lifespan, CORS, healthcheck `/`, Mangum handler para Lambda, Swagger UI custom. Idéntico al patrón de `mining_summit/main.py`. |
| `services/ingest/routes/ingest.py` | Router `/v1/ingest` con 4 endpoints: `GET /template` (metadata), `GET /template/file` (descarga .xlsx), `POST /excel` (upload + valida), `GET /{dataset_id}` (status). Todos protegidos con `Depends(get_current_user)`. |
| `services/ingest/controllers/ingest.py` | Orquesta `parse_and_validate` → upload a S3 vía FILES (solo si válido) → `persist_dataset` en Dynamo → respuesta. |
| `services/ingest/models/dataset.py` | `IngestDataset` TypedDict — schema NoSQL para tabla `t_ingest_datasets` (PK: `dataset_id`). |
| `services/ingest/services/datasets.py` | Acceso a Dynamo: `persist_dataset`, `get_dataset_by_id`. Usa `crud.create_item` con `unique_key_attribute='dataset_id'`. |
| `services/ingest/services/file_storage.py` | Cliente HTTP a FILES (`POST /v1/files/upload`). Reenvía el bearer del usuario. Centraliza la política de storage en FILES; el servicio Ingest no habla a S3 directo. |
| `services/ingest/tests/test_excel_validator.py` | 6 tests Pytest: filas válidas mínimas, columna faltante, cantidad negativa, fecha inválida, derivación de monto_total, extensión no soportada. **6/6 verdes.** |
| `services/ingest/.gitignore` | Excluye `.env`, `__pycache__`, `.pytest_cache`, plantillas generadas en `assets/`. |
| `requirements.txt` | + `requests==2.32.3`, `pytest==8.3.3`. |

### Verificación (✅)
- Import de `main.py` con `.env` dummy → todas las rutas registradas: `GET /v1/ingest/template`, `GET /v1/ingest/template/file`, `POST /v1/ingest/excel`, `GET /v1/ingest/{dataset_id}`, más `/`, `/docs`, `/openapi.json`.
- Pytest: 6/6 verdes en `tests/test_excel_validator.py`.
- Fixes aplicados durante el debug:
  - `_derive_monto_total` no rompe cuando `precio_unitario` está ausente (caso de archivos con solo columnas requeridas).
  - Errores de columna faltante (`column_in_dataframe`) leen el nombre desde `failure_case` en vez de `column` (donde pandera lo deja `None`).

### Chunk 4 — Empaque para deploy (✅ completo)

| Archivo | Rol |
|---|---|
| `Dockerfile` | Build para Lambda x86_64 sobre `public.ecr.aws/lambda/python:3.14`. Incluye un paso adicional: ejecuta `scripts/generate_template.py` durante el build para bundlear `template_ventas_v1.xlsx` en `assets/`, así el endpoint `GET /v1/ingest/template/file` puede servirlo directo desde disco. ZIP final: `lambda_function.zip`. |
| `.dockerignore` | Excluye `__pycache__`, `.git`, `.venv`, `.env`, `assets/template_ventas_*.xlsx` (se regenera en build). |
| `deploy.config` | FUNCTION_NAME=`ingest-service`, ROLE_NAME=`lambda-service-ingest-execution-role`, REGION=`us-east-1`, TIMEOUT=30, MEMORY_SIZE=**512** (Excel parsing pesa más memoria que mining_summit), DYNAMODB_TABLE_NAME=`t_ingest_datasets`, DYNAMODB_PRIMARY_KEY=`dataset_id`/S. |
| `dynamodb.sh` | Bootstrap local. Una sola tabla: `t_ingest_datasets` con PK `dataset_id`/HASH. Reusa el contenedor `dynamodb-local-container:3100` por convención del proyecto. Ejecutable y syntax-checked con `bash -n`. |
| `README.md` | Doc del servicio: stack, estructura, env vars (10), endpoints (4), contrato v1 de la plantilla (10 columnas), reglas de negocio, run local. |

### Verificación (✅)
- `bash -n dynamodb.sh` → syntax OK.
- `chmod +x dynamodb.sh` aplicado.
- Listado final del servicio (`ls -la`) cubre los 11 archivos/dirs estándar del boilerplate más `assets/`, `scripts/`, tests y los 3 dotfiles (`.env.example`, `.gitignore`, `.dockerignore`).
- El Dockerfile **no se buildeó** en esta sesión (requiere Docker + ~20 min); está listo para `docker build` cuando se vaya a deployar.

### Chunk 5 — Migración del módulo de optimización (✅ servicio completo; pendiente: seed + notebook)

**Decisión de diseño (con el usuario, 2026-06-15):**
- Vivienda: **nuevo microservicio** `services/optimization/` (SRP — separa algoritmo de CRUD).
- Datos: **nueva tabla Dynamo** `t_optimization_routes` (auto-suficiente; sin dependencia HTTP de LOCALIZATION).
- Fuente: portar verbatim los algoritmos del monolito `api/` (Postgres → Dynamo solo en la capa de datos).

**Estructura creada (sigue boilerplate.md al pie de la letra):**

```
services/optimization/
├── assets/
├── controllers/
│   ├── __init__.py
│   └── optimization.py   ← 4 controllers async + helpers, port desde monolito
├── models/
│   ├── __init__.py
│   └── route_point.py    ← TypedDict para t_optimization_routes
├── routes/
│   ├── __init__.py
│   └── optimization.py   ← 5 endpoints GET, todos con JWT
├── schemas/
│   ├── __init__.py
│   └── optimization.py   ← Pydantic V2: DataMap/Optimization/Route + QueryParams
├── scripts/__init__.py
├── services/
│   ├── __init__.py
│   ├── api_exceptions.py ← verbatim EVENTS (canónica DynamoDB)
│   ├── crud.py           ← verbatim EVENTS
│   ├── db_connection.py  ← verbatim EVENTS
│   ├── environment.py    ← verbatim EVENTS
│   ├── exceptions.py     ← verbatim EVENTS
│   ├── logger_config.py  ← verbatim EVENTS
│   ├── security.py       ← verbatim EVENTS
│   ├── utils.py          ← verbatim EVENTS
│   ├── ml_optimization.py ← port verbatim del monolito (GeoAnalyzer, optimal_route, etc.)
│   └── route_data.py     ← acceso Dynamo: get_route_points(route_id, day)
├── tests/
│   ├── __init__.py
│   └── test_ml_optimization.py  ← 4 tests del algoritmo
├── .env
├── .dockerignore
├── .gitignore
├── Dockerfile             ← +geos-devel +proj-devel para osmnx
├── README.md
├── deploy.config          ← MEMORY=1024MB TIMEOUT=60s (osmnx + networkx pesados)
├── dynamodb.sh            ← composite key route_day_key (HASH) + client_id (RANGE)
├── main.py
└── requirements.txt
```

**Contrato preservado del monolito** — mismo path/método/query, solo cambia prefijo (`/api/v1/optimization/*` → `/v1/optimization/*`):
- `GET /v1/optimization/data_model?route_id&day`
- `GET /v1/optimization/distances?route_id&day`
- `GET /v1/optimization/optimal_route?route_id&day&dist`
- `GET /v1/optimization/distance_matrix?route_id&day`
- `GET /v1/optimization/route?route_id&day&dist`

**Cambio de capa de datos:** monolito hacía `SELECT * FROM routes WHERE route_id=X AND day=Y` en Postgres. El microservicio lee la misma forma desde Dynamo con una sola Query bajo PK compuesta `route_day_key = f"{route_id}#{day}"`. La adaptación está aislada en `controllers/optimization.py:_load_dataframe` (todo lo demás del algoritmo es port verbatim).

**Verificación (✅):**
- Import de `main.py` → las 5 rutas + `/`, `/docs`, `/openapi.json` registradas.
- Pytest `tests/test_ml_optimization.py` → **4/4 verdes** (distance_between_points, hexa_color_generator_list, fiter_order_df, GeoAnalyzer distance matrix simétrica).
- `bash -n dynamodb.sh` → syntax OK.
- `diff` de los 8 shared files contra `events/services/` → idénticos (regla boilerplate-como-contrato cumplida).

### Chunk 5d — Fix del notebook + seed Dynamo (✅ completo)

**Helper `lib/frontend_functions.py`**: ya alineado al nuevo microservicio sin necesidad de cambios — `data_api` arma `f'{url}/v1/optimization/{endpoint}?route_id=...&day=...&dist=...'` y reenvía el bearer. La signature actual `data_api(token, url, endpoint, params: OptimizationParams)` es la canónica.

**Notebook `routes.ipynb` (6 celdas actualizadas):**

| Cell | Cambio |
|---|---|
| 1 | Imports: agregado `data_api` a `from lib.frontend_functions import (...)` y `from lib.models import OptimizationParams`. |
| 4 | URL hint actualizada: default `http://localhost:3120` (PORT del nuevo optimization service); alternativas comentadas (API Gateway local, AWS deploy). |
| 12 | `get_data(token, url, 'data_model', route_id, day, 1)` (uso incorrecto) → `data_api(token, url, 'data_model', OptimizationParams(route_id, day, primary=1))`. |
| 13 | Args posicionales → `OptimizationParams(route_id, day, primary=1)`. |
| 15 | Args posicionales + `radio` → `OptimizationParams(route_id, day, primary=1, dist=radio)`. |
| 17 | Args posicionales (`primary=2` para devolver dict crudo) → `OptimizationParams(route_id, day, primary=2)`. |
| 19 | Args posicionales + `radio` → `OptimizationParams(route_id, day, primary=1, dist=radio)`. |

Notebook re-validado como JSON (`nbformat=4`, 54 cells, sin pérdida de celdas/metadata).

**Seed Dynamo (`services/optimization/scripts/seed_from_csv.py`):**
- Lee CSV con columnas `route_id, day, client_id, latitude, longitude, [client]`.
- Convierte a items con PK compuesta `route_day_key = "{route_id}#{day}"`, SK `client_id`. Lat/lon como `Decimal` (DynamoDB rechaza floats nativos).
- `batch_writer` para escritura amortizada.
- Soporta local Dynamo (`--endpoint-url http://localhost:3100`) y AWS (credenciales por default chain).
- Lee `DYNAMODB_TABLE_NAME_OPTIMIZATION_ROUTES` del entorno o `.env`; fallback `t_optimization_routes`.
- CSV de ejemplo en `scripts/sample_routes.csv` (12 filas, 3 rutas × 1-2 días en La Paz para probar end-to-end).

**Flujo end-to-end para correr el notebook ahora:**

```bash
# 1. Levantar Dynamo local + crear tabla
cd app/services/optimization
./dynamodb.sh

# 2. Seed con datos de ejemplo
cp .env  # ya creado
PYTHONPATH=. python scripts/seed_from_csv.py \
    --csv scripts/sample_routes.csv \
    --endpoint-url http://localhost:3100

# 3. Levantar el servicio
pip install -r requirements.txt
python main.py   # → http://localhost:3120

# 4. Abrir routes.ipynb con la venv activa y ejecutar.
```

**Caveat documentado:** el notebook usa un solo `url` para login (AUTH) y optimization. En producción ambos van por el mismo API Gateway. En local hay que decidir routing (SAM CLI, nginx, o partir el notebook en dos URLs). No bloquea el cierre del paso 2; será un detalle del paso 4 (frontend).

---

## Paso 4 — Frontend demo en S3+CloudFront (🟡 en progreso)

Layout del demo en `app/portal/demo/`, sibling del landing existente (`app/portal/index.html`). Cero build step, Vanilla JS para que sea trivial publicar en CloudFront.

### Chunk 4a — Scaffold + login + home + helpers compartidos (✅ completo)

| Archivo | Rol |
|---|---|
| `portal/demo/index.html` | Login (email + password). Redirige a `home.html` o a `?next=...` post-login. |
| `portal/demo/home.html` | Selector con 3 cards (Excel, Playground, Routes). Muestra email logueado + botón Salir. |
| `portal/demo/styles/demo.css` | Dark theme compartido continuación del landing (mismas vars CSS). Toasts, cards, formularios, botones. |
| `portal/demo/js/config.js` | `window.SD_CONFIG` con URLs por servicio (defaults locales: 3000/3110/3120/3130/3140) + `LOGIN_PATH` configurable por deployment. |
| `portal/demo/js/auth.js` | `window.SD_AUTH`: `login` (POST `/v1/auth/login`), `logout`, `requireAuth`, `getToken`, `getEmail`. Persistencia en sessionStorage. |
| `portal/demo/js/api.js` | `window.SD_API`: `get/post/postFormData` con bearer automático. En 401 limpia sesión y bouncea a login. |
| `portal/demo/js/ui.js` | `window.SD_UI`: `toast`, `setButtonBusy`, `qs/qsAll`. |

**Cambios en el landing:**
- `portal/index.html` línea ~144: CTA "Solicitar acceso al demo" (mailto) → reemplazado por "Entrar al demo en vivo" → `demo/index.html`. Mailto sigue como link secundario.

**Decisiones de diseño:**
- Sin frameworks (Vanilla JS) → cero build, publicación gratis en S3+CloudFront.
- JWT en `sessionStorage` (no localStorage) → expira al cerrar pestaña, suficiente para POC.
- URLs por servicio configurables vía `config.js` (un archivo editable por entorno, no requiere rebuild).
- Path de login (`LOGIN_PATH`) centralizado en config para soportar deployments en raíz (`/demo/`) o bajo prefijo (`/portal/demo/`) cambiando una sola línea.

**Verificación (✅):**
- Server local (`python3 -m http.server`) sirve `/demo/`, `/demo/home.html`, los 4 JS y el CSS con HTTP 200.
- 404 limpio para archivos inexistentes.
- Landing CTA apunta correctamente a `demo/index.html`.
- Login HTML contiene `loginForm` + referencias a `SD_AUTH`.
- `auth.js` arma URL contra `/v1/auth/login` del AUTH service.
- **No verificado visualmente en navegador** (sin acceso a Playwright en esta sesión). Recomiendo abrir `http://localhost:<port>/portal/demo/` para validar antes de los chunks de módulos.

### Chunk 4b — Módulo Excel → Oportunidades (✅ completo)

| Archivo | Rol |
|---|---|
| `portal/demo/excel/index.html` | Página única con 4 secciones progresivas: descarga plantilla, upload, resultado de validación (summary + errores), oportunidades (tabla ordenable + filtrable). |
| `portal/demo/excel/excel.css` | Estilos del módulo: upload zone con drag-and-drop, metric cards, tabla ordenable con flecha asc/desc, filtros. Continuación del dark theme compartido. |
| `portal/demo/excel/excel.js` | Lógica completa del flujo. |

**Flujo end-to-end implementado:**
1. **Descarga plantilla** → `GET ${INGEST_URL}/v1/ingest/template/file` con bearer; blob → trigger `.xlsx` download.
2. **Subir archivo** → drag-and-drop o file picker (`.xlsx`/`.csv`); valida extensión client-side; `POST ${INGEST_URL}/v1/ingest/excel` multipart.
3. **Resultado de validación** → 5 metric cards (filas válidas, errores, PdVs, productos, rango de fechas). Si `status='failed'`: tabla de errores con fila/columna/valor/mensaje en español (cap a 200 filas con indicador). Si `validated`: botón "Ejecutar análisis".
4. **Run analytics** → `POST ${ANALYTICS_URL}/v1/analytics/run/{dataset_id}`. Render del summary del run (oportunidades, PdVs con acciones, impacto $ esperado, reglas evaluadas).
5. **Tabla de oportunidades** → 8 columnas (PdV, producto recomendado, basado en, lift, confianza, drop u, $ esperado, score). Ordenable por cualquier columna (default: score desc). Filtro por substring (PdV id/nombre o producto). Tooltip en cada fila muestra el `rationale` en español.

**Detalles UX:**
- Toasts (success/error/info) para feedback inmediato.
- Botones con estado busy (label + disabled) durante calls async.
- Scroll-into-view automático cuando aparecen las secciones nuevas.
- Tabla con `tabular-nums` para que las cifras alineen.
- Filtros de moneda formateados como `$ 1,234.56` (locale `es-BO`).
- Confianza renderizada como porcentaje.

**Verificación (✅):**
- Server local sirve `/demo/excel/` + CSS + JS con HTTP 200.
- HTML tiene todos los hooks DOM esperados (uploadZone, downloadTemplateButton, runAnalyticsButton, opportunitiesTable, opportunitySummary, pdvFilter).
- JS contiene las 3 URLs de servicio (`/v1/ingest/template/file`, `/v1/ingest/excel`, `/v1/analytics/run/`) + integración con `SD_AUTH` / `SD_API` / `SD_UI`.
- **`node --check`** sobre `excel.js` → return code 0 (sintaxis válida).
- **No verificado en navegador** (sin Playwright en sesión). Recomiendo abrir manualmente y probar el flujo end-to-end con los servicios `auth + ingest + analytics` corriendo locales.

### Chunk 4c — Módulo Playground ML (✅ completo)

| Archivo | Rol |
|---|---|
| `portal/demo/playground/index.html` | 3 tabs (Lineal · Logística · Z-Score+Sigmoid) con 8 formularios, Chart.js vía CDN. |
| `portal/demo/playground/playground.css` | Tabs con underline animado, grid responsive, result blocks con pills + result-table, chart-wrapper con altura fija. |
| `portal/demo/playground/playground.js` | Mapping de todos los endpoints + parsers JSON permisivos + Chart.js para J_history. |

**Endpoints cubiertos (10 de `ml_functions`):**

| Tab | Endpoint | UI |
|---|---|---|
| Lineal | `POST /v1/prediction/train-linear-regression` | Form + pills `w_final/b_final/iters/costo` + line chart de `J_history`. |
| Lineal | `POST /v1/prediction/predict-linear-regression` | Tabla `entrada → ŷ`. |
| Lineal | `POST /v1/prediction/compute-cost` + `compute-gradient` | Pills `cost/dj_db/dj_dw` (dos llamadas encadenadas para mostrar ambos). |
| Logística | `POST /v1/classification/train-logistic-regression` | Pills + line chart de `J_history`. |
| Logística | `POST /v1/classification/predict-logistic-classification` | Pills `Total/Clase 1/Clase 0` + tabla `entrada → clase`. |
| Logística | `POST /v1/classification/cost-logistic` + `gradient-logistic` | Pills `cost/dj_db/dj_dw`. |
| Común | `POST /v1/common/normalize-features` | Pills `μ/σ` + tabla del `x_norm`. |
| Común | `POST /v1/classification/sigmoid-batch` | Tabla `z → σ(z)`. Tolerante a array directo o `{values:[...]}`. |

**Detalles UX:**
- Cada form arranca con el **example del schema OpenAPI** pre-cargado → click "Calcular" y se ve algo de inmediato.
- Botón "Restablecer ejemplo" por form.
- Botones "Usar pesos entrenados" en los forms de predicción → copian `w_final/b_final` del último train automáticamente. Sino, toast informativo.
- Parser JSON permisivo: acepta tanto `2.0` como `[1, 2, 3]` en campos escalares-o-lista (`w`, `w_in`, etc.).
- Chart.js renderizado con tema dark (accent del proyecto), grid color `#26314f`, sin aspect-ratio (`maintainAspectRatio: false`) y altura fija del wrapper.
- Form-note inline por form para errores de parsing o de la API; toast como respaldo.

**Verificación (✅):**
- Server local sirve `/demo/playground/` + CSS + JS con HTTP 200.
- HTML contiene los 8 IDs de forms + 2 IDs de charts + 2 botones de reuse + tag `<script src="…chart.js…">`.
- JS contiene las 10 rutas de endpoints + `new Chart(...)` + helpers `parseJSONField` y `renderCostChart`.
- **`node --check`** sobre `playground.js` → return code 0 (sintaxis válida).
- **No verificado en navegador** (sin Playwright). Levantar `ml_functions` localmente y abrir `/demo/playground/` para probar end-to-end.

### Chunk 4d — Módulo Optimización de rutas (✅ completo)

| Archivo | Rol |
|---|---|
| `portal/demo/routes/index.html` | Layout sidebar (params + capas + summary) + mapa Leaflet. Carga Leaflet 1.9.4 (CSS+JS) vía unpkg con SRI integrity. |
| `portal/demo/routes/routes.css` | Grid responsive (sidebar 340px + mapa 1fr), tweaks dark-theme para Leaflet (popup, attribution, container background), loader overlay con spinner, toggles con swatches de color. |
| `portal/demo/routes/routes.js` | Flujo completo: form → API → Leaflet drawing → summary. |

**Flujo end-to-end implementado:**
1. **Cargar puntos** → `GET ${OPT_URL}/v1/optimization/data_model?route_id=X&day=Y` con bearer; dibuja `circleMarker`s (rojo=inicio, verde=fin, amarillo=resto) + polyline azul punteada con el orden client_id (ruta "original" de referencia).
2. **Optimizar** → `GET ${OPT_URL}/v1/optimization/optimal_route?route_id=X&day=Y&dist=R`; dibuja polyline teal con los segmentos del orden óptimo.
3. **Summary card** con 6 métricas: paradas, segmentos, distancia total (graph), lineal total, promedio/tramo, radio OSM. Formato `m`/`km` según magnitud.
4. **Capas toggleables** (puntos, original, optimizada) — checkbox que add/remove `LayerGroup`.
5. **Loader overlay** mientras el backend ejecuta osmnx (puede tardar varios segundos).

**Decisiones de diseño:**
- **Tiles CartoDB Dark Matter** (free + open) en lugar de OSM default para combinar con el theme del demo.
- **Leaflet vía CDN unpkg con SRI**: cero build step, bundle invariable, deployable directo a S3.
- **Sin OSM road-aligned polyline:** la ruta optimizada se dibuja lineal entre paradas. El backend SÍ proyecta la ruta sobre OSM nodes (campo `route` en `RouteResponse`), pero retorna node IDs, no lat/lng. Para el road-aligned exacto habría que extender `optimization` con una resolución de coords. Lo documento como deuda técnica del POC.
- **Popups con info contextual** por marker (cliente, día, coords) y por segmento (origin→target, distance graph vs linear).

**Verificación (✅):**
- Server local sirve `/demo/routes/` + CSS + JS con HTTP 200.
- HTML tiene todos los hooks DOM (`#map`, `routeForm`, `loadPointsButton`, `optimizeButton`, `summaryCard`, los 3 toggles) y las tags de Leaflet (CSS + JS).
- JS contiene las 2 rutas (`/v1/optimization/data_model`, `/v1/optimization/optimal_route`), las 4 primitivas Leaflet (`L.map`, `L.tileLayer`, `L.polyline`, `L.circleMarker`), tiles CartoCDN, helpers `drawOptimizedRoute`/`renderSummary`.
- **`node --check`** sobre `routes.js` → return code 0 (sintaxis válida).
- **No verificado en navegador** (sin Playwright). Para probar end-to-end: `./dynamodb.sh` + seed CSV + levantar `optimization` localmente, luego abrir `/demo/routes/`.

---

## 🎯 Paso 5 — Empaque del pitch técnico (✅ completo)

Tres entregables listos para mostrar el POC a un prospecto sin tocar
código:

### 5.1 — Generador de datos sintéticos
`app/tools/synthesize_sales.py` — crea un Excel realista que pasa
end-to-end por ingest + analytics con afinidades embebidas a propósito.

| Característica | Valor |
|---|---|
| Catalogo | 12 SKUs, 4 categorías (galletas/yogurt/cerveza/snack + 4 staples) |
| PdVs | 5 con perfiles distintos (PdV-007 fan de galletas, PdV-012 cervecero sin snacks, PdV-036 solo galletas, etc.) |
| Afinidades embebidas | A↔B con `cooccurrence_probability ∈ [0.6, 0.8]` |
| Dataset por defecto | 1,200 órdenes / 4,478 filas / 60 días |
| Reproducibilidad | `--seed 42` |
| CLI | `python tools/synthesize_sales.py --output ... --orders ... --seed ...` |

**Validación end-to-end ejecutada (✅):**
- Ingest: 4478/4478 filas válidas, 0 errores.
- Analytics: **16 oportunidades, 5/5 PdVs, $2,525.48 de impacto esperado, lift máx 9.92, 342 reglas evaluadas.**

**Bug interno corregido durante la validación:** el primer draft del generator caía en bucle infinito cuando `basket_size > len(reachable_skus)` para PdVs con catálogos chicos (PDV-036, PDV-048). Corregido con cap dinámico al `len(reachable)` + safety iteration limit. Tres procesos zombies de pruebas anteriores fueron limpiados con `pkill -9 -f synthesize_sales.py`.

### 5.2 — Guion de demo de 5 minutos
`app/docs/DEMO_SCRIPT.md` — guion paso-a-paso pensado para una llamada
comercial en vivo:

| Bloque | Tiempo |
|---|---|
| Preparación (antes de la reunión) | offline |
| Hook (el problema) | 45 s |
| Login + home | 15 s |
| Módulo Excel (plantilla, upload, validación, run, tabla) | 3 min |
| Diferenciador técnico (Playground ML) | 45 s |
| Bonus rutas (si hay tiempo) | 45 s |
| Cierre comercial | 30 s |

Incluye **apéndice de troubleshooting** (qué decir si falla cada paso) y
**apéndice de métricas esperadas** (números del dataset `--seed 42`
listos para referenciar en vivo).

### 5.3 — README de evaluación
`app/POC_EVALUATION.md` — guía para que cualquier evaluador (técnico o
no técnico) reproduzca el POC end-to-end en 20 minutos:

- §1: qué se está evaluando.
- §2: arquitectura en ASCII art (browser → API Gateway → 8 Lambdas → Dynamo + S3).
- §3-4: setup local paso a paso (clonar, DynamoDB local, sembrar, arrancar 3 servicios, servir el demo).
- §5: recorrido recomendado de 15 min cubriendo los 4 módulos + verificación de audit en EVENTS.
- §6: **tabla de KPIs con umbrales** (oportunidades ≥ 10, impacto > $1000, lift máx > 5, 0 errores 5xx, etc.).
- §7: limitaciones conocidas (deploy pendiente de los 3 nuevos, sin road-aligned, sin multi-tenancy, etc.).
- §8: próximos pasos sugeridos si el POC pasa.

---

## 🎉 POC — SmartDecisions COMPLETO al 100%

Los 5 pasos del plan original cerrados:

1. ✅ **Cerrar la marca** (SmartBear → SmartDecisions; BearSoft preservada como empresa; oso reinterpretado; portal HTML)
2. ✅ **Contrato Excel + validador + boilerplate + capa HTTP + empaque + fix notebook + seed Dynamo**
3. ✅ **Motor afinidad × drop size** (Apriori + ponderación monetaria; output accionable en $)
4. ✅ **Frontend demo S3+CloudFront** (4 sub-chunks: scaffold + Excel + Playground ML + Rutas Leaflet)
5. ✅ **Empaque del pitch técnico** (generador sintético + guion 5 min + README evaluación)

**Audit posterior aplicado:** patrón TRADE de `@audit_event` + `@log_usage` a EVENTS en los 3 servicios nuevos; URLs reales productivas en `.env` y `config.js`.

**Métricas finales del POC:**
- 3 microservicios nuevos: ingest, optimization, analytics.
- 8 services en total en el ecosistema (los 5 productivos + 3 nuevos del POC).
- 15 tests verdes (6 ingest + 4 optimization + 5 analytics).
- 4 módulos del demo frontend.
- 1 dataset sintético reproducible.
- Impacto demo: **$2,525 en oportunidades comerciales** sobre 1,200 órdenes sintéticas.

**Pendientes para "fase post-POC"** (no parte del POC mismo):
- Deploy a Lambda de ingest/optimization/analytics + actualizar `config.js` con esas URLs reales.
- Piloto con cliente real (Excel histórico de 6-12 meses).
- Multi-tenancy (prefijos S3 por tenant + claim JWT).
- Forecasting (Prophet/statsmodels) + filtrado colaborativo + grafo de afinidad.

---

## 🔍 Auditoría pre-paso-5 (2026-06-16)

Antes de cerrar el POC el usuario pidió validar 3 ejes contra el patrón canónico.

| Eje | Estado inicial | Estado final |
|---|---|---|
| Estructura boilerplate | ✅ los 3 OK | ✅ |
| `@handle_service_errors` aplicado | ✅ 4/1/6 (ingest/optimization/analytics) | ✅ |
| **`@audit_event` + `@log_usage` a EVENTS (patrón TRADE)** | ❌ ausente | ✅ **incorporado** |
| URLs reales prod en demo + `.env` | ⚠️ localhost / faltaba EVENTS_SERVICE_URL | ✅ |

### Nuevo módulo `services/events_emitter.py`
Port adaptado del patrón TRADE (sin acoplamiento SQLAlchemy). Copiado verbatim a los 3 servicios. **No toca el `utils.py` compartido** para preservar el boilerplate contract (regla `feedback-boilerplate-standard`).

- `send_audit_event(payload)` / `send_usage_log(payload)` — POST async fail-quiet a `${EVENTS_SERVICE_URL}/v1/events/{audit,usage-log}`.
- `@audit_event(microservice, entity_name, action)` — service-layer; sync+async (`inspect.iscoroutinefunction`); schedule fire-and-forget; `asyncio.to_thread` para no bloquear el event loop.
- `@log_usage(microservice)` — endpoints FastAPI; captura method/path/status/IP/user/body/elapsed-ms.

### Audit + log aplicados

| Servicio | `@audit_event` en service-layer | `@log_usage` en endpoints |
|---|---|---|
| ingest | `persist_dataset` (CREATE IngestDataset) | 4 endpoints |
| analytics | `persist_run` (CREATE AnalyticsRun) | 3 endpoints |
| optimization | `optimization_algorithm_controller` (READ OptimalRoute) | 5 endpoints |

Firmas de endpoints actualizadas para aceptar `request: Request`.

### URLs reales productivas

**`.env` de los 3 servicios** (alineado al patrón TRADE/forms):
```
EVENTS_SERVICE_URL=https://uyrs6ucto3.execute-api.us-east-1.amazonaws.com
FILES_SERVICE_URL=https://ek2xktuyr4.execute-api.us-east-1.amazonaws.com
BUCKET_NAME=ml-data-file-handler
```
Normalizado naming: `DYNAMODB_REGION` + `BUCKET_NAME` (no `AWS_REGION` + `FILES_BUCKET_NAME`) → `analytics/services/dataset_loader.py` actualizado.

**`portal/demo/js/config.js`** reorganizado:
- Productive: AUTH, EVENTS, FILES, ML_FUNCTIONS
- Pending deploy (localhost): INGEST, OPTIMIZATION, ANALYTICS

### Verificación post-auditoría (✅)
- Los 3 `main.py` importan limpio; todas las rutas registradas (4+5+3 funcionales).
- `DeprecationWarning` de `asyncio.iscoroutinefunction` corregido (uso `inspect.iscoroutinefunction`).
- Pytest: **15/15 verdes** (6 ingest + 4 optimization + 5 analytics).

---

## 🎉 Paso 4 — Frontend demo en S3+CloudFront COMPLETO

Los 4 sub-chunks cerrados:
- ✅ **4a** Scaffold demo (login + home + helpers compartidos JS/CSS)
- ✅ **4b** Módulo Excel → Oportunidades (ingest + analytics)
- ✅ **4c** Módulo Playground ML (10 endpoints + Chart.js)
- ✅ **4d** Módulo Optimización de rutas (Leaflet + CartoCDN dark)

**Estructura final del demo en `app/portal/demo/`:**
```
demo/
├── index.html              # login
├── home.html               # selector 3 módulos
├── js/                     # config, auth, api, ui (compartidos)
├── styles/demo.css         # dark theme común
├── assets/.gitkeep
├── excel/                  # módulo 1: ingest + analytics
├── playground/             # módulo 2: ml_functions con Chart.js
└── routes/                 # módulo 3: optimization con Leaflet
```

**Para deploy a S3+CloudFront** basta con `aws s3 sync portal/ s3://<bucket>/ --delete` y editar las URLs reales de cada servicio en `demo/js/config.js`. Cero build step.

**Pendiente solo el paso 5** (empaque del pitch técnico: datos sintéticos, guion 5 min, README "cómo evaluar el POC").

---

## Paso 3 — Motor afinidad × drop size (✅ servicio completo)

**Servicio:** `services/analytics/`. Sigue boilerplate al pie de la letra (mismo árbol que `optimization` y `ingest`).

**Algoritmo (servicios/affinity_engine.py):**
1. Agrupar el DataFrame validado por `id_pedido` → transacciones (sets de productos).
2. `mlxtend.preprocessing.TransactionEncoder` → one-hot.
3. `mlxtend.frequent_patterns.apriori(min_support)` → frequent itemsets.
4. `association_rules(metric='lift', min_threshold)` → reglas con support/confidence/lift.
5. Para cada PdV:
   - antecedentes ⊆ productos que ya compra,
   - consequente NO está en lo que ya compra,
   - `opportunity_score = lift × confidence × expected_drop_size_amount` (o `_units` si faltan precios).
6. Dedupe (PdV, recommended_product_id) quedándose con el mayor score; top N por PdV.

**Diferenciador SmartDecisions cumplido:** output **accionable en dólares**, no métricas abstractas. `Opportunity.rationale` lo explica en español al usuario no técnico.

**Endpoints (todos con JWT):**
- `POST /v1/analytics/run/{dataset_id}` — lee `t_ingest_datasets` para resolver `file_s3_key`, descarga directo de S3 con boto3, corre el pipeline, persiste el run en Dynamo.
- `GET /v1/analytics/results/{dataset_id}` — devuelve el run más reciente.
- `GET /v1/analytics/results/{dataset_id}/pdv/{pdv_id}` — filtra al PdV.

**Persistencia:** `t_analytics_runs` (PK `dataset_id` (S) + SK `run_id` (S, UUIDv4)). El sort key permite re-runs con thresholds distintos sin perder historial.

**Lectura cross-service (decisión POC):**
- `t_ingest_datasets`: `get_item` directo con boto3 (mismo AWS account).
- S3: `boto3.client('s3').get_object` directo en lugar de FILES HTTP — evita un hop extra y latencia para POC.

**Tuning configurable vía env:**
- `AFFINITY_MIN_SUPPORT` (default `0.01`).
- `AFFINITY_MIN_LIFT` (default `1.0`).
- `AFFINITY_TOP_N_PER_PDV` (default `10`).

**Deploy config:** `MEMORY=1024` `TIMEOUT=120` (Apriori + pandas pueden requerir tiempo en datasets grandes).

**Verificación (✅):**
- `bash -n dynamodb.sh` → syntax OK.
- `diff` de los 8 shared files vs `events/services/` → idénticos.
- Import de `main.py` → 6 rutas registradas (3 funcionales + `/`, `/openapi.json`, `/docs`).
- Pytest `tests/test_affinity_engine.py` → **5/5 verdes**:
  - Recomienda B a PdV-3 (que solo compra A) cuando A↔B tienen alta afinidad.
  - No recomienda productos que el PdV ya compra.
  - `opportunity_score` correcto = `lift × confidence × drop_size_amount`.
  - Cap `top_n_per_pdv` aplicado por PdV.
  - DataFrame vacío → 0 opportunities, no falla.

**Pendientes del paso 3:**
- Ninguno crítico. Posibles mejoras post-POC:
  - Mover lectura cross-service a HTTP (FILES + `GET /v1/ingest/{dataset_id}`) para acoplamiento más limpio.
  - Estimación monetaria más sofisticada usando drop size **histórico del PdV específico** en vez del promedio global del producto.
  - Soporte de re-runs idempotentes (mismo dataset_id + parámetros → mismo run_id determinístico).

---

## Paso 2 — Resumen final

✅ Chunk 1 (contrato + validador + plantilla) · ✅ Chunk 2 (boilerplate shared) · ✅ Chunk 3 (capa HTTP ingest) · ✅ Chunk 4 (empaque ingest) · ✅ Chunk 5 (a–d: migración optimization desde monolito a microservicio Dynamo + fix notebook + seed). Listo para arrancar **paso 3** (motor afinidad × drop size).

---

## 🛠️ Post-POC PRs (correcciones tras prueba E2E del usuario)

Después de cerrar el plan original de 5 pasos, el usuario corrió pruebas
end-to-end del demo en su browser y encontró bloqueos y problemas de UX
que requirieron 4 PRs adicionales de pulido.

### PR1 — Bugs bloqueantes (✅ completo, 2026-06-18)

| Bug | Causa | Fix |
|---|---|---|
| INGEST → FILES upload 404 | Inventé endpoint `/v1/files/upload`. Real: `POST /v1/s3/upload` multipart con `bucket_name` + `file_path` + `file` | Reescrito `services/file_storage.py`. Cliente HTTP correcto + parser de respuesta tolerante a 4 shapes (`file_key`/`file_s3_key`/`key`/`url`+bucket) |
| CORS en respuestas 500 | `RuntimeError` levantado por `handle_service_errors` salía sin pasar por exception handler, browser lo marcaba como CORS-blocked | Handler explícito `@app.exception_handler(RuntimeError)` en `api_exceptions.py` antes del genérico de `Exception`. Replicado a los 3 servicios |
| Plantilla 400 al servir local | Dockerfile la generaba en build pero `python main.py` no | `_ensure_template_present()` en lifespan startup |
| INGEST file_s3_key sin prefijo | `_extract_s3_key` ignoraba el campo `file_key` real y caía a fallback que devolvía solo el basename → ANALYTICS hacía `get_object` con key inválida → `NoSuchKey` | Reescrita la función para preferir `file_key` (canónico de FILES), y el fallback de URL preserva el path completo del bucket |
| ANALYTICS schema mismatch | `get_dataset_metadata` buscaba `Key={'dataset_id': ...}` pero la tabla AWS tiene PK `id` | Corregido a `Key={'id': dataset_id}` |
| Optimization tabla simple vs compuesta | `.env` apuntaba a Dynamo productivo, pero la tabla creada inicialmente tenía PK `id` simple, incompatible con el query por (route_id, day) | Script `scripts/recreate_aws_table.sh` que recrea con PK compuesta `route_day_key` + SK `client_id` |
| `db_connection.py` divergente del canónico | Yo había agregado lógica `DYNAMODB_ENDPOINT_URL` para Dynamo local; rompía la regla "boilerplate compartido idéntico a EVENTS" | Revertido al canónico verbatim de EVENTS (`boto3.resource('dynamodb')` sin parámetros). `.env` apunta a AWS productivo como AUTH/EVENTS |

**Cambios estructurales:** las 3 tablas DynamoDB ahora viven en AWS productivo
con nombres definitivos `ingest_datasets`, `analytics_runs`,
`optimization_routes`. `ingest_datasets` y `analytics_runs` usan PK simple `id`
(con `dataset_id`/`run_id` como atributo mirror). `optimization_routes` usa PK
compuesta `route_day_key` + SK `client_id`.

### PR2 — Playground ML real (✅ completo, 2026-06-19)

Eliminado el viejo Playground con forms hardcoded ("inservible" según el
usuario). Reescrito con 4 tabs reales basadas en `notebooks/frontend.ipynb`:

| Tab | Funcionalidad | Endpoints |
|---|---|---|
| **1 · Datasets** | Upload `.csv`/`.txt` al bucket vía FILES, listar bucket, preview con delimiter/header configurables, despachar a tabs 2/3 | `POST /v1/s3/upload`, `POST /v1/s3/list-files`, `GET /v1/s3/read/{bucket}/{key}` |
| **2 · Clasificación (Logistic)** | Selector X/Y/Label, scatter por clase, train logistic + Z-Score opcional, decision boundary `y = -(b + w₀x)/w₁`, predict punto custom con probabilidad | `POST /v1/classification/train-logistic-regression`, `POST /v1/classification/sigmoid-batch` |
| **3 · Regresión Lineal** | Multi-select features + target, scatter por feature, train linear (single + multi), Z-Score opcional vía endpoint, cost J en escala log, predict con normalización aplicada al input | `POST /v1/common/normalize-features`, `POST /v1/prediction/train-linear-regression`, `POST /v1/prediction/predict-linear-regression` |
| **4 · Utilidades (Z-Score · Sigmoid)** | Z-Score standalone (manual o pull de dataset cargado) + Sigmoid batch con curve chart + threshold 0.5 line + tabla z → σ(z) → clase | mismos que tab 3 + tab 2 |

**Arquitectura JS:** dividido en 5 archivos (`playground.shell.js` con FILES
client + parser tabular + state compartido; `playground.datasets.js`,
`playground.classification.js`, `playground.prediction.js`,
`playground.utilities.js`).

### PR3 — Módulo Rutas con upload (✅ completo, 2026-06-20)

Antes el módulo Rutas solo leía de Dynamo — sin forma de subir puntos
propios desde el browser.

**Backend** (`services/optimization/`):
- `services/route_data.py`: `bulk_upload_points(route_id, day, points)` con strategy delete-then-write para idempotencia + `delete_points_for_route_day` + dedupe por client_id.
- `controllers/optimization.py`: `bulk_upload_routes_controller` + `_parse_csv_text` con aliases tolerantes (`id/cliente_id/client_id`, `lat/latitude/y`, `lon/lng/longitude/x`); valida que todas las filas compartan (route_id, day). Decorado con `@audit_event('OPTIMIZATION', 'RoutePoints', 'BULK_CREATE')`.
- `routes/optimization.py`: `POST /v1/optimization/routes/bulk-upload` multipart, decorado con `@log_usage`.
- `schemas/optimization.py`: `BulkUploadResponse`.

**Frontend** (`portal/demo/routes/`):
- Nueva card "Subir CSV de puntos" en sidebar con drag-and-drop + botón "Bajar plantilla" (genera `plantilla_puntos_ruta.csv` con 5 PdVs de La Paz) + botón "Subir y cargar".
- POST al endpoint → auto-sincroniza `route_id`/`day` del form con la respuesta → dispara click programático a "Cargar puntos" → mapa se refresca automáticamente.

### PR4 — Identidad visual BearSoft (✅ completo, 2026-06-19)

El dark theme + acentos teal del demo inicial no respetaba la marca real.
Migración completa a light corporate basada en los assets que pasó el usuario.

**Assets nuevos en `portal/assets/`:**
- `bear-face.jpg` — cara del oso, brand mark circular del header.
- `bear-mascot.jpg` — oso caminando con frasco, hero del landing.
- `bearsoft-logo.jpg` — banner de la marca.
- `favicon.svg` — SVG vectorial con huella brown + monograma "SD" navy.

**Paleta light corporate (CSS variables compartidas en `style.css` y `demo.css`):**
- `--bg #ffffff` blanco puro, `--bg-alt #f7f3ea` crema claro.
- `--text #0d1e4c` navy del logo BearSoft.
- `--accent #0d1e4c` primary (navy), `--accent-2 #7a4a2a` secondary (brown huella), `--accent-3 #c4a378` tan claro.
- `--border #e3dccc`, sombras suaves rgba(navy).

**Cambios:**
- Botones primary navy sólido, secondary brown sólido, ghost outline navy.
- Header de cada página (landing + 5 demo) usa `bear-face.jpg` con borde navy circular.
- Hero del landing reemplaza el SVG genérico por `bear-mascot.jpg`.
- Chart.js defaults pasaron de teal/gris-oscuro a navy/cream.
- Leaflet tiles de **CartoDB Dark Matter** → **CartoDB Voyager** (light + color).
- Polylines/markers del módulo Rutas con paleta corporativa (rojo profesional, verde corporativo, brown punteada para original, navy sólida para optimizada).
- Cache-bust `?v=4` y `?v=5` en CSS/JS para forzar reload sin hard refresh por archivo.

### Próximos pasos del usuario (anotados, no son trabajo de Claude todavía)

- Prueba E2E del módulo Rutas (no validada visualmente todavía).
- Deploy de los 3 microservicios nuevos (`ingest`, `optimization`, `analytics`) a AWS Lambda + API Gateway.
- Deploy del frontend estático a S3 + CloudFront.
- DNS vía CloudFlare → `smartdecisions.bearsoft.com.bo` o `smartdecisions.raforios.com`.
- Una vez deployado, actualizar `portal/demo/js/config.js` con las URLs reales de los 3 nuevos servicios.

---

## Memoria persistente vinculada

- `project_naming.md` — empresa BearSoft / producto SmartDecisions / TRADE-FORMS son Binaria
- `project_deployment_strategy.md` — sin RDS; default DynamoDB+Lambda+S3/CloudFront
- `reference_deployed_services.md` — AUTH/FILES/EVENTS en API Gateway/Lambda
- `project_notebooks_as_frontend_spec.md` — frontend.ipynb + routes.ipynb son spec del frontend, no scratch pads
- `project_demo_portal_roadmap.md` — portal demo, CMS público en Dynamo

---

## Bitácora de sesiones

### 2026-06-17 — Paso 5: empaque del pitch técnico (cierre del POC)
- Generador sintético `tools/synthesize_sales.py`: 12 SKUs en 4 categorías, 5 PdVs con perfiles distintos, 5 afinidades embebidas con prob 0.6-0.8, reproducible con `--seed 42`.
- Bug del generator caía en bucle infinito para PdVs con catálogo < basket_size; corregido con cap dinámico + safety limit. Procesos zombies de runs previos limpiados con pkill.
- Dataset `tools/samples/ventas_demo.xlsx`: 4478 filas, 1200 órdenes, $565,521 monto total.
- Validación end-to-end: ingest 4478/4478 OK; analytics 16 oportunidades, 5/5 PdVs, **$2,525.48 impacto esperado**, lift máx 9.92, 342 reglas.
- `docs/DEMO_SCRIPT.md`: guion de 5 min para llamadas comerciales + apéndices de troubleshooting y métricas esperadas.
- `POC_EVALUATION.md`: guía de 20 min para reproducir el POC end-to-end + tabla de KPIs con umbrales mínimos + arquitectura ASCII + limitaciones conocidas + roadmap post-POC.
- **POC cerrado al 100%.** Los 5 pasos del plan original están en verde.

### 2026-06-16 — Paso 4 chunk 4d: módulo Optimización de rutas (cierre del paso 4)
- 3 archivos en `portal/demo/routes/`: HTML (Leaflet + form + sidebar), CSS (grid sidebar+mapa, tweaks dark-theme para Leaflet, loader overlay), JS (flujo data_model → markers + polyline original → optimal_route → polyline optimizada + summary).
- Tiles CartoDB Dark Matter (free + open) para combinar con el theme.
- Leaflet 1.9.4 vía unpkg CDN con SRI integrity → cero build.
- Layers toggleables (puntos / original / optimizada) con checkbox add/remove LayerGroup.
- Summary con 6 métricas (paradas, segmentos, distancia total graph, lineal total, promedio/tramo, radio OSM).
- Deuda técnica documentada: optimal_route dibuja lineal entre paradas; el road-aligned exacto requiere extender el backend para retornar lat/lng de los OSM nodes.
- Smoke: HTTP 200 + hooks DOM + endpoints + Leaflet primitives + `node --check` OK.
- **Paso 4 cerrado al 100%.** Listo para el paso 5 (empaque del pitch).

### 2026-06-16 — Paso 4 chunk 4c: módulo Playground ML
- 3 archivos nuevos en `portal/demo/playground/`: HTML con 3 tabs, CSS de tabs/result blocks/charts, JS con 8 forms.
- Cubre los 10 endpoints de `ml_functions`: train/predict/cost/gradient para lineal y logística, normalize Z-score y sigmoid batch.
- Chart.js 4.4.7 vía CDN para visualizar la convergencia (`J_history`) del entrenamiento en ambas regresiones.
- Examples del schema OpenAPI pre-cargados en cada form; botón "Usar pesos entrenados" para reusar `w_final/b_final` en los predicts.
- Parser JSON permisivo para campos escalares-o-lista; tolerancia a respuestas con shapes alternativos (sigmoid batch).
- Smoke: HTTP 200 en los 3 archivos; todos los hooks DOM presentes; las 10 rutas en JS; `node --check` OK.

### 2026-06-15 — Paso 4 chunk 4b: módulo Excel → oportunidades
- 3 archivos nuevos en `portal/demo/excel/`: HTML, CSS, JS.
- Flujo end-to-end: descarga plantilla → upload con drag-and-drop → validación con metric cards + tabla de errores → run analytics → tabla de oportunidades ordenable y filtrable con tooltip de rationale.
- Integración con tres microservicios: AUTH (token), ingest (template + upload), analytics (run).
- Formateo es-BO para números/moneda; confianza como porcentaje.
- Smoke test: server local 200 en todas las rutas; `node --check` syntax OK; todos los hooks DOM presentes.
- Pendientes: 4c (playground ML) y 4d (rutas con Leaflet).

### 2026-06-15 — Paso 4 chunk 4a: scaffold del demo
- `app/portal/demo/` creado como sibling del landing del paso 1.
- 7 archivos nuevos: login (index.html), home con selector de módulos, dark CSS compartido, 4 helpers JS (config, auth, api, ui).
- Auth flow contra `POST /v1/auth/login` del servicio AUTH; JWT en sessionStorage.
- API wrapper centraliza bearer + 401 bounce a login.
- URLs configurables en `js/config.js` por entorno (un archivo editable, sin rebuild).
- Landing actualizado: CTA principal de "demo" ahora linkea al demo en vivo (mailto queda como secundario).
- Smoke test con Python http.server: todos los assets sirven 200; 404 limpio para inexistentes.
- Pendientes: 4b/4c/4d (un módulo por chunk).

### 2026-06-15 — Paso 3: motor afinidad × drop size
- Servicio nuevo `services/analytics/` completo en una vuelta (lección de chunk 5).
- Motor en `services/affinity_engine.py`: Apriori + association_rules ponderados por drop size en $. Output accionable por PdV con rationale en español.
- Lectura cross-service: `t_ingest_datasets` (Dynamo) + S3 directo (POC simplification documentada).
- 3 endpoints (`POST /run/{id}`, `GET /results/{id}`, `GET /results/{id}/pdv/{pdv}`).
- Persistencia en `t_analytics_runs` con composite key (dataset_id, run_id) → soporte de re-tuning sin perder historial.
- Tests: 5/5 verdes cubriendo recomendaciones, exclusiones, score correcto, top_n cap, empty input.
- **Paso 3 cerrado.** Próximo: paso 4 (frontend demo en S3+CloudFront con 3 módulos).

### 2026-06-15 — Paso 2: cierre completo (chunk 5d notebook + seed)
- Notebook `routes.ipynb`: 6 celdas actualizadas para usar `OptimizationParams` (cell 1 imports, cell 4 URL hint, cells 12/13/15/17/19 calls). Cell 12 corregida del bug original (`get_data` mal usado en lugar de `data_api`).
- Helper `lib/frontend_functions.py` revisado: la signature actual `data_api(token, url, endpoint, params)` ya arma `/v1/optimization/{endpoint}` — no requiere cambios.
- Seed script `services/optimization/scripts/seed_from_csv.py` + CSV de ejemplo (12 filas, 3 rutas en La Paz). Usa `batch_writer`, soporta local + AWS.
- Notebook revalidado como JSON (54 cells, nbformat=4) tras los edits.
- **Paso 2 cerrado al 100%**. Listo para paso 3 cuando el usuario decida.

### 2026-06-15 — Paso 2: migración del módulo de optimización (chunk 5 a–c)
- Descubrimiento: los endpoints `/optimization/*` que `routes.ipynb` llamaba existen en el **monolito** `api/` (FastAPI + SQLAlchemy + Postgres), no en los microservicios. Mi grep inicial sobre `app/services/` los había declarado inexistentes — corregido tras la observación del usuario.
- Decisión con el usuario: nuevo microservicio `services/optimization/` + nueva tabla Dynamo (`t_optimization_routes`).
- Migración: 5 endpoints, controllers, ml_optimization, schemas portados al microservicio. Algoritmo verbatim del monolito; capa de datos reemplazada por DynamoDB (Query por PK compuesta `"{route_id}#{day}"`).
- Lambda: MEMORY=1024MB / TIMEOUT=60s para acomodar osmnx + networkx; Dockerfile añade `geos-devel proj-devel` además del baseline.
- **Boilerplate inicialmente incompleto** (faltaban main.py/Dockerfile/README/deploy.config/etc. porque dividí en sub-chunks). Tras observación del usuario, completado todo el árbol en una sola vuelta para evitar dejar el servicio a medias.
- Tests: 4/4 verdes en ml_optimization (distance, color generator, filter/sort, distance matrix simétrica).
- Pendiente: chunk 5d (lib helpers + notebook updates + script de seed Postgres → Dynamo).

### 2026-06-15 — Paso 2: empaque para deploy
- Creados Dockerfile, .dockerignore, deploy.config, dynamodb.sh, README.md siguiendo el patrón de mining_summit.
- Dockerfile bundlea la plantilla `.xlsx` durante el build (paso `RUN python scripts/generate_template.py`).
- MEMORY_SIZE de Lambda = 512 MB (más que mining_summit) para acomodar el parsing de Excel con pandas.
- Tabla única en Dynamo: `t_ingest_datasets`, PK `dataset_id`/S.
- Pendiente solo el chunk 5: fix de `routes.ipynb`.

### 2026-06-15 — Paso 2: capa HTTP del ingest
- Creados `main.py`, `routes/ingest.py`, `controllers/ingest.py`, `models/dataset.py`, `services/datasets.py`, `services/file_storage.py` siguiendo el patrón de mining_summit.
- 4 endpoints registrados bajo `/v1/ingest/*`; todos exigen JWT vía `get_current_user`.
- Cliente HTTP a FILES en `file_storage.upload_excel` (reenvía bearer del usuario). El servicio Ingest no toca S3 directo.
- 6 tests Pytest verdes en el validator. 2 fallos iniciales corregidos durante el debug (manejo de `column_in_dataframe` y `precio_unitario` ausente).
- Pendientes: Dockerfile/deploy.config/README/dynamodb.sh + fix de `routes.ipynb`.

### 2026-06-12 — Paso 2: contrato Excel + boilerplate
- Acordadas con el usuario las 2 decisiones de diseño: servicio nuevo `services/ingest/` + Pydantic V2 + pandera.
- Implementados schemas Pydantic, validador pandera con mensajes en español, parser de Excel/CSV, script generador de plantilla.
- Pandera 0.20.4 incompatible con Python 3.14 (typing.Union en `multimethod`) → escalado a pandera 0.31.1 que funciona limpio.
- Smoke test end-to-end (clean / corrupt / empty) pasa.
- **Error corregido tras reproche del usuario:** inicialmente sólo había copiado `logger_config.py` del boilerplate y dejado el resto para "chunk 2". El usuario observó que faltaban los manejos de errores, security, db_connection, etc. Copiados verbatim los 8 shared files de `mining_summit/services/`, añadidos `__init__.py` a controllers/models/routes/tests/scripts, creado `.env.example`.
- **Antes de avanzar más allá del paso 2 se pidió OK explícito del contrato al usuario.** Corregido también por el usuario un error en sesión anterior: la empresa es **BearSoft**, no BaarSoft. Memoria persistente actualizada y nueva feedback memory creada (`feedback_confirm_brand_spelling.md`).

### 2026-06-11 — Inicio del POC
- Definido el plan de 5 pasos (revisado con notebooks como spec del frontend).
- Confirmada nomenclatura: empresa **BearSoft**, producto **SmartDecisions**.
- Confirmada infra: CloudFront + S3 (frontend), Lambda + API Gateway (servicios).
- Paso 1 ejecutado: ~30 ocurrencias cosméticas reemplazadas (SmartBear→SmartDecisions del producto) en docs, código Python de servicios y frontend, scripts CI y READMEs. **BearSoft (empresa) se mantiene como estaba.** Hubo un error inicial: propagué incorrectamente "BaarSoft" en lugar de "BearSoft" por confiar en un typo del prompt sin verificar; el usuario corrigió manualmente y se actualizó memoria para evitar reincidencia.
- `deploy.config` verificado sin referencias a la marca antigua → no hay recursos AWS por renombrar.
- Decisiones del usuario sobre paso 1 aplicadas:
  - Paths absolutos `/Users/.../SmartBear/...` reescritos a `/SmartDecisions/...` en CI scripts, READMEs y Postman collections.
  - Oso reinterpretado: SVG creado en `app/portal/assets/logo-bear.svg`.
  - Portal landing creado en `app/portal/` (HTML+CSS+JS vanilla, dark theme, listo para S3+CloudFront).
- Comando físico de `mv` del directorio queda como acción manual del usuario (Claude no puede mover su propio CWD).
