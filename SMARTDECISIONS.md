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
> **Última actualización: 2026-08-29**

---

## Regla de oro

La constitución (`CLAUDE.md` + `global-rules.md` + `boilerplate.md`) manda sobre
cualquier patrón que se encuentre en el código. **Si el código existente
contradice la constitución, se avisa — no se propaga.** Todo el código de
INGEST, ANALYTICS y OPTIMIZATION fue escrito por Claude: no existe "código
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
| Rutas de visita | ¿En qué orden visito y qué le llevo a cada uno? | ✅ |
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

## 5. Guion de demo comercial (10 minutos)

> Requiere el frontend desplegado (ver §7.1). Los números son los de
> `ventas_demo.xlsx`; si cambia el generador, actualizar también §4.4.

### Antes de la reunión

| Cosa | Estado |
|---|---|
| Dataset cargado | Subir `ventas_demo.xlsx` **antes** de la reunión y dejar la sesión abierta: la carga tarda y no aporta al relato |
| Credenciales | Listas para copiar y pegar |
| Navegador | Sesión nueva, sin caché vieja, dev tools cerrados |
| Respaldo | Capturas de las cuatro pantallas clave por si falla la red |

### 1. El problema (1 min)

> "Una distribuidora mediana toma sus decisiones comerciales con la intuición del
> gerente y un reporte de ventas que solo dice cuánto se vendió. No usa un ERP
> analítico porque cuesta caro, tarda meses y necesita un consultor. Pero **sí
> tiene** un archivo de ventas. SmartDecisions convierte ese archivo en una lista
> de acciones concretas, con su valor en bolivianos, en menos de un minuto."

Diferenciador en pantalla: `Afinidad × Drop Size = Oportunidad Comercial Real`.

### 2. Resumen Comercial (3 min) — "¿cómo vamos?"

Abrir el módulo. Bs 1,17 M de venta, 24 meses de tendencia, estacionalidad con el
pico de noviembre.

**El momento que engancha es Rentabilidad:**

> "Miren esto. LÁCTEOS vende Bs 192.161 y deja 12%. NUTRICIÓN vende menos de la
> mitad y deja 29%. El reporte de ventas que ustedes reciben hoy pone a LÁCTEOS
> arriba. **El que más vende casi nunca es el que más deja**, y esa diferencia no
> la ve nadie hasta que alguien la calcula."

Seguir con Concentración: cuántos clientes hacen el 80% de la venta, y el ABC.

### 3. Oportunidades (3 min) — "¿qué le ofrezco a cada cliente?"

964 acciones en 260 puntos de venta, Bs 61.900 de venta potencial.

> "Esto no es un tablero que muestra lo obvio. Le dice a su vendedor: *a esta
> tienda no le estás vendiendo esta categoría y deberías, porque tiendas con su
> mismo patrón de compra la venden bien*. Con el monto esperado al lado."

Abrir el drill-down de un producto y mostrar los comercios interesados con su
motivo y probabilidad.

### 4. Salud de Cartera (1,5 min) — "¿a quién estoy por perder?"

> "25 clientes en riesgo. No 103: **25**, ordenados por lo que está en juego,
> para que un vendedor los trabaje esta semana. Los que ya se fueron hace más de
> seis meses están en otra lista, porque eso es una campaña de reactivación, no
> una visita."

### 5. Rutas de visita (1,5 min) — el cierre visual

Abrir el mapa. Es el momento más vistoso: calles reales, paradas numeradas y
coloreadas por valor del cliente.

> "Los mismos clientes del archivo, agrupados por cercanía en días de visita, y
> ordenados para recorrer menos. Cada parada dice a quién visita, cuánto compra y
> qué ofrecerle. Un 5% menos de kilómetros es combustible que no se gasta."

### 6. Cierre (30 s)

> "Todo lo que vio salió de **un solo archivo de ventas**. Sin ERP, sin
> instalación, sin proyecto de integración. El siguiente paso es que traiga un
> archivo de su negocio a una sesión de trabajo y vea sus propias oportunidades.
> ¿Cuándo le queda?"

### Si algo falla

| Falla | Cómo recuperar |
|---|---|
| El archivo no carga | Tener otra sesión con el dataset ya cargado en una pestaña aparte |
| Un análisis tarda | La afinidad es el más pesado. Hablar mientras calcula: es buen momento para explicar qué está haciendo |
| El mapa no carga | Depende de OSRM público. Pasar a Cartera y volver después; si insiste, mostrar la captura |
| Sin internet | Ir a las capturas. No improvisar con la consola |
| **"¿Y mis datos?"** | El archivo queda en el bucket S3 del cliente vía el servicio FILES. Sin terceros, sin entrenamiento cruzado, y se borra cuando termina la prueba |
| **"¿Los datos del demo son reales?"** | Decir la verdad: vienen de una operación real de consumo masivo, anonimizada; el costo y el historial extendido son simulados y **está declarado en una hoja del propio archivo**. Esa honestidad genera más confianza que fingir |

---

## 6. Estado de cada pieza

Al **7 de septiembre de 2026**.

| Pieza | Estado | Pendiente |
|---|---|---|
| INGEST | ✅ desplegado | — |
| ANALYTICS | ✅ desplegado | — |
| OPTIMIZATION | ✅ desplegado | Los 109 puntos viejos quedaron con la clave anterior; se regeneran subiendo el CSV |
| MINING_ANALYSIS | ✅ desplegado | El ETL escribe sólo en el relacional (opción **b** pendiente) |
| QUOTES | ✅ desplegado | Redesplegar por la ventana del bloque del BCB |
| AI | ✅ desplegado, 9 roles cargados | Encender `AI_URL` en el portal |
| Portal demo | ✅ publicado | — |
| bearsoft.com.bo | ✅ publicado | — |
| Logs de CloudFront | ✅ activos en los dos sitios | Retención de 90 días; reporte con `tools/traffic_report.py` |
| Streamlit del Ministerio | ✅ operativo | Carga quincenal contra MySQL local |

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

## 8. Lo último que se hizo

**14 de septiembre de 2026 — observaciones posteriores a la reunión del 9.**

Se revisaron con clientes potenciales sólo Análisis Comercial y Optimización de
rutas. De ahí salieron tres tableros nuevos, y de la revisión con el economista,
la corrección del panel del dólar.

### Fuente de volumen — módulo nuevo

Existía repartido en tres bloques y en ninguno se veía como una pregunta propia:
el mix de categorías dentro de Crecimiento, el ABC dentro de Concentración y un
ranking de productos en el Resumen. Ninguno cruzaba cliente con producto.

1. **`services/volume.py`** (596 líneas) con lo que el bloque contesta: curva de
   Pareto de productos con su alcance —a cuántos clientes le llega cada uno—,
   clientes con el **producto que los sostiene** y qué porcentaje de su compra
   representa, el cruce cliente × producto leído de los dos lados, y la
   **descomposición del último movimiento** en precio, cantidad, cruce, entradas
   y salidas por producto, y en clientes nuevos, perdidos y retenidos. Las dos
   descomposiciones suman el mismo cambio, así que ninguna puede explicar más de
   lo que pasó.
2. **Las piezas se mudaron, no se copiaron.** `category_mix` salió de
   `growth.py`, el ABC salió de `concentration.py` y `top_clients` —que el
   frontend nunca renderizaba— se reemplazó por la tabla de clientes con ancla.
   `AbcBlock.products`, que viajaba con hasta 300 filas sin que nadie las
   mostrara, dejó de existir.
3. **`hhi_level` es ahora un helper compartido** en `analytics_utils.py`: los dos
   motores hacen la misma pregunta a sujetos distintos —clientes y productos— y
   cada uno trae sus propios cortes del `.env`.
4. **Nueve variables nuevas** `VOLUME_*` en el `.env`; se fueron
   `CONCENTRATION_ABC_A_LIMIT`, `CONCENTRATION_ABC_B_LIMIT` y
   `CONCENTRATION_MAX_ABC_ROWS`.
5. **Vista propia en el portal** (`stepVolume`), con su tarjeta en el menú, su
   sello de cálculo y su botón de IA. **Sale de la respuesta del resumen**: pedir
   la pregunta nueva no cuesta otra llamada al endpoint, y `openAnalysis` acepta
   la vista en la que terminar.
6. **Rol de IA `volume_source` v1** sembrado en `ai_prompts`, y la vista sumada a
   la lista cerrada de `ViewName`. La IA recibe **su bloque**, no la respuesta
   entera del resumen: mandarla completa hacía que explicara pantallas que no se
   están viendo.
7. **Dos fallos de paso, arreglados:** las tarjetas KPI armadas en el frontend
   —las de Concentración y las de este bloque— salían **sin etiqueta y sin nota**,
   porque `kpiLabel` y `kpiHint` sólo sabían traducir `metric_code` y no caían en
   la etiqueta propia de la tarjeta.

**Verificado:** 68 tests en verde y Pylint 10.00 en ANALYTICS; el motor corrido
sobre `DetalleVentas.csv` real (121.236 filas, 211 productos con venta: 33 hacen
el 80%, HHI 0,0408) con las dos descomposiciones cerrando en el mismo cambio; y
el renderizador del portal corrido en Node contra esa misma salida —vista,
KPIs, seis tablas, los dos gráficos, el payload de la IA y el caso sin datos—.

**Pendiente de Rafael:** desplegar **ANALYTICS** (bloque nuevo + nueve variables
nuevas del `.env`) y **AI** (la vista `volume_source` en el `Enum`). El portal
**no se publicó todavía a propósito**: sin el backend nuevo la vista mostraría su
nota de vacío. En cuanto despliegues, publico y verifico.

1. **Assets de marca del demo.** `portal/demo/assets/` había quedado con el
   juego viejo —el oso de dibujo animado y los favicons de julio— mientras la
   página se actualizó el 11 y 13 de septiembre. Se copió el juego nuevo a los
   seis HTML del demo y se subió un `favicon.ico` real, que antes devolvía HTML.
   El estampador de `tools/deploy_demo_portal.py` ahora **cubre imágenes e
   iconos**, no sólo `.js`/`.css`: reemplazar los bytes detrás de un nombre fijo
   dejaba a CloudFront y al navegador sirviendo la imagen anterior.
2. **Frase de apertura de `bearsoft.com.bo`** reemplazada por la versión que
   trajo Rafael, con el cierre que ata la experiencia al producto. El
   `og:description` se alineó: decía "Veintidós años".
3. **Panel del dólar: una sola tabla y un solo gráfico.** Había dos tablas
   —una fija, alimentada por `/forecast` con el método del servicio, y otra que
   seguía al selector—: la misma pregunta contestada dos veces y con dos
   respuestas a la vista. Ahora el selector de modelo manda sobre las cifras, el
   gráfico y la tabla única. Se cayó la llamada a `/forecast` en ese panel
   —`/bench` ya trae histórico, vigente y confianza—, o sea **una invocación de
   Lambda en vez de dos**.
4. **El modelo por defecto dejó de estar escrito en el código.** Era
   `DEFAULT_MODEL = 'DAMPED_TREND'`; ahora es el de menor error medido al plazo
   pedido, que el servicio ya devuelve primero, y la pantalla **explica por qué
   lo es** con su error y el número de réplicas. Mientras el usuario no elija,
   el default sigue al plazo; en cuanto elige, se respeta su elección.
5. **Dos contadores de histórico**, que no se deducen uno del otro: cotizaciones
   publicadas y días corridos que cubren. El BCB publica en días hábiles y el
   viernes cubre el fin de semana. La fecha de arranque de la serie sale del
   dato y no de un `27/06/2026` escrito en el HTML.
6. **La capa de IA recibe el modelo elegido.** Antes se le pasaba el banco
   completo y no sabía cuál estaba viendo el usuario: explicaba nueve
   proyecciones donde en pantalla hay una. Viaja la respuesta tal cual más
   `selected_model`; la vista del escenario además recibe el resultado del
   escenario, que no le llegaba.

**Verificado:** `node --check`, arnés en Node sobre la vista con una respuesta
de `/bench` fabricada (selector, tabla única, casilla de proyectadas, payload de
IA y cambio de modelo), y lo publicado comparado con lo local en demo y página.

**Pendiente de Rafael (backend):** nada de esto lo necesita. El texto del rol
`rate_forecast` en `ai_prompts` sí conviene versionarlo para que use
`selected_model`, y eso se administra por la API, no por el repositorio.

### Cuentas por cobrar — módulo nuevo

Lo pidieron los interesados como el hueco más grande: la mayoría de sus ventas
son a crédito —dijeron cerca del 70%, con plazos de 5 a 120 días— y el archivo de
ventas no responde nada de eso.

1. **Contrato ampliado** (§3.1): cinco columnas de crédito en la hoja de ventas y
   la hoja `Cobros` como contrato aparte, cargable después y de forma
   incremental. Endpoint propio: `POST /v1/ingest/{dataset_id}/collections`. Si el
   libro que devuelve el cliente ya trae la hoja llena, **la misma subida carga
   las dos cosas**.
2. **`services/receivables.py` + `receivables_views.py`** en ANALYTICS. El motor
   mide el libro; el segundo arma las cuatro listas sobre las que se actúa. Todo
   al nivel de factura, contra el **último día con actividad del archivo** y no
   contra hoy: un dataset del trimestre pasado reportaría toda su cartera vencida
   sólo por el paso del tiempo.
3. **Los KPI**, con su descripción en pantalla: antigüedad por tramos con su
   provisión, recuperable contra incobrable, DSO, mora ponderada **por monto** y
   no por factura, CEI —que mide al equipo de cobranza, no a los clientes—, plazo
   otorgado contra plazo real, calendario de vencimientos, curva de cobro por
   cohorte y la lista de gestión ordenada por **recupero esperado** y no por
   antigüedad: el saldo más viejo suele ser el que menos vuelve.
4. **Margen neto del crédito:** margen bruto − costo financiero − incobrable
   esperado. Sobre el archivo de demo, 22,9% de margen bruto quedan en **15,0%**.
   Es el número que da vuelta una reunión.
5. **Política por cliente** en `analytics_credit_policies`, con fallback al `.env`
   **campo por campo**: quien sólo quiere cambiar la tasa no declara los siete
   parámetros. `GET`/`PUT /v1/analytics/credit-policy`, y la política aplicada
   viaja en la respuesta para que el lector vea qué produjo cada número.
6. **Rol de IA `receivables` v1** sembrado, con una regla explícita: si se cita
   una tasa de pérdida, decir que es un parámetro configurado y no un hecho.

### Stock del día — módulo nuevo

**Se dejó fuera el "almacén con reservas" a propósito**, y coincidimos en el
motivo: SmartDecisions sería dueño de la verdad del stock —concurrencia,
idempotencia, la culpa cuando el ERP diga otra cosa— y esa pelea la pierde contra
el ERP del cliente. Lo que sí se hace: **leer** lo que el ERP ya comprometió y
reportar lo que implica.

1. **Contrato y endpoint** (§3.2): `POST /v1/ingest/{dataset_id}/stock`. Una carga
   nueva reemplaza la foto anterior, que es el punto de una foto diaria.
2. **`services/stock.py`** en ANALYTICS: cobertura en días a la demanda
   observada, fecha estimada de quiebre, exceso sobre el techo de cobertura,
   capital inmovilizado y clase ABC de cada producto. La demanda sale del
   histórico de ventas y **no del módulo de pronóstico**: la cobertura es una
   medición, y mezclarle una proyección haría parecer medida una fecha inferida.
3. **Con stock y sin demanda medida no hay cobertura**: se reporta `NO_DEMAND` y
   todas sus unidades cuentan como capital quieto. Informar cobertura infinita
   disfrazaría de sano un producto que nadie compra.

### Un fallo que venía de antes

El corte ABC comparaba el acumulado **incluyendo** el propio producto, así que un
producto que concentra el 99% de la venta salía **clase C** en vez de A. Corregido
en `volume.py` y en `stock.py`: ahora se compara el acumulado que lo precede, y el
ítem que cruza el umbral pertenece a la clase que cruza. Sobre el archivo real,
las 33 clases A coinciden ahora exactamente con el punto de Pareto.

### Limpieza de reglas rotas

1. **Los cuatro `__all__` los había puesto yo** —verificado con `git log -S`— y
   son inertes: el proyecto nunca usa `from modulo import *`, y no tienen nada que
   ver con `__init__.py`. Quitados. Eso destapó que `services/analytics.py`
   importaba los nueve motores **sólo para re-exportarlos**: el controlador ahora
   importa de cada motor y hay una capa menos.
2. **Los comentarios y docstrings en castellano, traducidos**: 80 líneas en los
   archivos del producto y ocho frases del boilerplate, repetidas por copia en
   los diez servicios. **El boilerplate también**: el `db_connection.py` original
   de EVENTS (agosto 2025) está enteramente en inglés y el castellano lo
   introdujo Claude en commits posteriores. Que un archivo sea contrato significa
   que no se cambia su comportamiento, no que pueda quedar en otro idioma.
3. **El botón de IA de Pronóstico nunca se montaba.** `js/ai.js` lo inserta en
   `.section-head` y esa sección era la única que no la tenía, así que la vista
   estaba registrada y el botón no aparecía en pantalla. Corregido; las ocho
   vistas del módulo comercial tienen ahora su botón.
4. **Skill `/constitucion`** (`.claude/skills/constitucion/`): siete barridos de
   las reglas que **no fallan solas** —idioma, mecanismos inventados, carpetas
   nuevas, DTOs, códigos de UI, configuración y qué se borró de código previo—.
   Con el filtro de los diez servicios en código, no en prosa.

**Verificado:** los diez servicios del producto con su suite en verde y Pylint
10.00 (ANALYTICS 98, MINING_ANALYSIS 87, QUOTES 42, INGEST 34, OPTIMIZATION 19,
AI 16). Los dos motores corridos sobre `ventas_demo.xlsx`: cartera de Bs 187.961
con 57,9% vencido, DSO 71,6 días, CEI 35,5; almacén de 159 productos con 28
quiebres y Bs 60.217 inmovilizados. Las dos vistas del portal corridas en Node
contra esas respuestas, incluidos los casos sin datos.

**Pendiente de Rafael — una sola ronda de despliegue:**

| Servicio | Por qué |
|---|---|
| **INGEST** | Contrato v3, dos endpoints nuevos, `collections.py` y `stock.py` |
| **ANALYTICS** | Cinco motores nuevos, tres endpoints, **28 variables nuevas** en el `.env` y la tabla `analytics_credit_policies` |
| **AI** | Tres vistas nuevas en el `Enum` (`volume_source`, `receivables`, `stock`) |
| **QUOTES** | Sólo la limpieza del `__all__` y el docstring; sin cambio funcional |
| **MINING_ANALYSIS** | Sólo idioma en un comentario y en la descripción de Swagger |
| AUTH · EVENTS · FILES · ML_FUNCTIONS · OPTIMIZATION | Sólo idioma en el boilerplate; van si hay redespliegue de todas formas |

**Ya hecho de este lado, no hace falta pedirlo:**

- **Tabla `analytics_credit_policies`** creada y activa. Se declaró en
  `services/ci/api/create_dynamodb_tables.sh` —que es donde viven las tablas del
  producto— y se ejecutó el script, que es idempotente y saltó las 16 existentes.
  El `services/ci/create_dynamodb_tables.sh` es el de Binaria (perfil
  `deploy_binaria`) y no se toca.
- **Plantilla v3 publicada** en `s3://ml-data-file-handler/ingest/templates/`,
  con las cuatro hojas —Ventas, Cobros, Stock e Instrucciones— y verificada por
  SHA-256 contra el archivo local. Las tres hojas de datos pasan sus tres
  validadores sin una sola incidencia.
- **`AsyncIterator` → `AsyncGenerator`** en los `main.py` de los siete servicios
  que lo usaban. Pylance avisaba que anotar así el retorno de un
  `@asynccontextmanager` quedó obsoleto: el decorador espera un generador
  asíncrono. Verificado abriendo y cerrando el `lifespan` de los siete, no sólo
  que importen.

**Nota del orden:** la plantilla se publicó antes del deploy de INGEST. No rompe
nada porque el validador corre en modo `strict='filter'` y descarta las columnas
que no conoce; hasta que INGEST esté desplegado, un archivo con crédito y stock
cargará sus ventas y **ignorará en silencio** esas dos hojas.

**El portal no se publicó a propósito.** Sin el backend nuevo las tres vistas
nuevas mostrarían su nota de vacío. En cuanto despliegues, publico y verifico
contra lo local.

**Antes — 9 de septiembre de 2026, barrido de configuración en seis servicios.**

Se auditaron AI, QUOTES, INGEST, ANALYTICS, OPTIMIZATION y MINING_ANALYSIS con
el agente `auditor-hardcode`, y se corrigió todo lo que el barrido encontró.

1. **Dos inconsistencias que no se veían.** `HISTORY_DEFAULT_LIMIT` existía,
   estaba en el `.env` y era requerida, pero la ruta de INGEST y el listado
   escribían `20` a mano; en QUOTES, el banco de modelos redondeaba a `4`
   decimales literales mientras el resto del archivo respetaba `RATE_DECIMALS`.
   Cambiar el `.env` dejaba el sistema en dos estados a la vez.
2. **Se eliminó el patrón `ENV_VARS['X'] or valor`** de INGEST y QUOTES. En
   `bcb_source.py` el respaldo era además código muerto: la variable ya estaba
   declarada como requerida, así que el `or` nunca se ejecutaba.
3. **ANALYTICS: se retiró el mecanismo `setting()`.** Veintisiete perillas del
   servicio —umbrales de concentración, cartera, márgenes, segmentación,
   eficiencia y afinidad— se leían con un valor por defecto en el código, y
   quince de ellas ni siquiera figuraban en el `.env`: corrían con números que
   nadie había elegido. Ahora son requeridas y están todas configuradas.
4. **Parámetros del modelo de pronóstico al `.env`** en ANALYTICS (ventana del
   promedio móvil, techo del horizonte, categorías del gráfico) y en
   MINING_ANALYSIS (suelo de colapso, decimales publicados, horizonte por
   defecto).
5. **Regalías del Ministerio:** el tipo de cambio `6.96`, el piso de
   recaudación de Bs 5.000, la caída crítica del -20% y las filas de cada KPI
   dejaron de ser literales.

**Lo que se dejó a propósito:** el campo `dist` de OPTIMIZATION —está muerto por
contrato, corresponde borrarlo, no parametrizarlo—, las palabras excluidas del
ETL de regalías —una lista con comas no puede vivir en el `.env`— y el
`limit = 2` de `latest_prices_before`, que es la aritmética de una variación
diaria, no una decisión.

**Verificado:** 248 tests en verde y Pylint 10.00 en los seis servicios.
**Pendiente:** los seis necesitan redespliegue de backend. Las variables nuevas
sólo llegan al Lambda a través del `.env`, que `build_and_deploy.sh` vuelca
entero en `--environment Variables={...}`.

**Antes — 8 de septiembre de 2026, tras la primera reunión con clientes.**

1. **Plantilla de ventas restaurada.** Daba 503: al limpiar duplicados en S3 se
   borró `ingest/templates/template_ventas_v1.xlsx`. Ahora se **genera desde el
   contrato** (`tools/build_sales_template.py`), así no puede divergir del
   validador. Verificado: pasa su propia validación.
2. **Banco de modelos en Cotizaciones.** Nueve modelos —ingenuo, promedio,
   deriva, lineal, promedio móvil, suavizado simple, Holt, tendencia amortiguada
   y Theta— que se activan y se acumulan en el mismo gráfico, cada uno con su
   error medido por backtest y su veredicto contra el ingenuo. Sin ARIMA a
   propósito: con 70 observaciones no hay con qué estimar sus órdenes, y un
   modelo vendido como sofisticado que pierde contra "mañana es igual que hoy"
   es un pasivo frente a un cliente.
   *Resultado a 7 días la amortiguada gana; a 30 pierde contra el ingenuo. Eso
   se ve en pantalla, no se esconde.*
3. **Gráfico de productos legible:** los nombres largos se encimaban. Fuente
   menor, ancho de eje fijo, nombres cortados con el completo en el tooltip.
4. **Pronóstico comercial comparado:** ahora trae los dos métodos y los dibuja
   juntos. Donde se separan es donde la proyección deja de ser sólida.
5. **Segmentación a 10 filas**, para que la tabla quepa sin desplazar.

**Decidido:** ML_FUNCTIONS se mantiene desplegado (no representa costo); los
cuadernos de capacitación se harán sólo si hacen falta.

**Antes — semana del 1 al 7 de septiembre de 2026.**

1. **Cotizaciones y proyecciones** completo: cotización oficial con su cadena de
   quincenas, tipo de cambio con vigencia de fin de semana, escenario de venta.
2. **Modelo predictivo reemplazado** tras las preguntas de un economista: el
   ajuste lineal era el peor de cuatro alternativas medidas. Las cifras
   publicadas cambiaron mucho — el dólar de +8,96% a +1,57% a 30 días.
3. **Aislamiento por cliente** cerrado en los tres servicios, incluida una
   colisión en OPTIMIZATION que **borraba** datos entre clientes.
4. **Historial propio y panel "Tu actividad"** en el portal, con dos endpoints
   de listado que no existían.
5. **Captura automática del dólar**: regla de EventBridge diaria a las 13:00 UTC.
6. **Control de duplicados en la carga**: el mismo archivo ya no crea un dataset
   nuevo. Se limpiaron las 46 copias acumuladas.
7. **Capa de IA** construida y desplegada: 9 vistas, roles versionados en tabla,
   caché con TTL. Corrigió dos errores del modelo con reglas explícitas (contar
   de más, inferir el día de la semana).
8. **bearsoft.com.bo reescrita** como sitio de la empresa y no como portafolio
   personal.
