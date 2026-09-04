# ⛏️ Mining-Analysis-Service 📊

Bienvenido al microservicio de **Análisis Minero**, un componente estratégico dentro de la arquitectura de la API **SMARTBEAR**. Este servicio actúa como un **Data Warehouse** especializado en el sector minero, permitiendo la ingesta, normalización y análisis avanzado tanto de cotizaciones de minerales como de la recaudación de regalías mineras, impulsando la generación de KPI's críticos.

---

## 🎯 Propósito Principal

El **Mining-Analysis-Service** está diseñado para centralizar la inteligencia de mercado y la gestión financiera del sector minero. Su propósito es transformar datos operativos brutos en información estratégica para la toma de decisiones. Sus funcionalidades clave incluyen:

* **Motor ETL Especializado:** Capacidad dual para procesar archivos CSV (cotizaciones diarias con limpieza automática de formatos numéricos latinos) y archivos Excel (liquidaciones y transacciones de regalías procesadas directamente en memoria).
* **Data Warehouse Relacional:** Almacena de forma eficiente y normalizada el catálogo de minerales (`t_minerals`), histórico de precios (`t_mining_prices`), padrón de operadores mineros (`t_companies`) y el desglose de distribución de regalías a nivel departamental y municipal (`t_royalties` y `t_royalty_transactions`).
* **Interconexión Institucional:** Provee **endpoints** seguros para que otras instituciones puedan consultar históricos de precios y resúmenes de recaudación de manera estandarizada.
* **Módulo de BI Integrado:** Diseñado para alimentar interfaces analíticas (como Streamlit), entregando estructuras de datos optimizadas para visualizaciones de tendencias, variaciones porcentuales (YOY/MoM) y distribución geográfica de recursos.
* **Auditoría y Trazabilidad:** Identificación precisa del usuario que ejecuta las cargas masivas con registros detallados en los logs del sistema, asegurando el seguimiento de operaciones financieras sensibles.

---

## 🛠️ Tecnologías Utilizadas

Este microservicio sigue los estándares de alta disponibilidad, precisión financiera y robustez de la arquitectura SmartDecisions:

* **Lenguaje:** Python 3.14 🐍
* **Framework Web:** FastAPI ✨
* **Servidor ASGI:** Uvicorn 🚀
* **ORM & Base de Datos:** SQLAlchemy (MySQL)
* **Validación de Datos:** Pydantic
* **Procesamiento de Datos:** Pandas 🐼
* **Seguridad:** JWT (Integrado con Central Auth Service)
* **Contenedorización:** Docker 🐳

---

## 🚀 Endpoints de la API

A continuación se listan los **endpoints** principales de la API, agrupados por su dominio de datos para una mejor referencia.

### Cotizaciones y Precios de Minerales

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/v1/mining-analysis/etl/upload` | Carga masiva de cotizaciones mineras desde un archivo CSV. Dispara proceso de normalización y auditoría. |
| `GET`  | `/v1/mining-analysis/prices` | Recupera el listado completo de precios históricos, incluyendo la metadata de cada mineral. |
| `GET`  | `/v1/mining-analysis/reports/daily?date=YYYY-MM-DD` | Devuelve la cotización más reciente por mineral del catálogo oficial hasta la fecha indicada, con `is_fallback = true` cuando se usa un día anterior. Incluye `previous_price_low` y `change_pct` (variación vs. día previo con dato). Insumo del reporte interno **Minerales_01**. |
| `GET`  | `/v1/mining-analysis/reports/biweekly?year=YYYY&month=MM&half=1\|2` | Promedio simple de `price_low` por mineral en la quincena solicitada (`half=1` cubre los días 1-15; `half=2` cubre del 16 al fin de mes). Cuando no hay datos en el periodo, retrocede hasta hallar la quincena más reciente con cotizaciones. Insumo del reporte oficial **Minerales_02**. |

### Endpoints públicos (sin JWT) para el sitio institucional

Pensados para `mineria.gob.bo` y otros consumidores anónimos. El default del regex CORS ya cubre `*.mineria.gob.bo` (además de `*.bearsoft.com.bo`, `*.cloudfront.net` y `localhost`), así que no requieren configuración extra. Para otros dominios de terceros, agrégalos a `CORS_ALLOWED_ORIGINS` (lista CSV) o ajusta `CORS_ALLOWED_ORIGIN_REGEX`.

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `GET`  | `/v1/mining-analysis/public/reports/daily?date=YYYY-MM-DD` | Idéntico a `/reports/daily` pero anónimo. |
| `GET`  | `/v1/mining-analysis/public/reports/biweekly?year=&month=&half=` | Idéntico a `/reports/biweekly` pero anónimo. |
| `GET`  | `/v1/mining-analysis/public/reports/biweekly/history?from=YYYY-MM-DD&to=YYYY-MM-DD` | Serie histórica de quincenas con datos, ordenada cronológicamente. `from`/`to` opcionales (defaults a `MIN`/`MAX` de `t_mining_prices`). |
| `GET`  | `/v1/mining-analysis/public/reports/daily/{png\|pdf}?date=YYYY-MM-DD` | Reporte diario renderizado sobre la plantilla **Minerales_01** (binario, descarga directa). |
| `GET`  | `/v1/mining-analysis/public/reports/biweekly/{png\|pdf}?year=&month=&half=` | Reporte quincenal renderizado sobre la plantilla **Minerales_02** (binario, descarga directa). |

### Regalías Mineras y Transacciones

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `POST` | `/v1/mining-analysis/royalties/upload` | Ejecuta el proceso ETL en memoria a partir de un archivo Excel con las liquidaciones oficiales del SIN. |
| `GET`  | `/v1/mining-analysis/royalties/summary` | Obtiene el resumen agregado de coparticipación de regalías mineras (recaudación bruta, comisiones y distribución neta a gobernaciones y municipios). Soporta filtrado por gestión fiscal. |
| `GET`  | `/v1/mining-analysis/royalties/transactions` | Recupera un análisis granular de las transacciones de pago de regalías agrupadas por empresa operadora (NIT), municipio y gestión. |

### Utilidades y Salud

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `GET` | `/` | Healthcheck del servicio, estado de la conexión a la base de datos y validación del entorno. |
| `GET` | `/docs` | Documentación interactiva Swagger UI con esquemas detallados de Request/Response. |

---

## 🗂️ Estructura del Microservicio

```txt
mining_analysis/
├── controllers/
│   ├── __init__.py
│   └── mining_analysis.py
├── models/
│   ├── __init__.py
│   └── mining_analysis.py
├── routes/
│   ├── __init__.py
│   └── mining_analysis.py
├── schemas/
│   ├── __init__.py
│   └── mining_analysis.py
├── services/
│   ├── __init__.py
│   ├── api_exceptions.py
│   ├── crud.py
│   ├── db_connection.py
│   ├── environment.py
│   ├── exceptions.py
│   ├── logger_config.py
│   ├── mining_analysis.py
│   ├── royalties_etl.py
│   ├── security.py
│   └── utils.py
├── .dockerignore
├── .env
├── .gitignore
├── deploy.config
├── Dockerfile
├── Dockerfile.api
├── main.py
├── README.md
├── requirements.txt
└── seed_locations.txt
```

---

## 📀 Ejecución Local

Para levantar el microservicio en tu entorno de desarrollo local, sigue estos pasos:

1. **Instalar dependencias:**
   ```shell
   pip install -r requirements.txt
   ```

2. **Configurar Variables de Entorno:** Renombra o crea un archivo `.env` en la raíz del proyecto y ajusta las credenciales de conexión a MySQL, así como la URL del servicio de autenticación central.

3. **Iniciar el Servicio:**
   ```shell
   python main.py
   ```
   *(El servidor se iniciará típicamente en `http://localhost:3000`, y podrás acceder a la documentación en `/docs`).*

---

## 🧰 Scripts Operativos

Viven en `scripts/` y se ejecutan como módulos, para que respeten el
`PYTHONPATH` del microservicio. **Los que escriben exigen `--yes`**; sin esa
bandera imprimen el plan y salen sin tocar nada.

### La rutina de cada quincena, en orden

Estos tres se usan juntos, cada 15 días, cuando llega el PDF del Ministerio:

**1. `audit_decimals.py` — antes de cargar.** Solo lee. El PDF oficial publica
con dos decimales (`WÓLFRAM 64205.75`); al re-tipearlos al Excel consolidado a
veces se pierden y quedan enteros. Este auditor recorre cada hoja `Diario`,
cruza el promedio que trae el Excel contra el promedio aritmético de los días, y
lista las celdas que hay que verificar contra el PDF. No corrige nada: dice
dónde mirar.

```shell
python -m scripts.audit_decimals                       # usa data/cotizaciones_mineras_bolivia.xlsx
python -m scripts.audit_decimals --source /ruta.xlsx --tolerance 0.01
```

**2. `ingest_pdf_xlsx.py` — la carga.** Lee las hojas `{Mes} Q{1|2} - Diario`
del Excel consolidado y las inserta en `t_mining_prices`. Idempotente: omite las
fechas que ya tienen registro, así que volver a correrlo sobre el mismo archivo
no duplica nada.

```shell
python -m scripts.ingest_pdf_xlsx --source /ruta/cotizaciones_mineras_bolivia.xlsx --yes
```

**3. `migrate_to_dynamodb.py` — publicar a la nube.** El ETL escribe en el
relacional y el servicio desplegado lee de DynamoDB, así que la quincena recién
cargada hay que empujarla. Idempotente: cada escritura es un put por clave.

```shell
python -m scripts.migrate_to_dynamodb            # informa qué copiaría
python -m scripts.migrate_to_dynamodb --yes      # copia y verifica
```

### El que no se ejecuta

**`cli_support.py` — no se ejecuta.** Es el andamiaje que comparten los demás:
abre la sesión de base de datos, la cierra bien y aborta si el archivo fuente no
existe. Estaba escrito dos veces con formas distintas; vive acá una sola vez.

---

## 🧪 Pruebas

```shell
pytest -v
```

Suite enfocada en:
- `clean_currency_pro` (formato anglo vs. europeo, casos límite y la regresión Bismuto `17.54 → 1754`).
- Servicio de reporte diario con fallback al registro previo más reciente.
- Servicio de reporte quincenal con promedio sobre días disponibles, fallback al periodo anterior y manejo de `half` inválido.
- Idempotencia del seed `ensure_official_minerals`.

---

## ☁️ Despliegue y persistencia conmutable

El servicio corre sobre **MySQL/PostgreSQL o DynamoDB**, según
`PERSISTENCE_BACKEND` en el `.env`:

| Valor | Qué usa |
|---|---|
| `sql` | El motor relacional de `DB_HOST`/`DATABASE`. |
| `dynamodb` | Las tablas `minerals` y `mining_prices`. |

**En AWS tiene que ser `dynamodb`:** no hay RDS levantado. Para trabajar local
contra el MySQL del Docker, cambia el valor a `sql`. La suite de pruebas queda
fijada al camino SQL desde `tests/conftest.py`, así que no depende de lo que
diga el `.env` ni toca AWS.

### Tablas

Las crea `services/ci/api/create_dynamodb_tables.sh`, que sabe de claves
compuestas:

| Tabla | Partición | Ordenamiento |
|---|---|---|
| `minerals` | `mineral_id` (S) | — |
| `mining_prices` | `mineral_id` (S) | `date` (S, ISO) |

La clave de ordenamiento es lo que permite leer "este mineral entre estas dos
fechas" en una sola consulta, que es como se lee siempre.

### Permisos

El rol del Lambda recibe `AmazonDynamoDBFullAccess` del propio
`build_and_deploy.sh`, así que las dos tablas quedan cubiertas sin pasos
extra.

### Proceso quincenal del boletín (Ministerio)

El ETL escribe **solo** en el relacional; las lecturas sí saben de los dos
motores. Hasta que la escritura también pase por `prices_store`, la quincena se
carga contra MySQL local y después se empuja a la nube:

```bash
# 1. Levantar el servicio contra MySQL, sin tocar el .env
PERSISTENCE_BACKEND=sql python main.py

# 2. Subir el xlsx desde el Streamlit (apunta a http://localhost:3020)
#    y generar el boletín PDF/PNG como siempre.

# 3. Empujar la quincena nueva a DynamoDB
python -m scripts.migrate_to_dynamodb --yes
```

### Apuntar el Streamlit al servicio desplegado

`demo/utils/config.py` lee `API_BASE_URL` del entorno y su default es
`http://localhost:3020/v1/mining-analysis`; sin esa variable el Streamlit
siempre golpea localhost, aunque el Lambda esté arriba.

```bash
export API_BASE_URL="https://jvxmqeg601.execute-api.us-east-1.amazonaws.com/minig_analysis/v1/mining-analysis"
streamlit run app.py
```

**Sirve para consultar, no para cargar.** Contra AWS las lecturas funcionan
—`/prices`, los reportes diario y quincenal, el PDF y el PNG—, pero
`POST /etl/upload` escribe en el relacional y en el Lambda no hay ninguno. La
carga de la quincena se hace con el servicio local, según el flujo de arriba.

El paso 3 es idempotente: reescribe lo que ya estaba con los mismos valores y
agrega lo nuevo.

### Migrar el histórico

El ETL carga el MySQL local; DynamoDB arranca vacío. Para copiar el histórico:

```bash
python -m scripts.migrate_to_dynamodb          # informa qué copiaría
python -m scripts.migrate_to_dynamodb --yes    # copia y verifica
```

Lee siempre del relacional y escribe en DynamoDB, sea cual sea el
`PERSISTENCE_BACKEND`. Es idempotente: cada escritura es un put por clave, así
que correrlo dos veces deja el mismo estado. Usa como partición el mismo
identificador numérico que expone el camino SQL (`str(row.id)`), que es lo que
mantiene los dos backends hablando del mismo mineral.

## 👤 Creado Por

**Rafael Ríos Bascón** [raforios@gmail.com](mailto:raforios@gmail.com)
