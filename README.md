# BearSoft — SmartDecisions y SmartBilling

Monorepo de **BearSoft**. Contiene los microservicios, los portales web y las
herramientas de dos productos propios:

- **SmartDecisions**: análisis financiero, comercial y de minerales para
  tomar decisiones con los datos que la empresa ya tiene en su ERP.
- **SmartBilling**: facturación de comercios, con las farmacias como primer
  vertical. Se vende solo o junto a SmartDecisions.

Ambos se apoyan en los mismos servicios base (autenticación, auditoría,
archivos, cálculos y explicaciones con IA) y se publican detrás de una sola
dirección de API: **`https://api.bearsoft.com.bo/v1/<servicio>/…`**.

En el repositorio también viven, por conveniencia, servicios de clientes
(Binaria y el Ministerio de Minería). Están en la sección
[Servicios de clientes](#servicios-de-clientes) y no forman parte de los
productos.

---

## Documentos de referencia

| Documento | Qué contiene |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | Reglas técnicas del proyecto: arquitectura, configuración, datos y protocolo de trabajo. Es la fuente única. |
| [`SMARTDECISIONS.md`](SMARTDECISIONS.md) | Estado del producto, decisiones vigentes y lo último que se hizo. |
| [`docs/parametros.md`](docs/parametros.md) | Definición única de los valores de negocio de cada servicio. |
| [`docs/cambios/`](docs/cambios) | Planes de trabajo por producto. |
| [`docs/siat/`](docs/siat) | Anexo técnico de facturación del SIAT (Impuestos Nacionales). |
| `.claude/rules/`, `.claude/skills/`, `.claude/agents/` | Estándares de código, procedimientos y revisiones automáticas. |
| `services/<servicio>/README.md` | Documentación técnica de cada microservicio, en inglés. |

---

## Servicios

Todos son **Python 3.14 + FastAPI**, corren en **AWS Lambda** (con Mangum) y
guardan sus datos en **DynamoDB**. Cada uno sigue las mismas cinco capas:
`schemas/`, `models/`, `routes/`, `controllers/` y `services/`.

### Base — los usa todo producto

| Servicio | Carpeta | Ruta en el gateway | Para qué |
|---|---|---|---|
| AUTH | `services/auth` | `/v1/auth`, `/v1/users` | Usuarios, roles y emisión de tokens JWT (con `client` y `role`). |
| EVENTS | `services/events` | `/v1/events` | Auditoría (quién cambió qué) y registro de uso de cada endpoint. |
| FILES | `services/files` | `/v1/s3` | Subir, leer y borrar archivos en S3. Ningún otro servicio toca un bucket. |
| ML_FUNCTIONS | `services/ml_functions` | `/v1/prediction`, `/v1/classification`, `/v1/routing`, `/v1/common` | Cálculos comunes: pronósticos, clasificaciones y rutas. No guarda nada: recibe el objeto completo y devuelve el resultado. |
| AI | `services/ai` | `/v1/ai` | Explicaciones en lenguaje natural con Amazon Bedrock. |

### Independiente

| Servicio | Carpeta | Ruta en el gateway | Para qué |
|---|---|---|---|
| QUOTES | `services/quotes` | `/v1/quotes` | Tipo de cambio oficial y factores externos, generales y de cada empresa. Lo usan SmartDecisions y SmartBilling. |

### SmartDecisions

| Servicio | Carpeta | Ruta en el gateway | Para qué |
|---|---|---|---|
| COMMERCIAL | `services/commercial` | `/v1/commercial` | Cargas de ventas, clientes y stock; análisis comerciales (segmentación, pronóstico, afinidad, cartera, objetivos) y rutas de vendedores. |
| FINANCE | `services/finance` | `/v1/finance` | Análisis Financiero: catálogo de cuentas, balance general, estado de resultados, impuestos, modelo de negocio y proyección. |
| MINING_ANALYSIS | `services/mining_analysis` | `/v1/mining-analysis` | Cotizaciones de minerales y la recomendación «vender hoy o esperar». |

### SmartBilling

| Servicio | Carpeta | Ruta en el gateway | Para qué |
|---|---|---|---|
| BILLING | `services/billing` | `/v1/billing` | Productos e inventario por lote, compras, ventas, caja, alertas y configuración de cada comercio. La facturación SIAT se documenta en `docs/siat/`. |

### Cómo se relacionan

- Cada servicio **arranca solo**: no depende de otro para levantar. Si una
  opción necesita a otro servicio y éste no responde, esa opción falla con su
  código, pero el servicio sigue respondiendo.
- Lo ajeno se pide **por HTTP** al dueño, siempre a través de `API_URL`
  (`{API_URL}/v1/<servicio>/…`).
- Todo endpoint exige el token de AUTH. Todo controlador reporta su uso a
  EVENTS, y los que cambian algo dejan registro de auditoría.
- Un cálculo común vive una sola vez, en ML_FUNCTIONS.

---

## Configuración y parámetros

- El **`.env`** de cada servicio sólo lleva configuración: entorno, nombres
  de tablas y buckets, URLs, credenciales y timeouts. Ningún valor puede
  llevar coma ni llave.
- Los **valores de negocio** (plazos, decimales, umbrales, parámetros de
  modelos) viven en la tabla `<servicio>_parameters` de cada servicio. Lo que
  cambia por empresa vive en otra tabla del mismo servicio. La definición
  está en [`docs/parametros.md`](docs/parametros.md) y se siembra con:

  ```bash
  python -m tools.seeds.seed_service_parameters <servicio> --yes
  ```

- El backend devuelve **datos y códigos**, nunca textos para el usuario. Los
  portales traducen cada código.

---

## Portales

Sitios estáticos en HTML, CSS y JavaScript sin dependencias ni compilación,
publicados en S3 + CloudFront.

| Carpeta | Dirección | Qué es |
|---|---|---|
| `portal/page` | `bearsoft.com.bo` | Página de la empresa. |
| `portal/demo` | `smartdecisions.bearsoft.com.bo` | Aplicación de SmartDecisions (exige inicio de sesión). |
| `portal/billing` | `smartbilling.bearsoft.com.bo` | Aplicación de SmartBilling. |
| `portal/raforios` | — | Sitio personal de Rafael Ríos Bascón. |

El portal de SmartDecisions se publica con:

```bash
python3 -m tools.deploy.deploy_demo_portal          # muestra qué cambiaría
python3 -m tools.deploy.deploy_demo_portal --yes    # sube e invalida CloudFront
```

---

## Infraestructura

- **Gateway único:** el API HTTP `bearsoft-gateway` recibe todo lo que llega a
  `api.bearsoft.com.bo` y envía cada `/v1/<prefijo>` al Lambda de su
  servicio. Los servicios propios no tienen un API por servicio, salvo EVENTS,
  que conserva el suyo porque lo usa el entorno de desarrollo de Binaria.
- **Despliegue de un servicio:** `services/ci/api/build_and_deploy.sh`, con la
  configuración del `deploy.config` de cada servicio. Los scripts del dominio
  y de las tablas están en `services/ci/api/`; su
  [README](services/ci/api/README.md) explica el orden.
- **Tablas:** `services/ci/api/create_dynamodb_tables.sh`.

---

## Pruebas y calidad

Antes de entregar un cambio en un servicio:

```bash
python tools/verification/verify_service.py services/<servicio>   # o --all
```

Corre los tests, Pylint (10.00), el formato de las firmas, los type hints, el
tamaño de los archivos (menos de 800 líneas), los duplicados y las reglas de
configuración y de EVENTS.

Las dependencias de prueba (`pytest`, `pylint`, `moto`) están en
`services/requirements-dev.txt`. Nunca entran en un Lambda: el
`requirements.txt` de cada servicio lista sólo lo que importa.

**GitHub Actions** (`.github/workflows/python-package.yml`) corre Pylint y los
tests de AUTH, EVENTS, FILES, ML_FUNCTIONS y AI sin `.env`.

---

## Herramientas

`tools/` guarda sólo lo que se usa más de una vez: verificación, despliegue
del portal, plantillas que el cliente llena, siembra de datos base, datos de
demostración, conversión de documentos e informes de visitas. El detalle está
en [`tools/README.md`](tools/README.md).

---

## Servicios de clientes

Viven en el repositorio por conveniencia, pero **no son parte de SmartDecisions
ni de SmartBilling**. Cada uno tiene su propio README.

| Carpeta | Cliente | Qué es |
|---|---|---|
| `services/trade`, `services/forms`, `services/localization` | Binaria | Trade marketing, formularios y geolocalización, sobre MySQL. Apuntan a su propio gateway. |
| `services/cms` | Ministerio de Minería | Contenido del sitio institucional. |
| `services/mining_summit` | Ministerio de Minería | Registro y asistencia de la Cumbre Minera; su frontend está en `demo/cumbre-minera`. |
| `demo/` | Ministerio de Minería | Sitio institucional y tableros en Streamlit. |
| `notebooks/` | — | Cuadernos de exploración. |

---

## Autor

**Rafael Ríos Bascón** — BearSoft
[raforios@gmail.com](mailto:raforios@gmail.com)
