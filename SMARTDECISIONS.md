# SMARTDECISIONS

> **Documento único del producto:** qué es, cómo está construido, qué está
> **terminado**, cuál es el **estado actual** y qué queda **pendiente**. Se lee
> primero al abrir una sesión. No es un diario: lo que ya vive en el código va
> como puntero.
>
> Lo que no vive aquí: las reglas técnicas en `CLAUDE.md` y `.claude/rules/`;
> los procedimientos en `.claude/skills/`; cómo presentarlo (guion, pantallas,
> preguntas) en `GUIA_SMARTDECISIONS.md`, guía interna; el contrato de
> columnas en el código que lo valida.
>
> **Última actualización: 2026-10-05**

---

## Regla de oro

`CLAUDE.md` manda sobre cualquier patrón que se encuentre en el código. **Si el
código existente la contradice, se avisa — no se propaga.** Todo el código de
AI, ANALYTICS, INGEST, MINING_ANALYSIS, OPTIMIZATION, QUOTES y BILLING lo
escribió Claude: no hay "código heredado" que sirva de excusa.

---

## 1. El producto

**En una frase:** SaaS de BearSoft que convierte **los archivos que la empresa
ya tiene** —ventas, cobros, stock, visitas, objetivos— en decisiones
comerciales: qué ofrecer a cada cliente, cuánto se va a vender, a quién estás
por perder, cuánto ganas de verdad, cuánto te deben y en qué orden recorrer la
ruta. **Sin ERP nuevo, sin instalación y sin proyecto de integración.**

**Concepto diferenciador:** `Afinidad × Drop Size = Oportunidad Comercial Real`.

**Mercado:** gerencias comerciales de distribuidoras y consumo masivo en
Bolivia. Segundo vertical: mineras y comercializadoras (cotizaciones), hoy con
poca prioridad comercial (Rafael, 04-oct).

**Marca:** empresa **BearSoft**, productos **SmartDecisions** y
**SmartBilling** (servicio BILLING).

### Los archivos de origen y para qué sirven

Definido por Rafael el 01-oct y el 04-oct. **Se tiene presente en cada cambio.**

| Archivo | Qué es |
|---|---|
| `data/DetalleVentas.xlsx` | Datos de ejemplo cedidos. Base de **Comercial Illimani** vía `tools/build_sample_dataset.py` |
| `base 2025.xlsx` | Datos de otra empresa. Base de **Distribuidora Andina** vía `tools/convert_sales_export.py` |
| `PRE- CIERRE…` y `LPZ CIERRE…` | **Modelos** de indicadores y tableros de una tercera empresa (Cumplimiento salió de ahí). No son requisitos |
| Las plantillas | La definición de BearSoft de lo mínimo que el producto necesita |

**Las dos empresas de prueba son inventadas y deben estar completas.** No hay
clientes reales en producción: lo desplegado es la demo. Si a un dataset de
prueba le falta un dato, **se fabrica** de forma verosímil y se carga; no se
diseña el producto alrededor del hueco. Ninguna regla, nombre ni cifra de esos
archivos entra al código como si fuera del producto.

### Módulos

| Módulo | Pregunta |
|---|---|
| Resumen Comercial | ¿Cómo vamos, de quién dependemos, cuánto ganamos? |
| Fuente de volumen | ¿De qué productos y clientes sale la venta? |
| Oportunidades | ¿Qué le ofrezco a cada cliente y cuánto vale? |
| Pronóstico | ¿Cuánto voy a vender? |
| Segmentación / Salud de Cartera | ¿Quiénes valen más y a quién estoy por perder? |
| Cuentas por cobrar | ¿Cuánto me deben, qué tan vencido, cuánto recupero? |
| Cumplimiento de objetivos | ¿Cumplió cada cliente, en lo facturado y en lo cobrado? |
| Stock del día | ¿Cuánto me dura, qué quiebra, cuánto capital quieto? |
| Rutas | ¿En qué orden visito, dónde está cada vendedor, se cumplió el plan? |
| Cotizaciones | Tipo de cambio, minerales y factores que se mueven |
| Interpretación (IA) | ¿Qué significa esto? — sobre cualquiera de las anteriores |

---

## 2. Descripción técnica

Microservicios Python (FastAPI + Mangum sobre Lambda), cinco capas, DynamoDB.
Frontends Vanilla JS sin build sobre S3 + CloudFront: `portal/demo/`
(SmartDecisions) y `portal/billing/` (SmartBilling). **Una sola entrada de API:
`api.bearsoft.com.bo/v1/<servicio>/…`** (ver §6, Infraestructura).

| Grupo | Servicios |
|---|---|
| **Base** (obligatorios para todo producto) | AUTH (JWT con `client` y rol), EVENTS (auditoría y uso), FILES (S3) |
| **SmartDecisions** | INGEST, ANALYTICS, OPTIMIZATION, QUOTES, AI, MINING_ANALYSIS |
| **SmartBilling** | BILLING |
| **Capacitación** | ML_FUNCTIONS |

**FORMS, LOCALIZATION, TRADE, CMS y MINING_SUMMIT no se tocan** sin pedido
explícito: son de clientes.

**Límites que condicionan el diseño:** Lambda 250 MB sin comprimir (sin
scikit-learn, osmnx, Prophet ni mlxtend); API Gateway 29 s y 10 MB (los
archivos suben a S3 por FILES); DynamoDB 400 KB por ítem; OSRM público con
límite de tasa.

**Contrato de datos:** la fuente de verdad es el código —`SALES_COLUMNS`,
`COLLECTION_COLUMNS`, `STOCK_COLUMNS`, `VISIT_COLUMNS` y objetivos en
`services/ingest/schemas/`—, de donde se derivan el validador, el mapeador de
cabeceras y las **cinco plantillas** (`tools/build_sales_template.py`). Ventas
crea el dataset; los otros cuatro se enganchan a él. Todo entra por **tres
puertas** con el mismo validador: archivo, API JSON del ERP y `from-s3`.

**Datos de prueba:**

| Empresa (`client` del JWT) | Ingresa | Dataset | Contenido |
|---|---|---|---|
| Comercial Illimani S.R.L. | `gerente@raforios.com` | `8c9b15fa…` | 22.008 ventas, 24 meses, cobros, stock, visitas (923), objetivos (6.384) |
| Distribuidora Andina S.R.L. | `gerente@bearsoft.com.bo` | `6c20be37…` | 5.079 ventas, 7 meses, cobros (603), stock (256), visitas (411), objetivos (1.925) |

Usuarios y roles por empresa: memoria `reference_test_companies_users`.
Completar un archivo de ventas con los otros cuatro:
`python -m tools.complete_demo_dataset ventas.xlsx --out-dir …`; cargarlo:
`tools/load_second_owner.py`.

**Cómo verificar:** `/verificar-servicio <nombre>` (tests, Pylint 10.00,
firmas, type hints, hardcode, tamaño, idioma de comentarios, EVENTS, S3
directo, duplicados entre servicios, cobertura de endpoints).

---

## 3. Finalizado

| Pieza | Fecha | Dónde mirar |
|---|---|---|
| Los nueve análisis comerciales, Cartera y Cuentas por cobrar | 17-sep | `services/analytics/` |
| Rutas: plan → visita → venta → cierre, geocercas, stock transaccional; pantalla del vendedor | 21/22-sep | `services/optimization/`, `portal/demo/routes/` |
| Usuarios por empresa y roles (`client` en el JWT; MANAGER, SELLER, REQUESTER) | 21/30-sep | `security.py` de cada servicio |
| EVENTS en todos los servicios (auditoría y uso); lectura sólo ADMIN y escritura con token reenviado | 23-sep / 03-oct | `CLAUDE.md` §7, `_caller_authorization` en `utils.py` |
| Maestro de clientes en INGEST, tres puertas, nunca sobrescribe | 27-sep | `services/ingest/services/clients.py` |
| Dos canales de carga para todos los contratos, modo APPEND idempotente | 28-sep | `prepare_rows` / `validate_rows` en INGEST |
| Un archivo por contrato (cinco plantillas) | 28-sep | `tools/build_sales_template.py` |
| INGEST pasa por FILES; patrón FILES para DynamoDB | 28-sep | `services/ingest/services/utils.py` |
| Rutas: Histórico y Planes separados por fecha, repetir ruta, alta de cliente en la calle, Optimizar con dos mapas | 28-sep | `localization.py`, `localization_sources.py` |
| Factores fechados y lectura en dólares a la cotización de cada día | 29-sep | QUOTES `factors`, `exchange-rates/at`; `_scoped_dataframe` en ANALYTICS |
| Cumplimiento de objetivos (reproduce el libro modelo a 4 decimales) | 29-sep | `services/analytics/services/objectives.py` |
| Maestro de vendedores y un plan por vendedor | 01-oct | `ingest_sellers`, `POST /plan/{id}/by-seller` |
| Oportunidades de 118 s a 14 s | 01-oct | `opportunities` en ANALYTICS |
| Aislamiento por dueño también en ANALYTICS y OPTIMIZATION | 03-oct | `get_dataset_metadata` |
| Dominio único `api.bearsoft.com.bo`, `/health`, `/docs` por servicio, CI ordenado | 03-oct | `ci/api/README.md` |
| Prueba completa del vendedor en producción | 03-oct | plan `PRUEBA-BEARSOFT-2026-10-03` |
| **Las dos empresas de prueba completas** (costo, cobros, stock, visitas, objetivos) | 04/05-oct | `tools/complete_demo_dataset.py` |
| Guía interna única para presentar, con las dos empresas | 05-oct | `GUIA_SMARTDECISIONS.md` |
| Tablas y datos documentados por servicio (sección «Datos que guarda») | 05-oct | `README.md` de cada servicio |
| **SmartBilling** (BILLING): mostrador, ventas, catálogo con lotes, recepción, tablero, configuración; FEFO; impresión térmica | 23-sep | `services/billing/`, `portal/billing/` |
| SIAT sin trámite: CUF, módulo 11, XML validado contra el XSD, nominatividad, enmascarado de tarjeta, simulación | 29/30-sep | `billing_siat.py`, `billing_invoice_xml.py`, `tools/billing/dry_run_invoice.py` |
| SIAT piloto: WSDL dentro del servicio y **comunicación exitosa** con el token | 04-oct | `services/billing/wsdl/LEEME.md` |

---

## 4. Estado actual

**Desplegado:** los once servicios desde el 03-oct (comprobar con
`aws lambda list-functions --profile deploy_ml`). Frontends al día.

**Esperando el despliegue de backend (Rafael):**

- **ANALYTICS** — un costo en cero ya no cuenta como costo (Rentabilidad
  mostraba 100 % de margen); y en Cumplimiento una venta **al contado** cuenta
  como cobrada (antes inflaba la deuda con todo el contado). Sin este
  despliegue, el Cumplimiento de Andina muestra la deuda inflada.
- **INGEST** — `IngestDataset` declara todo lo que el ítem guarda, con un test
  que falla si vuelve a quedar atrás.
- **AUTH** — dos altas simultáneas del mismo correo respondían 500 en vez de
  «Email already registered» (`create_user_item`).
- **BILLING** — el token del SIAT va como `TokenApi <token>` (sin eso el SIAT
  responde «API KEY NO VALIDO») y los WSDL en `services/billing/wsdl/`, que
  viajan en el ZIP. Comprobar si ya salió con los commits del 05-oct.

**Revisión del 04/05-oct en el portal**, con las dos empresas: los nueve
análisis, las ocho secciones de Rutas y Cotizaciones abren sin errores de JS.
El Cumplimiento de Illimani (24 meses) tarda mucho en llegar con conexión
lenta: el servicio responde en 1,1 s; lo que pesa es la respuesta.

**SmartBilling:** corregido el error «Cannot read properties of null» de
RECEPCIÓN y TABLERO (una sección que terminaba de cargar después de cambiar
de sección pintaba su error encima de la nueva; `portal/billing/js/app.js`).
Ronda nueva de funcionalidades definida el 04-oct (ver §5).

---

## 5. Pendiente

En orden.

1. **Desplegar ANALYTICS, BILLING, INGEST y AUTH** (Rafael; ver §4).
2. **SmartBilling, ronda del 04-oct**, por cambios con `intent.md`, `spec.md`
   y `plan.md` en `docs/cambios/` (plantilla en `docs/cambios/_plantilla/`):
   - `billing-proveedores-pedidos`: catálogo de proveedores, producto con
     varios proveedores (código y costos con historia), pedidos con recepción
     parcial; la recepción sin pedido se permite.
   - `billing-caja`: apertura y cierre por usuario con fecha y hora, arqueo
     por medio de pago (efectivo, QR, débito, crédito), EGRESOS de la caja
     abierta, roles MANAGER/SELLER. `intent.md` ya escrito y respondido.
   - `billing-sucursales`: inventario por sucursal y traspasos — simple, dos
     sucursales que se pasan mercadería.
3. **SIAT:** pedir CUIS y CUFD reales en el piloto; agregar el WSDL de
   `FacturacionOperaciones` cuando se haga contingencia y el de
   `ServicioFacturacionDocumentoAjuste` para notas de crédito y débito.
4. **Cobertura de endpoints:** OPTIMIZATION 32, BILLING 16, MINING_ANALYSIS 10
   y AI 1 sin prueba (`endpoint-coverage` sale como TODO).
5. **Maestro de productos**, con la misma regla que clientes y vendedores.
6. **Sección "Usuarios"** para que un MANAGER administre a su gente, y panel
   del ADMIN (usuarios, roles de IA, uso por cuenta). Cuando el sistema esté
   listo para pruebas, no antes (01-oct).
7. **Sugerencias sin decidir:** Cumplimiento podría mandar el detalle por
   cliente sólo al abrirlo (la respuesta de 24 meses es pesada); reemplazar
   OSRM público antes de tener clientes pagando.
8. **Postergado:** oro y plata en la cotización anticipada (la LBMA bloquea la
   lectura automática desde el 30-sep; cotizaciones tiene baja prioridad);
   alinear los modelos de AI a `TypedDict`; alinear
   `mining_analysis/services/utils.py` al boilerplate; corregir
   `portal/billing/README.md`, que todavía dice `supplies`.

**Lo que falta para vender, no para demostrar:** control de suscripción,
retención de datos y persistencia de lo que produce la capa de IA.

---

## 6. Decisiones vigentes

### Negocio

- **Las empresas de prueba son el escenario ideal**, completas; los datos que
  falten se fabrican (04-oct).
- **Degradación elegante, no ceros.** Sin un dato opcional, la sección se
  declara no disponible y la UI la oculta. **Un costo en cero es un costo no
  informado.**
- **Aceptación parcial:** las filas inválidas se apartan con su motivo y el
  resto entra. Coordenada 0 = sin dato.
- **Catálogos maestros (clientes, vendedores; productos después).** Las
  plantillas no cambian; los campos de la transacción se validan completos y
  los de un catálogo sólo se comprueba que existan, y si no, se dan de alta.
- **Un objetivo se mide dos veces**, contra lo facturado y contra lo cobrado.
  El cobro cuenta en el mes de la factura que salda —única lectura bajo la cual
  `facturado = cobrado + deuda`— y **una venta al contado está cobrada al
  momento**. Los cortes del semáforo y el valor del punto van en la política
  comercial por propietario; el producto no declara nombres de cluster.
- **SmartDecisions no reserva stock del ERP:** reporta
  `disponible = existencia − comprometido`.
- **La cotización oficial de una quincena es el promedio de la anterior**; el
  BCB publica el viernes una cotización que rige hasta el lunes; el tipo de
  cambio flota desde el 27-jun-2026 (antes, régimen fijo).
- **El Ministerio de Minería recibe el boletín en PDF y PNG** a cambio de los
  datos de cotizaciones.
- **Un factor es una cifra y si cuenta o no**, con historia fechada; un cálculo
  usa el estado de **su propia fecha**. Un monto en dólares se convierte a la
  cotización de su propio día.

### Técnicas

- **El backend devuelve datos y códigos, nunca texto de cara al usuario.**
- **Nada configurable vive en el código**; las variables son requeridas.
- **INGEST es la única puerta de entrada de datos y el único dueño de los
  maestros.** Quien necesite un cliente lo pide a INGEST por HTTP.
- **El dueño es parte de la consulta**: el `client` del token (o el email si
  no lo tiene). En OPTIMIZATION también es clave de partición. Un recurso
  ajeno responde igual que uno inexistente.
- **Un archivo se identifica por su contenido.** Misma huella y mismo dueño =
  el mismo dataset.
- **La cuenta por cobrar vive al nivel de factura**; cobro sin venta es
  incidencia con código.
- **Pronóstico: suavizado exponencial con tendencia amortiguada**, ajustado por
  backtest, publicando su error y el del modelo ingenuo.
- **La capa de IA recibe la respuesta del backend tal cual**; los roles viven
  versionados en DynamoDB.
- **Sin versiones fijadas en `requirements.txt`**; el Lambda no tiene pyarrow
  (comparar `Enum` por `.value`).
- **Los timestamps de un dispositivo se normalizan a `TARGET_TIMEZONE`** antes
  de decidir el día.
- **No se crean carpetas nuevas dentro de un microservicio** sin pedido.
  Excepciones autorizadas: `scripts/` en MINING_ANALYSIS y `wsdl/` en BILLING
  (04-oct: tiene que viajar en el ZIP).
- **Los WSDL del SIAT se leen de disco**, nunca se bajan en el arranque.
- **Los tests de los servicios base no importan módulos que validen entorno**
  (GitHub Actions corre sin `.env`).

### Infraestructura

- **Sin RDS por presupuesto.** Todo servicio nuevo: DynamoDB + Lambda + S3.
- **Un solo EVENTS para pruebas y producción** hasta pasar de 10 clientes
  reales (03-oct).
- **Un dominio para toda la API**, `bearsoft-gateway` (HTTP API, formato 2.0),
  una ruta `ANY /v1/<prefijo>/{proxy+}` por servicio. Costo adicional USD 0.
- **Despliegue ordenado con `ci/api/start.sh`**: tablas → base → INGEST y
  QUOTES → ANALYTICS, OPTIMIZATION, MINING_ANALYSIS, AI → BILLING → tareas →
  dominio. El CORS de cada API vive en su `deploy.config`.
- **Las tablas se crean con `create_dynamodb_tables.sh`.**
- **El `.env` viaja entero a las variables del Lambda: ningún valor lleva coma
  ni llave.**
- **Los deploys de backend los hace Rafael; los de frontend, Claude.**
- **Frontends:** SmartDecisions con `python3 -m tools.deploy_demo_portal --yes`;
  SmartBilling en `bearsoft-smartbilling-portal` + CloudFront `EWVWU4A03ZZ4Z`
  (`aws s3 sync portal/billing/ … --delete --exclude README.md` e
  invalidación).
- **Gotchas:** con red lenta `aws s3 cp` puede devolver 0 sin subir (comprobar
  `CodeSize`); el CORS de un API ya creado no se actualiza desde el script;
  `GET /v1/ingest/history` no existe (el listado es `/v1/ingest/datasets`).
