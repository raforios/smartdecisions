# SmartDecisions

## Definicón

> Es un sistema de Inteligencia de Negocios orientado a empresas desde pequeñas hasta grandes; pensando en que muchas de estas tienen sistemas ERP que les permiten el control de todos sus procesos y otras empreas que tengan los registros de su información en archivos y planillas Excel. 

> Las empresas pueden tener mucha información registrada en sus archivos o sistemas ERP o apenas lo necesario para que puedan sobrevivir y controlar sus compras, ventas, inventarios y clientes, lo más básico cuando son empresas comerciales.

> Estas son las consideraciones base para presentar un sistema de inteligencia de negocios que sea útil que en simples pasos les parmita ver su salud financiera, clientes, inventarios, ventas, distribución, todos los elementos que juegan en la parte comercial y decisional

---

## Consumo de información

El `SmartDecisions` tiene como base de consumo de información, más no es limitativa pudiendo ser ampliada en caso de que sea necesario los siguientes datos:

1. **INVENTARIO - STOCK:** Se puede integrar vía API con el ERP o cargar mediante un archivo, el propósito es tener en vivo el inventrio actualizado a "hoy" (valorado, en bolivianos y dólares al tipo de cambio oficial y en USDT). Por otro lado; si se tiene habilitado el módulo de ventas ver en vivo como se va moviendo ese inventario de manera "real" independiente del ERP o de los registros de ventas que tiene el cliente.

2. **VENTAS:** Se puede integrar vía API con el ERP o cargar mediante un archivo, ver las ventas organizadas por periodos, mensuales, anuales o las diarias actualizadas al último día que se tiene información. Podríamos tener en combinación con las **RUTAS** y el **INVENTARIO** un estimado en "vivo" de lo que hoy se está vendiendo. También aplican los tipos de cambios oficial y USDT.

3. **COMPRAS:** Se puede integrar vía API con el ERP o cargar mediante un archivo, el propósito es tener las compras y/o importaciones que se hicieron para que nuestro **INVENTARIO** esté actualizado, ver cuánto nos costó esa última compra respecto a las anteriores, diferencias y márgenes todo lo que comercialmente es importante para un analista comercial y financiero. También aplican los tipos de cambios oficial y USDT.

4. **CUENTAS POR COBRAR:** Se puede integrar vía API con el ERP o cargar mediante un archivo, el propósito es tener los cobros registrados para todos los clientes que tienen deudas con nosotros y el flujo y segumiento que tengamos de cada uno de esos clientes y sus cuentas. También aplican los tipos de cambios oficial y USDT.

5. **RUTAS:** Se puede integrar vía API con el ERP o cargar mediante un archivo. Las rutas que están definidas para los vendedores que son los que consumen el **INVENTARIO** y realizan **VENTAS** que ya mencióne en el punto 2. Estas rutas deben tener planificaciones cargadas previamente, también se pueden crear planificaciones y luego asignarlas a los vendedores y distribuidores. Pueden existir rutas "sobre la marcha" que se van creando en vivo y se deben registrar los datos que se van adquiriendo del cliente, la venta además de la ubicación. También es importante las distancias para los factores externos como combustibles y otros que podríamos requerir que y estén relacionados con esa parte.

6. **PARÁMETROS:** Clientes, ubicaciones, configuraciones todos los datos que necesitemos en el `SmartDecisions` para que funcione correcatmente deberían de poder ser ingresados mediante formularios que nos permitan configurar y cargar los datos que faltan y que no vienen del API de integración con el ERP o los archivos, acá también serían otros factores que podrían ser requeridos para ver margenes y todo lo que es decisional

---

## Salida de la inforamción

El `SmartDecisions` a partir de la información consumida debe generar lo siguiente:

1. **REPORTES:** La mayoría o todos ya los tenemos ahora, sólo que no están en los lugares correctos divididos acorde su área, de manera que sean intuitivos para buscar porque no están modularizados y la estructura que tenemos es desorganizada

2. **KPI'S:** La mayoría de estos ya los tenemos ahora, sólo que no están en los lugares correectos que sean intuitivos para buscar porque no están modularizados y la estructura que tenemos es desorganizada

3. **MAPAS:** Ya los tenemos y las funcionalidades como optimización, comparación, en vivo, histórico y todas herramientas que sean necesarias para que esos mapas sean útiles

4. **INTEGRACIÓN CON IA:** Cada reporte, KPI o segmeento que necesite una explicación debería estar integrado con IA los prompts deberían ser parametrizables deberíamos tener un CRUD de prompts para irlos modificando de manera que se puedan ir ajustando, esto en la para te **PARÁMETROS**

---

## Regla de oro

`CLAUDE.md` manda sobre cualquier patrón que se encuentre en el código. **Si el
código existente la contradice, se avisa — no se propaga.** Todo el código de
AI, ANALYTICS, INGEST, MINING_ANALYSIS, OPTIMIZATION, QUOTES y BILLING lo
escribió Claude: no hay "código heredado" que sirva de excusa.

**RESPETA ESTE ARCHIVO ANTE TODO DEJA DE INFERIR**

---

## Descripción técnica

Microservicios Python (FastAPI + Mangum sobre Lambda), cinco capas, DynamoDB.
Frontends Vanilla JS sin build sobre S3 + CloudFront: `portal/demo/`
(SmartDecisions) y `portal/billing/` (SmartBilling). **Una sola entrada de API:
`api.bearsoft.com.bo/v1/<servicio>/…`**, y en el código una sola variable,
`API_URL` (ver Infraestructura).

| Grupo | Servicios |
|---|---|
| **Base** (todo producto los usa) | AUTH (JWT con `client` y rol), EVENTS (auditoría y uso), FILES (S3), ML_FUNCTIONS (cálculos: pronósticos, proyecciones, clasificaciones, rutas; no guarda nada), y AI (explicaciones con Bedrock) |
| **SmartDecisions** | COMMERCIAL (cargas, análisis y rutas; une INGEST, ANALYTICS y OPTIMIZATION desde el 23-oct), FINANCE (Análisis Financiero) y MINING_ANALYSIS (cotizaciones de minerales y «vender hoy o esperar») |
| **Independiente** | QUOTES (tipo de cambio y factores externos): ni base ni de un solo producto; lo usan SmartDecisions y SmartBilling (Rafael, 26-oct) |
| **SmartBilling** | BILLING |

**FORMS, LOCALIZATION, TRADE, CMS y MINING_SUMMIT no se tocan**: son de
clientes y quedan fuera de toda revisión.

**Límites que condicionan el diseño:** Lambda 250 MB sin comprimir (sin
scikit-learn, osmnx, Prophet ni mlxtend); API Gateway 29 s y 10 MB (los
archivos suben a S3 por FILES); DynamoDB 400 KB por ítem; OSRM público con
límite de tasa.

---
### Datos Técnicos adicionales

- **El backend devuelve datos y códigos, nunca texto de cara al usuario.** El
  portal traduce cada código (también los de AI) en su catálogo.
- **El `.env` es configuración** (entorno, Lambda, tablas, URLs, timeouts),
  nunca valores de cálculo. **Cada servicio guarda sus parámetros en sus
  tablas:** `<servicio>_parameters` (iguales para todas las empresas, bloque
  SERVICE PARAMETERS de `utils.py`, definidos en `docs/parametros.md`) y la
  tabla de cada empresa. Ningún servicio depende de otro para arrancar
  (Rafael, 24-oct-2026).
- **Un cálculo común vive una sola vez, en ML_FUNCTIONS**: las proyecciones de
  FINANCE, COMMERCIAL, QUOTES y MINING_ANALYSIS, la segmentación, la afinidad
  (Apriori) y el algoritmo de rutas de COMMERCIAL.
- **Los seis servicios con el boilerplate común** (COMMERCIAL, MINING_ANALYSIS,
  BILLING, FINANCE, QUOTES y AI) tienen las mismas funciones en `utils.py`;
  los bloques estándar van al final.
- **El uso y la auditoría se envían a EVENTS antes de responder** (se esperan,
  no se dejan en segundo plano): el Lambda se congela al contestar. AUTH, FILES
  y ML_FUNCTIONS no reportan.
- **COMMERCIAL es la única puerta de entrada de datos comerciales y el dueño de
  los maestros** de clientes y vendedores.
- **La capa de IA recibe la respuesta del backend tal cual.** Una pantalla
  existe para AI si tiene un texto activo en `ai_prompts` (rol, contexto,
  misión y reglas, versionados); se editan en Parámetros › Prompts de la IA,
  sin desplegar. Modelo: Claude Haiku 4.5 (`us.` en Bedrock).
- **AUTH:** el alta de usuarios es sólo para `ADMIN`; contraseñas con `bcrypt`
  directo, compatible con los hashes viejos de passlib.
- **Sin versiones fijadas en `requirements.txt`**; el Lambda no tiene pyarrow
  (comparar `Enum` por `.value`).
- **Los timestamps de un dispositivo se normalizan a `TARGET_TIMEZONE`** antes
  de decidir el día.
- **No se crean carpetas nuevas dentro de un microservicio** sin pedido.
  Excepciones autorizadas: `wsdl/` en BILLING (04-oct: tiene que viajar en el
  ZIP) y `scripts/` en MINING_ANALYSIS, que se retira cuando la carga
  quincenal corra con `tools/etl_minerals/`.
- **La carga quincenal de minerales es independiente del API**
  (`tools/etl_minerals/`, 19-oct): su propio `.env` y dependencias; carga el
  Excel en el MySQL local y lo publica en DynamoDB. El catálogo de minerales es
  la tabla `t_minerals`, no una lista en el código.
- **Los WSDL del SIAT se leen de disco**, nunca se bajan en el arranque.
- **CI de GitHub:** pylint 10.0 sin `--rcfile` y pytest sin `.env` sobre AUTH,
  EVENTS, FILES, ML_FUNCTIONS y AI; sus tests puros no importan módulos que
  validen entorno.
- **Tipos con sintaxis moderna** (`list[str]`, `str | None`), en todo el código
  propio, boilerplate incluido. Lo vigila el chequeo `modern-typing`;
  `pyupgrade` vive sólo en `SmartBear/.venv`. Archivos de hasta 800 líneas.
- **`tools/` cumple las mismas reglas que los servicios** (Pylint 10.00 por
  herramienta, firmas, tipos, idioma); `verify_service.py --all` la revisa.
  Qué hay en cada carpeta de `tools/` y para qué sirve: `tools/README.md`.

---

### Infraestructura

- **Sin RDS por presupuesto.** Todo servicio nuevo: DynamoDB + Lambda + S3.
- **Un solo EVENTS para pruebas y producción** hasta pasar de 10 clientes
  reales.
- **Un dominio para toda la API**, `bearsoft-gateway` (HTTP API, formato 2.0),
  una ruta `ANY /v1/<prefijo>/{proxy+}` por servicio. Costo adicional USD 0.
  Todos los servicios propios y el portal llaman `{API_URL}/v1/<servicio>/…`
  (desde el 21-oct-2026; ninguno conserva una `*_SERVICE_URL`).
- **Despliegue ordenado con `services/ci/api/start.sh`**: tablas → AUTH, EVENTS,
  FILES, ML_FUNCTIONS, AI → QUOTES → COMMERCIAL, MINING_ANALYSIS, FINANCE →
  BILLING → tareas → dominio. El CORS de cada API vive en su `deploy.config`.
- **Las tablas se crean con `create_dynamodb_tables.sh`.**
- **El `.env` viaja entero a las variables del Lambda: ningún valor lleva coma
  ni llave.** El `.dockerignore` de cada servicio excluye `.env` del paquete.
- **Los deploys de backend los hace Rafael; los de frontend, Claude.**
- **Frontends:** SmartDecisions con `python3 -m tools.deploy.deploy_demo_portal --yes`;
  SmartBilling en `bearsoft-smartbilling-portal` + CloudFront `EWVWU4A03ZZ4Z`
  (`aws s3 sync portal/billing/ … --delete --exclude README.md --cache-control no-cache` e
  invalidación).
- **Gotchas:** con red lenta `aws s3 cp` puede devolver 0 sin subir (comprobar
  `CodeSize`); el CORS de un API ya creado no se actualiza desde el script;
  el listado de cargas es `/v1/commercial/datasets`; la salud de ML_FUNCTIONS está en `/v1/common/health`.
---

## Reglas de negocio "a mano alzada" (pueden ajustarse y mejorarse)

1. Comienza con una planificación de las ventas un FORECAST, esa planificación nos lleva a hacer un pedido a nuestros proveedores, ese pedido puede ser vigente para un mes o un trismestre eso dependerá de cada empresa. Ese pedido y el costo de tenerlo en mis almacenes se calculó al tipo de cambio del día que estoy haciendo el pedido que estoy pagando por esos productos.

2. Cuando llegan a mis almacenes ya tienen un costo unitario donde les han sumado todo lo que implica desde pedir hasta traer (transporte, fletes, aduana, etc) ese precio por cada producto es el que me da el costo unitario. A ese costo unitario yo le añado los demás valores que cada empresa debe tener entre los más comunes impuestos, utilidad o margen e incluso el costo de dejarlos en las tiendas y los clientes que consumen esos productos.

3. Ese precio el día que se lo fija, tiene un valor en dólares a ese mismo día de ahí en más y durante la vigencia de todos los lotes de mi pedido o del precio, el costo del producto debería ser el mismo, muchas veces los van ajustando para no perder, pero cada venta que hago tiene un valor al día de la venta.

4. Los créditos que doy y todo eso se calcula al día que estoy dando el crédito o estoy vendiendo, eso ya es historia, lo que pasó desde que pedí los productos, hasta que los vendí ya sea al contado a crédito, no va a cambiar porque se hizo en un momento donde el tipo de cambio vigente era XX 

5. Asumo y si no es así es una regla que nosotros como SmartDecisions podemos implementar, es que cada agrupamiento sea mensual, el diario no sirve para esta parte, sería más para el SamrtBilling (NO significa que no debemos recibir los datos diarios), el agrupamiento por ventas debería ser mensual y entonces sabemos cuánto vendimos en el mes en cuestión al tipo de cambio de ese último día del mes y cuál es la diferencia con hoy que consulto, nuestras importanciones e inventarios sabemos cuanto tenemos hoy al tipo de cambio de hoy y eso es lo que tenemos lo que ya fue no va a cambiar, podemos ver respecto del día que se asignó el precio al inventario a hoy cómo cambio, para ver si quizá debmos hacer un ajuste de precios para no perder porque el costo de pedir XX cantidad de productos a YY precio hace un mes puede incidir en la cantidad del pedido de este mes y en el precio a futuro

6. Por eso te pedí que reorganicemos la estrucutra incluso de la navegación porque por un lado van nuestras ventas que son diarias pero el SmartDecisions debería evaluar por mes y sólo si alguien pide evaluar el detalle de un mes específico ingresar a ese mes, pero eso sigue siendo una fotografía nada se puede hacer ya porque eso trasncurrió así la unica comparación es saber cuánto en dolares vendí al útimo día del mes que analizamos versus hoy, esa diferencia nos puede dar un dato importante

7. La parte de compras es casi similar compramos a un precio hace uno o tres o seis meses para tener mucho stock, pero nuestro precio fue uno ese moemnto y ahora podría ser otro y debería darnos la información de esa diferencia porque sí podemos ajustar nuestros precios sabiendo el pasado y viendo como afecta el presente para que las futuras ventas que hagamos no jueguen en nuestra contra.

8. Lo que se vendío a crédito que son nuestras cuentas por cobrar no varían con el tipo de cambio ya te repetí varias veces que si dimos mil de credito cobramos los mil, acá no tiene nada que ver el tipo de cambio porque nuestras ventas son en bolivianos, para eso vemos todos los otros factores explicados antes para que el precio en bolivianos no juegue en nuestra contra, acá el tipo de cambio sólo nos sirve para ver la devaluación de lo que dimos de crédito versus lo que terminamos cobrando, para tomar decisiones sobre los plazos de los créditos o cosas así que cada empresa definirá

9. Si revisamos un mes en particular debe verse el cálculo a ese mes y como es a hoy, pero los reportes iniciales que son la suma de todo es a hoy, porque ese hoy es el que nos dice qué tenemos y qué está pasando y el pasado nos dice qué debemos corregir en el presente. Así que todas las vistas de los dashboards son a hoy pero si veo algo en particular es a ese momento, por eso te decía que los cálculos son en bolivianos y solo transformamos a dólares o USDT de la fecha cuando el reporte lo amerita y para un general es usando el valor vigente actual, para un mes específico los valores vigentes ese mes comaprados con hoy.

En síntesis lo que es para hoy a futuro es con el cambio de hoy, las vistas iniciales el estado actual es a hoy, los cáculos y sumas es en Bolivianos y luego se transforma con el tipo de cambio de hoy, si hay un requerimiento especifico de un periodo de tiempo se usa el tipo de cambio de ese periodo y se muestra al final la relación con hoy, lo pasado es como estaba no se actualiza no cambia, sólo se compara con hoy

---

## Último estado

> Lo escribe Claude cada vez que se detiene esperando algo. Sólo hechos
> comprobados; el detalle vive en `docs/cambios/smartdecisions/plan.md`.

**30-oct-2026.**

- **Desplegado (comprobado en AWS el 30-oct):** COMMERCIAL, QUOTES y AI
  (26-oct), FINANCE y MINING_ANALYSIS (26-oct), ML_FUNCTIONS (25-oct). El
  servicio genérico de parámetros ya no existe en AWS, ni las tablas
  `parameters_values` y `commercial_routes`.
- **Reunión del 28-oct:** hecha. Rafael está ordenando el feedback en un
  documento propio.
- **Rumbo nuevo (Rafael, 29/30-oct):** un producto de captura de datos por
  chat (Telegram primero, WhatsApp después), flexible para varios rubros, que
  sería la fuente de datos de SmartDecisions y hará variar un poco este
  producto. Por ahora es idea: Rafael pasará sus especificaciones y se diseña
  el plan. Material en `idea/`.
- **SmartBilling, en pausa desde el 30-oct** (todo desplegado); su estado y
  lo que falta para retomarlo no van aquí: los productos no se mezclan.
