# SMARTDECISIONS

> **Documento único del producto.** Qué es, cómo está construido, cómo se prueba,
> qué se hizo y cuándo, y qué falta.
>
> Reemplaza a `POC_EVALUATION.md`, `POC_PROGRESS.md` y `BITACORA.md`, que fueron
> eliminados por redundantes.
>
> **Léelo primero al abrir una sesión de trabajo.** El §7 es el estado operativo.
>
> Complementos vigentes: `CLAUDE.md` (constitución del proyecto),
> `../global-rules.md`, `../boilerplate.md`.
>
> **Última actualización: 2026-09-17**

---

## Regla de oro

La constitución (`CLAUDE.md`) manda sobre
cualquier patrón que se encuentre en el código. **Si el código existente
contradice la constitución, se avisa — no se propaga.** Todo el código de
AI, ANALYTICS, INGEST, MINING_ANALYSIS, OPTIMIZATION y QUOTES fue escrito por Claude: no existe "código
heredado" que sirva de excusa.

---

## 1. Qué es y para quién

Plataforma SaaS que convierte **un archivo de ventas** en decisiones comerciales
accionables: qué ofrecer a cada cliente, cuánto se va a vender, a quién estás por
perder, cuánto ganas de verdad y en qué orden recorrer la ruta. **Sin ERP, sin
instalación y sin proyecto de integración.**

**Concepto diferenciador:**
```
Afinidad × Drop Size = Oportunidad Comercial Real
```

**Tesis de coherencia — lo que lo hace un producto y no tres herramientas:** una
sola carga de ventas alimenta todos los módulos. El mismo archivo que produce el
dashboard produce el pronóstico, la segmentación, la rentabilidad y el mapa de
rutas. *Si un módulo necesita que el usuario cargue datos aparte, ese módulo está
mal diseñado.*

**Mercado:** primero gerencias comerciales de distribuidoras y consumo masivo en
Bolivia. Segundo vertical: mineras y comercializadoras (módulo de cotizaciones).

**Marca:** empresa **BearSoft**, producto **SmartDecisions**. TRADE, FORMS,
SUPPLIES, CMS y MINING_SUMMIT **no** son parte del producto: son módulos de
clientes que viven en el monorepo por conveniencia.

### Idioma
- **Todo lo que ve el usuario va en castellano**: UI del frontend, reportes
  descargables y el contenido del Excel de plantilla. La primera versión se vende
  en Bolivia.
- **Todo el código va en inglés**: identificadores, funciones, clases, comentarios,
  docstrings **y los campos del contrato JSON**.
- Más adelante habrá un internacionalizador para que frontend y descargables
  salgan en otros idiomas, principalmente inglés.

---

## 2. Cómo está construido

### 2.1 Servicios

Microservicios Python (FastAPI + Mangum sobre Lambda), Clean Architecture. Todos
validan `Authorization` contra AUTH.

**Base** (compartidos por todos los productos de BearSoft):

| Servicio | Función | Datos |
|---|---|---|
| 🔐 AUTH | JWT, usuarios, login. Token de 30 min. | DynamoDB |
| 🔔 EVENTS | Auditoría y logs de uso | DynamoDB |
| 📁 FILES | S3: subida, lectura, borrado, URLs pre-firmadas | S3 |

**SmartDecisions:**

| Servicio | Función | Infra |
|---|---|---|
| 📥 INGEST | Plantilla, parseo, validación y normalización del archivo de ventas, de los cobros y del stock | Lambda 1024 MB / 30 s |
| 📊 ANALYTICS | Resumen, fuente de volumen, afinidad, pronóstico, segmentación, crecimiento, concentración, eficiencia, margen, cartera, cuentas por cobrar y stock | Lambda 2048 MB / 120 s |
| 🗺️ OPTIMIZATION | Días de visita por proximidad y orden de paradas | Lambda 256 MB / 30 s |
| ⛏️ MINING_ANALYSIS | Cotización oficial de minerales, proyección, boletín PDF/PNG del Ministerio | Lambda 1024 MB · persistencia conmutable SQL/DynamoDB |
| 💵 QUOTES | Tipo de cambio oficial del BCB, proyección y escenario de venta | Lambda 256 MB |
| 🧠 AI | Capa de interpretación: convierte la respuesta de cualquier servicio en una explicación | Lambda 512 MB · Bedrock |

**ML_FUNCTIONS** (regresión, gradiente, Z-score) sigue desplegado pero **ningún
servicio lo consume**: su único cliente era el Playground, que se retiró del
portal. Se reubicará como demo de la línea de capacitación en `bearsoft.com.bo`.

> **LOCALIZATION no es parte de SmartDecisions** — es de Binaria. Las rutas las
> resuelve OPTIMIZATION.

**Qué entra en una revisión general y qué no.** Los diez servicios del producto
son AI, ANALYTICS, AUTH, EVENTS, FILES, INGEST, MINING_ANALYSIS, ML_FUNCTIONS,
OPTIMIZATION y QUOTES. **FORMS, LOCALIZATION, TRADE, EVENTS_MYSQL, PLANNING,
CMS, MINING_SUMMIT y SUPPLIES no se tocan nunca** sin que Rafael lo pida para
ese servicio en concreto: son de clientes —Binaria y el Ministerio— y viven en
el monorepo por conveniencia. Un hallazgo legítimo en uno de esos ocho se
reporta y se espera el OK; no se corrige de paso.

**Frontend:** `portal/demo/` — Vanilla JS, sin build, S3 + CloudFront.
`app/frontend/` es el prototipo Streamlit original: **está muerto**.

### 2.2 Módulos del producto

Cada módulo es una pregunta de negocio, no un algoritmo. *El usuario nunca lee
"regresión logística"; lee la pregunta que le importa.*

| Módulo | Pregunta que responde | Estado |
|---|---|---|
| Resumen Comercial | ¿Cómo vamos? ¿Crece? ¿De quién dependemos? ¿Cuánto ganamos? | ✅ |
| Fuente de volumen | ¿De qué productos y de qué clientes sale la venta, y de dónde vino el movimiento del mes? | ✅ |
| Oportunidades | ¿Qué le ofrezco a cada cliente y cuánto vale? | ✅ |
| Pronóstico | ¿Cuánto voy a vender los próximos meses? | ✅ |
| Segmentación | ¿Quiénes son mis clientes valiosos? | ✅ |
| Salud de Cartera | ¿A quién estoy por perder? | ✅ |
| Cuentas por cobrar | ¿Cuánto me deben, qué tan vencido está, cuánto voy a recuperar y qué deja el crédito? | ✅ |
| Stock del día | ¿Cuántos días me dura lo que tengo, qué está por quebrar y cuánto capital está quieto? | ✅ |
| Rutas | ¿En qué orden visito y qué le llevo a cada uno? | ✅ |
| Cotizaciones y proyecciones | ¿A qué precio está el mineral y el dólar, y conviene vender hoy o esperar? | ✅ |
| Interpretación (IA) | ¿Qué significa esto? — sobre cualquiera de las pantallas anteriores | ✅ |
| Predicciones de fuga | ¿Qué cliente va a dejar de comprarme? | 📋 |
| Retail | Módulo aparte, con su propio contrato de datos | 📋 |

**Playground ML se retira.** Exponía las tripas de una implementación de
descenso de gradiente ("Z-Score sobre una matriz", "Sigmoid en batch"): un
laboratorio de curso, no un producto. `ml_functions` sobrevive como **motor**
detrás de Predicciones, nunca como pantalla.

### 2.3 Stack

Python 3.14 · FastAPI · Pydantic V2 · Mangum · pandas/numpy · pandera ·
DynamoDB (boto3) + S3 · Vanilla JS + Chart.js + Leaflet · pytest · Pylint 10.00.

**Librerías descartadas — no reintroducir sin releer esto:**

| Librería | Motivo |
|---|---|
| `mlxtend` | Arrastra scikit-learn + scipy + matplotlib. Apriori reimplementado en pandas puro. |
| `osmnx`, `networkx` | Arrastran geopandas, shapely, fiona, pyproj. Reemplazados por OSRM vía `requests`. |
| `scikit-learn` | Solo se usaba para k-means; reimplementado en numpy (60 líneas). |
| `Prophet`, `statsmodels` | Peso desproporcionado: el pronóstico usa `numpy.polyfit` y media móvil. |
| `folium` | Genera HTML estático; artefacto de notebook, no UI web. Se usa Leaflet. |
| `OR-Tools` | Innecesario a esta escala: vecino-cercano + 2-opt resuelve decenas de paradas. |
| `Streamlit` | Sin auth propia, sin multi-tenant, sin marca. Callejón sin salida para un SaaS. |

### 2.4 Límites de infraestructura que condicionan el diseño

- **Lambda: 250 MB sin comprimir.** Es la restricción que eliminó las librerías
  de arriba.
- **API Gateway: 29 s de timeout y 10 MB de payload.** Ambos nos golpearon en
  producción. Soluciones: los archivos suben **directo a S3** con URL pre-firmada
  (evita el 413); la ingesta es **síncrona** porque 120k filas se parsean en menos
  de 1 s y lo lento es la subida del navegador, que no cuenta para el timeout.
- **DynamoDB: 400 KB por ítem.** Por eso un run de analytics recorta a los
  mejores por producto: 18.851 oportunidades no entran.
- **ANALYTICS corre con 2048 MB** porque con 256 MB la afinidad excedía los 29 s.
- **Sin presupuesto RDS.** Todo lo nuevo va a DynamoDB + Lambda + S3/CloudFront.
- **OSRM** (Open Source Routing Machine) traduce coordenadas a rutas por calles
  reales. Hoy usamos el servidor público de demostración, que tiene límite de
  tasa. Mitigado con **una sola llamada por día** en vez de una por tramo. Si un
  cliente lo usa a diario, se levanta un OSRM propio en contenedor.

---

## 3. Contrato de datos

Una fila = una línea de venta. Los encabezados de cara al cliente son **en
español familiar**; `column_mapper` los traduce a los nombres canónicos internos y
acepta además los alias típicos de un ERP (`Numero Factura`, `Codigo Sap`,
`Cliente ID`, `Unidades`, `Monto Final`…).

Los canónicos van **en inglés**, como todo identificador del código. La fuente
de verdad es `SALES_COLUMNS` en `services/ingest/schemas/ingest.py`: de ahí se
derivan el mapeador de encabezados, el esquema del DataFrame, las listas de
obligatorias y opcionales y la plantilla publicada.

| Columna (plantilla) | Canónico | Oblig. | Para qué sirve |
|---|---|---|---|
| Fecha | `date` | Sí | Tendencia, pronóstico, estacionalidad |
| Nro Factura | `order_id` | Sí | Agrupa la canasta — **sin esto no hay afinidad** |
| Cliente | `pos_name` → `pos_id` | Sí | Segmentación, cartera. El identificador lo deriva el servicio |
| Producto | `product_name` → `product_id` | Sí | Afinidad, ABC. El identificador lo deriva el servicio |
| Cantidad | `quantity` | Sí | Drop size |
| Zona / Ciudad / Region | `zone` / `city` / `region` | No | Análisis por sector |
| Canal | `channel` | No | Comparación entre canales |
| Vendedor | `seller` | No | Productividad de la fuerza de venta |
| Latitud / Longitud | `latitude` / `longitude` | No | **Habilita el módulo de rutas** |
| Categoria | `category` | No | Afinidad por categoría, mix, ABC |
| Precio Unitario | `unit_price` | No | Valorizar oportunidades en Bs |
| **Costo Unitario** | `unit_cost` | No | **Habilita margen y rentabilidad** |
| Monto Total | `total_amount` | No | Si falta, se calcula cantidad × precio |

**Obligatoria para el motor no es lo mismo que obligatoria para el cliente.** El
cliente escribe `Cliente` y `Producto`; `pos_id` y `product_id` los deriva
INGEST, porque el cliente no tiene esos códigos. Por eso `SalesColumn` distingue
`required` de `template_required`.

**Reglas del contrato:**

- **Degradación elegante, no ceros.** Si falta una columna opcional, la sección se
  declara no disponible y la UI la oculta. Mostrar 0% de margen cuando no hay
  costos es mentir.
- **Aceptación parcial.** Las filas inválidas se apartan en un CSV con su motivo y
  el resto se carga. Solo falla el archivo entero si falta una columna obligatoria.
- **Coordenada 0 = sin dato.** Un ERP rellena el GPS faltante con 0; una lectura
  real siempre trae decimales. Se anula el par completo para que el mapa no se
  vaya al Golfo de Guinea.
- **Fechas ISO y dd/mm/aaaa.** Se elige el formato que más fechas resuelva.
- **El motor de análisis es uno solo.** Excel, CSV y una futura integración con
  ERP son adaptadores de ingesta intercambiables. La normalización ocurre una sola
  vez, en INGEST.

### 3.1 Crédito y cobros

El formato lo definimos nosotros y el ERP se adapta. Las columnas de la venta
viajan en la **misma hoja de ventas**
—una sola carga sigue alimentando todos los módulos— y son opcionales: sin ellas,
el tablero de Cuentas por cobrar simplemente no se ofrece.

| Columna (plantilla) | Canónico | Qué es |
|---|---|---|
| Condicion Venta | `payment_terms` | `CONTADO` / `CREDITO`. Reemplaza el `Tipo Pago` que traen los ERP |
| Plazo Dias | `credit_days` | De 5 a 120; con la fecha de la venta deriva el vencimiento |
| Fecha Vencimiento | `due_date` | Si viene, manda sobre el plazo |
| Responsable Cobro | `collector` | Si falta, cae en `Vendedor` |
| Limite Credito | `credit_limit` | Del cliente. Sin esto no hay utilización de línea |

Los cobros son un **contrato aparte que se casa con la venta**, cargable después
y de forma incremental (hoja `Cobros` del mismo libro, o su propio archivo):

| Columna | Canónico | Qué es |
|---|---|---|
| Nro Factura | `order_id` | La llave contra la venta. Ya es obligatoria en la carga inicial |
| Fecha Cobro | `payment_date` | |
| Monto Cobrado | `paid_amount` | Admite abonos parciales: varias filas por factura |
| Medio | `payment_method` | Opcional |
| Responsable Cobro | `collector` | Opcional: quien cobró puede no ser el asignado |

**Reglas propias:**

- **La cuenta por cobrar vive al nivel de factura.** En la hoja de ventas una
  factura ocupa varias filas —una por producto—, así que el saldo se arma con la
  suma de `total_amount` por `order_id`. Si una misma factura apareciera con dos
  fechas o dos clientes, va como incidencia con código: no se elige una fila.
- **Factura sin cobros = saldo abierto, no error.** Es lo que permite cargar
  ventas hoy y cobros mañana.
- **Cobro sin venta = incidencia con código**, nunca descarte en silencio.
- **Parámetros de política por cliente en tabla**, con fallback al `.env` **campo
  por campo**: tramos de antigüedad, matriz de provisión, tasa financiera diaria,
  umbral de moroso y plazo por defecto. Quien sólo quiere cambiar la tasa no
  debería tener que declarar los siete.

### 3.2 Stock del día

Una **foto**, no un libro de movimientos: una fila por producto y día con lo que
había en el almacén. Se carga por su propio endpoint porque cambia todos los días
mientras el archivo de ventas se carga una vez, y porque el ERP que lo exporta
casi nunca es el mismo sistema que emite las facturas. Una carga nueva
**reemplaza** la anterior.

| Columna (plantilla) | Canónico | Qué es |
|---|---|---|
| Fecha | `snapshot_date` | El día de la foto |
| Producto | `product_name` → `product_id` | El identificador lo deriva el servicio |
| Existencia | `on_hand` | Unidades en el almacén |
| Comprometido | `committed` | Lo que el ERP ya reservó en pedidos. **Se lee, no se escribe** |
| En Transito | `in_transit` | Opcional |
| Almacen | `warehouse` | Opcional |
| Costo Unitario | `unit_cost` | Opcional. Sin él no se valoriza el inventario |

**La línea que no se cruza.** `disponible = existencia − comprometido` **reporta**
un compromiso que el ERP del cliente ya tomó. SmartDecisions no reserva, no
aparta y no promete stock: ser dueño de esa verdad significa ser dueño de la
concurrencia, la idempotencia y la culpa cuando el ERP diga otra cosa — una pelea
que este producto pierde contra el ERP del cliente. El endpoint de "almacén con
reservas" que se sugirió en la reunión **queda fuera a propósito**.

**Lo que sí es BI** y una consulta de saldo no da: cobertura en días a la demanda
observada, fecha estimada de quiebre, capital inmovilizado en lo que no rota, y
la clase ABC de cada producto para que un quiebre en un A no se lea como uno en
un C.

---

## 4. Cómo probarlo

### 4.1 Datos de muestra

`tools/build_sample_dataset.py` genera los archivos desde el export real de un
distribuidor. **Muestrea por cliente, nunca por fila** — un muestreo aleatorio
rompe las canastas y la afinidad deja de encontrar reglas.

```bash
python tools/build_sample_dataset.py --rows 24000 --months 24 \
    --output tools/samples/ventas_demo.xlsx        # demo de venta
python tools/build_sample_dataset.py --rows 2000 --months 3 \
    --output tools/samples/ventas_muestra_2k.xlsx  # fixture de pruebas
```

| Archivo | Filas | Período | Clientes |
|---|---|---|---|
| `ventas_demo.xlsx` | ~22.000 | 24 meses | 266 |
| `ventas_muestra_2k.xlsx` | ~2.000 | 3 meses | 130 |

Ambos traen `Costo Unitario`, geo limpia al 100% y una hoja **"Origen de los
datos"** que declara qué es real y qué simulado. Esa hoja no es decorativa: el
costo, el historial anterior a nov-2023 y el movimiento de clientes son
sintéticos, y el archivo se entrega a prospectos.

**Limitaciones del dato base:** el export real cubre 4 meses, una ciudad, una
región y un canal, y su último mes está incompleto. Por eso el generador corta el
mes parcial y extiende el historial con tendencia, estacionalidad y ruido,
**calibrado contra la rotación real del archivo (82% de retención mensual)**.

### 4.2 Entorno local

```bash
python -m venv .venv && source .venv/bin/activate
docker run -d --name dynamodb-local-container -p 3100:8000 amazon/dynamodb-local
for svc in ingest optimization analytics; do
    (cd services/$svc && ./dynamodb.sh && pip install -r requirements.txt)
done

cd services/ingest       && python main.py   # :3110  /docs
cd services/optimization && python main.py   # :3120  /docs
cd services/analytics    && python main.py   # :3130  /docs
cd portal && python -m http.server 8000      # http://localhost:8000/demo/
```

Los `.env` ya apuntan a las URLs productivas de AUTH/EVENTS/FILES y a DynamoDB
local. Si nadie los tocó, no hay nada que configurar.

### 4.3 Batería de verificación

```bash
(cd services/ingest       && pytest tests/ -q && pylint services/ controllers/ routes/ schemas/ tests/)
(cd services/analytics    && pytest tests/ -q && pylint services/ controllers/ routes/ schemas/ tests/)
(cd services/optimization && pytest tests/ -q && pylint services/ controllers/ routes/ schemas/ tests/)
```

**Umbral: todo verde y Pylint 10.00/10.** Al 2026-08-28: ingest 14/14,
analytics 51/51, optimization 15/15.

Además hay que verificar a mano:

| Qué | Cómo | Esperado |
|---|---|---|
| Paridad XLSX/CSV | Subir el mismo contenido en ambos formatos | Filas idénticas |
| Degradación | Subir archivo sin `Costo Unitario` | El bloque de margen **desaparece**, no muestra ceros |
| Ventana de fechas | `?date_from=&date_to=` en cualquier análisis | Bloque `periodo` coherente; rango vacío = error explícito, no informe en cero |
| Trazabilidad | `GET $EVENTS_URL/v1/events/audit?microservice=INGEST` | Un audit y un usage_log por acción |

### 4.4 Cifras esperadas con `ventas_demo.xlsx`

| Módulo | Qué debe salir |
|---|---|
| Carga | 22.008 / 22.008 filas válidas, 0 rechazadas |
| Resumen | ~Bs 1,17 M de venta, 24 meses en la tendencia |
| Margen | ~21,7% bruto; CAFES primero por margen |
| Oportunidades | ~964 acciones en ~260 PdV, ~Bs 61.900 |
| Pronóstico | 24 puntos históricos |
| Segmentación | Alto ≈ 54 clientes concentrando ~63% |
| Cartera | 25 en riesgo + 22 perdidos; churn mensual ~20% |
| Rutas | 5 días de 50-54 paradas; ~5% menos km que el orden voraz |

**Umbrales de performance:** ingesta de 22k filas < 3 s · resumen completo < 1 s ·
afinidad < 5 s · plan de rutas de 5 días < 15 s · cero 5xx en el camino feliz.

---

## 5. Guion de demo comercial

Vive en **`GUION_DEMO.md`**: los diez minutos paso a paso, con los números
de `ventas_demo.xlsx` y qué hacer si algo falla. Se enriquece aparte.

---

## 6. Estado de cada pieza

Al **17 de septiembre de 2026**.

| Pieza | Estado | Pendiente |
|---|---|---|
| INGEST | ✅ desplegado 16-sep | Lee `Cobros` y `Stock` en la subida por S3; libro abierto una sola vez (13,8 s) |
| ANALYTICS | ⏳ pendiente de redeploy | Tramos de antigüedad vacíos bajo pandas 3 sin pyarrow (comparación por `.value`) |
| OPTIMIZATION | ✅ desplegado | — (los puntos viejos se borraron el 16-sep) |
| MINING_ANALYSIS | ✅ desplegado | El ETL escribe sólo en el relacional (opción **b** pendiente) |
| QUOTES | ✅ desplegado | Redesplegar por la ventana del bloque del BCB |
| AI | ✅ desplegado, 9 roles cargados | Encender `AI_URL` en el portal |
| Portal demo | ✅ publicado 17-sep | Cerrar la verificación de Cartera y Cuentas por cobrar tras el deploy de ANALYTICS |
| bearsoft.com.bo | ✅ publicado | — |
| Logs de CloudFront | ✅ activos en los dos sitios | Retención de 90 días; reporte con `tools/traffic_report.py` |
| Streamlit del Ministerio | ⚠️ revisar | Pide `pandas<3` y el venv ya está en pandas 3 |

**Lo que falta para vender, no para demostrar:** aislamiento por empresa (hoy es
por correo del usuario), control de suscripción, retención de datos y persistencia
de lo que produce la capa de IA.

---

## 7. Decisiones vigentes

Las que siguen condicionando el código. Las que se revirtieron no están.

### Negocio

- **La cotización oficial de una quincena es el promedio de la quincena
  anterior.** La media del 1 al 15 rige del 16 al 30. Es el precio con el que se
  liquida y **no** es la última cotización del día. El promedio va sobre los
  registros que ese mineral tenga: Estaño puede tener 10 y Wólfram 2 en la misma
  quincena.
- **El BCB publica el viernes de noche una cotización que rige sábado, domingo y
  lunes.** El bloque está en `RATE_BLOCK_WEEKDAYS`, y la ventana del sync llega
  al final del bloque, no a "hoy": el lunes ya está publicado desde el viernes.
- **El 27 de junio de 2026 el tipo de cambio dejó de estar fijo.** Toda serie que
  se proyecte arranca ahí; los años de 6,86 pertenecen a otro régimen.
- **El Ministerio de Minería recibe el boletín en PDF y PNG** a cambio de los
  datos de cotizaciones. Ese intercambio no se toca.

### Técnicas

- **El backend devuelve datos y códigos, nunca texto de cara al usuario.** 14
  enumeraciones, 165 códigos. La interpretación es del frontend o de la capa de
  IA. No hay catálogos de textos en el repositorio.
- **Nada configurable vive en el código.** Las variables son **requeridas**: un
  `ENV_VARS['X'] or 30` sigue siendo un número elegido por el código. Si falta
  configuración, el servicio no arranca.
- **El modelo predictivo es suavizado exponencial con tendencia amortiguada**,
  con parámetros ajustados por backtest. Reemplazó a una recta de mínimos
  cuadrados que erraba el doble. Cada proyección se publica con **su error
  medido y el del modelo ingenuo**, para que se pueda juzgar.
- **El dueño es parte de la consulta, no un filtro posterior.** En OPTIMIZATION
  además es parte de la clave de partición, porque el upload borra la partición
  antes de escribir.
- **Un archivo se identifica por su contenido.** Misma huella y mismo dueño = el
  mismo dataset; no se duplica.
- **La capa de IA recibe la respuesta del backend tal cual.** No re-declara la
  forma: eso serían dos contratos para una sola cosa. `view` sólo elige el rol.
- **El entorno local corre las mismas versiones que el Lambda.** No se fijan
  versiones en `requirements.txt`; se actualiza `SmartBear/.venv` a lo último
  antes de probar. El Lambda **no tiene pyarrow**: en pandas 3 una columna de
  miembros de un `str, Enum` se compara por `.value`, nunca contra el miembro.
- **Un libro se abre una sola vez por subida.** Ventas, cobros y stock leen
  de `read_workbook`; tres aperturas de openpyxl agotaban los 30 s del Lambda.
- **Los roles de la IA viven en DynamoDB, versionados**, y se administran por
  `POST /v1/ai/roles`. Una versión nueva desactiva la anterior sin borrarla, y
  como la versión participa de la clave de caché, reajustar deja de servir lo
  viejo automáticamente.
- **No se crean carpetas nuevas dentro de un microservicio.** `scripts/` existe
  sólo en MINING_ANALYSIS, por la carga quincenal manual que no tiene alternativa.

### Infraestructura

- **Sin RDS por presupuesto.** Todo servicio nuevo va a DynamoDB + Lambda + S3.
- **`build_and_deploy.sh` no crea claves compuestas** ni admite dos tablas por
  servicio. Las tablas se crean con `create_dynamodb_tables.sh`; el acceso lo
  cubre `AmazonDynamoDBFullAccess` en el rol.
- **El `.env` completo viaja a las variables de entorno del Lambda**, con
  sintaxis abreviada: **ningún valor puede llevar coma**.
- **Bedrock exige perfiles de inferencia** (`us.` delante) y un formulario de
  caso de uso por cuenta.
- **Los deploys de backend los hace Rafael**; los de frontend, el asistente.

---

## 8. Estado al día

**17 de septiembre de 2026.** El detalle de cada cambio está en git y en la
memoria de sesión; aquí sólo lo que hace falta para retomar.

**Hecho en la ronda de observaciones del 16-sep:**
- INGEST lee `Cobros` y `Stock` en la subida que usa el portal (antes sólo
  en el multipart) y abre el libro una sola vez: 13,8 s las tres hojas.
- ANALYTICS: tramos de antigüedad vacíos en producción por pandas 3 sin
  pyarrow; corregido con comparación por `.value` y test de regresión.
- Portal: paginador único a 10 filas en todas las tablas (Cotizaciones
  incluido), gráficos sin deformar, semáforo de concentración, "menos
  vendidos" en barras, tablas pareadas al 50 %, menú en pirámide, "Rutas",
  badges de stock/riesgo con color, panel de IA oculto hasta pedirlo.
- Backtest de minerales (808 cotizaciones, 8 quincenas): pronosticar a 15
  días desde la serie no supera a "el precio se queda" (2,5 %); anticipar la
  oficial con los días ya cotizados sí: 0,6 % a mitad de quincena, 0,12 %
  en la víspera.

**Pendiente de Rafael:** desplegar **ANALYTICS**; entrar en la pestaña de
prueba para cerrar la verificación de Cartera y Cuentas por cobrar.

**Siguiente:**
1. RUTAS en dos fases: hoja `Visitas` (plan vs ejecución, BI puro) y luego
   registro de ubicación por web sin app móvil, portado de LOCALIZATION a
   DynamoDB dentro de OPTIMIZATION. Las planificadas se crean a partir de la
   ejecución salvo que exista una previa.
2. Minerales sin gastar: cobre, estaño, plomo y zinc diarios desde Westmetall
   (leer sus términos primero), regalías con las fórmulas del Art. 227 como
   parámetros en base, y el resto de minerales sólo del informe quincenal.
   La proyección a 30/60/90 días pasa a secundaria.
