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
| 🔐 AUTH | JWT, usuarios, login. Token de 30 min. | MySQL |
| 🔔 EVENTS | Auditoría y logs de uso | DynamoDB |
| 📁 FILES | S3: subida, lectura, borrado, URLs pre-firmadas | S3 |

**SmartDecisions:**

| Servicio | Función | Infra |
|---|---|---|
| 📥 INGEST | Plantilla, parseo, validación y normalización del archivo | Lambda 1024 MB / 30 s |
| 📊 ANALYTICS | Resumen, afinidad, pronóstico, segmentación, crecimiento, concentración, eficiencia, margen, cartera | Lambda 2048 MB / 120 s |
| 🗺️ OPTIMIZATION | Días de visita por proximidad y orden de paradas | Lambda 256 MB / 30 s |
| 🧠 ML_FUNCTIONS | Motor de cálculo (regresión, gradiente, Z-score) | Lambda 256 MB |
| ⛏️ MINING_ANALYSIS | Cotizaciones de minerales, regalías, reportes | MySQL |

> **LOCALIZATION no es parte de SmartDecisions** — es de Binaria. Las rutas las
> resuelve OPTIMIZATION.

**Frontend:** `portal/demo/` — Vanilla JS, sin build, S3 + CloudFront.
`app/frontend/` es el prototipo Streamlit original: **está muerto**.

### 2.2 Módulos del producto

Cada módulo es una pregunta de negocio, no un algoritmo. *El usuario nunca lee
"regresión logística"; lee la pregunta que le importa.*

| Módulo | Pregunta que responde | Estado |
|---|---|---|
| Resumen Comercial | ¿Cómo vamos? ¿Crece? ¿De quién dependemos? ¿Cuánto ganamos? | ✅ |
| Oportunidades | ¿Qué le ofrezco a cada cliente y cuánto vale? | ✅ |
| Pronóstico | ¿Cuánto voy a vender los próximos meses? | ✅ |
| Segmentación | ¿Quiénes son mis clientes valiosos? | ✅ |
| Salud de Cartera | ¿A quién estoy por perder? | ✅ |
| Rutas de visita | ¿En qué orden visito y qué le llevo a cada uno? | ✅ |
| Predicciones | ¿Qué cliente va a dejar de comprarme? | 📋 |
| Cotizaciones | ¿Cómo se movió el precio del mineral? | 📋 |

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

| Columna (plantilla) | Canónico | Oblig. | Para qué sirve |
|---|---|---|---|
| Fecha | `fecha` | Sí | Tendencia, pronóstico, estacionalidad |
| Nro Factura | `id_pedido` | Sí | Agrupa la canasta — **sin esto no hay afinidad** |
| Cliente | `id_punto_venta` / `nombre_pdv` | Sí | Segmentación, cartera |
| Producto | `id_producto` / `nombre_producto` | Sí | Afinidad, ABC |
| Cantidad | `cantidad` | Sí | Drop size |
| Zona / Ciudad | `zona` / `ciudad` | No | Análisis por sector |
| Vendedor | `vendedor` | No | Productividad de la fuerza de venta |
| Latitud / Longitud | `latitud` / `longitud` | No | **Habilita el módulo de rutas** |
| Categoria | `categoria` | No | Afinidad por categoría, mix, ABC |
| Precio Unitario | `precio_unitario` | No | Valorizar oportunidades en Bs |
| **Costo Unitario** | `costo_unitario` | No | **Habilita margen y rentabilidad** |
| Monto Total | `monto_total` | No | Si falta, se calcula cantidad × precio |

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

## 6. Bitácora por fechas

### Jun 2026 — POC
Marca cerrada (SmartBear → SmartDecisions, BearSoft como empresa). Contrato Excel
+ validador. Motor afinidad × drop size. Frontend demo en S3+CloudFront con tres
módulos (Excel, Playground ML, Rutas). Datos sintéticos y guion de demo.
*Se cerró contra el plan, pero no era un MVP: Playground no tenía propósito
comercial, Rutas no cargaba el mapa y los módulos no compartían datos.*

### Jul 2026 — reforma hacia MVP
Plantilla v2 con encabezados en español. Ingesta de archivos grandes (subida
directa a S3, luego síncrona tras romperse el auto-invoke del Lambda). Dashboard
comercial. Pronóstico. Segmentación. Afinidad a nivel **categoría** (a nivel SKU
las canastas reales son demasiado dispersas: 0 reglas). Memoria de analytics a
2048 MB tras un 503 por timeout.

### Ago 10 — pausa
Se congela SmartDecisions para cerrar SUPPLIES. Quedan escritos cinco motores
(growth, concentration, efficiency, portfolio, date_filter) **sin cablear**.

### Ago 26 — Fase A: cimiento de datos
`tools/build_sample_dataset.py`. `costo_unitario` en mapper, validador y
plantilla. `_sanitize_geo`. Bug encontrado: el mismo contenido cargaba 23.250
filas en XLSX y **9.064 en CSV** — `dayfirst=True` hacía que pandas dedujera
`%Y-%d-%m` y perdiera toda fecha posterior al día 12 (61% de las filas).

### Ago 27 — Fase B: rentabilidad y KPIs
`margin_engine` nuevo. Los cinco motores muertos, cableados. `date_from`/`date_to`
en los cinco endpoints. `GET /portfolio/{id}`. Frontend: barra de período, cuatro
bloques nuevos en el Resumen, tarjeta Salud de Cartera. Bugs de front que solo
aparecen renderizando: `auto-fill` comprimía gráficos, Chart.js medía canvas
ocultos (0×0), separador decimal mixto, eje Y sin anclar en cero.
**Backend desplegado por Rafael** (`d905c55`, `c2bdbbf`).

### Ago 29 — corrección de deuda: INGEST (incompleta)
Se consolidó la documentación en este único archivo (de 4 archivos y 1.586 líneas
a uno solo). En INGEST: los fallos de validación pasan de frases a **códigos**
(`ValidationRule`); las tuplas de retorno pasan a **dataclasses tipadas**
(`ValidationResult`, `ParseResult`); `_summarize` devuelve `IngestSummary`.

**Dos errores propios en la misma entrega:** creé `download_labels.py` con frases
en castellano dentro del código —rechazado, el texto va en un catálogo de
recursos, no en `.py`— y dejé valores mágicos en el controller después de haber
afirmado que ya no quedaban hardcodeos. Ambos quedan como primera tarea al
retomar.

### Ago 28 — datos realistas, Rutas y auditoría
- **Ciclos de vida de cliente** en el generador (altas, bajas, dormidos que
  vuelven, tendencia propia). Calibrado contra el 82% de retención real.
- **"En riesgo" separado de "perdido"**: de 103 clientes indistintos a 25
  accionables + 22 para reactivación.
- **Rutas reescrita**: `GET /v1/optimization/plan/{dataset_id}`. Se abandonan
  `route_id`/`day`. k-means propio + balanceo + 2-opt + OSRM en una llamada.
  Bugs: el 2-opt optimizaba un ciclo cerrado siendo la ruta un camino abierto;
  k-means daba días de 8 y 97 paradas; y **`[hidden]` no funciona si el CSS fija
  `display`** — ese overlay era la causa real del "mapa en modo carga".
- **Auditoría de constitución** (§6.2): se encontró deuda sistemática.

---

## 7. Estado actual

### 7.1 Desplegado
- Backend en producción desde el 27-ago.
- **Frontend sin desplegar**: se despliega todo junto al final, con la web de
  BearSoft.

### 7.2 Deuda técnica — PRIORIDAD MÁXIMA

Auditoría del 2026-08-28. Tres reglas de la constitución rotas de forma
sistemática en los tres servicios.

**a) Se devuelven `dict` en vez de DTOs Pydantic.** 13 funciones `build_*`
devuelven `Dict[str, Any]` y el controller hace `Model(**dict)`. La validación
queda recién en el borde: una clave mal escrita revienta en runtime. Pasó tres
veces en una sola sesión.

**b) Textos de UI dentro del backend.** 72 literales en castellano en los motores,
más los mensajes de validación de INGEST. No es solo estilo: si el backend fija
`motivo: 'No compra hace 57 días.'`, la futura capa de IA recibe prosa cocinada en
vez de hechos. El contrato correcto es `reason_code: 'SILENT'` +
`silence_days: 57`, y el texto lo compone el frontend.
*Excepción legítima:* lo que se escribe **dentro del Excel que descarga el
cliente** (encabezados e instrucciones) es **dato**, y va en castellano.

| archivo | literales | | archivo | literales |
|---|---|---|---|---|
| portfolio_engine | 18 | | commercial_summary | 11 |
| growth_engine | 12 | | margin_engine | 9 |
| efficiency_engine | 8 | | concentration / route_planner | 4 / 4 |
| forecast_engine | 3 | | affinity / segmentation | 2 / 1 |

**INGEST** (2026-08-29). El backend no devuelve ni escribe texto:

- **Códigos, no prosa.** `ValidationRule` para las filas e `IngestError` para las
  peticiones rechazadas (`UNSUPPORTED_FILE_FORMAT`, `EMPTY_UPLOAD`,
  `FILES_SERVICE_UNREACHABLE`, `FILES_SERVICE_REJECTED_UPLOAD`). El archivo de
  filas rechazadas lleva la columna `rule_codes` con `columna=CODIGO`, no frases.
- **Quién pone las palabras.** El frontend o la capa de IA. `portal/demo/js/api.js`
  expone `error.code` y `excel.js` tiene el catálogo de frases.
- **Sin valores mágicos.** `MAX_ISSUES_ON_RESPONSE` y `CSV_CONTENT_TYPE` se leen
  con `load_and_validate_env_vars` en el módulo que los usa, como `s3_storage.py`
  o `datasets.py`. El fallback queda en código porque `.env` no viaja al Lambda.
- **Descartado:** `download_labels.py`, `services/settings.py` y la carpeta
  `locales/` con su lector. Los tres fueron invenciones mías, no pedidas.
  **No se crean carpetas nuevas en un microservicio sin pedido expreso de Rafael.**
- **Plantilla estática en S3.** `template_builder.py` eliminado. `GET
  /v1/ingest/template/file` lee el `.xlsx` del bucket por defecto con la key
  `TEMPLATE_S3_KEY` (default `ingest/templates/template_ventas_v1.xlsx`) usando
  `download_bytes` de `s3_storage.py`. El warm-up de `main.py` desapareció. El
  formato está definido y lo cumple el cliente; si cambia, cambian lógica y
  reglas de negocio, y el archivo se repone en el bucket.
  **Falta subir el archivo al bucket** — el .xlsx generado quedó guardado; se
  publica cuando Rafael lo indique (primero la lógica, después el archivo).
- **Verificado:** 14/14 tests, Pylint 10.00, la app levanta.

**Aprobado explícitamente:** DataFrames para uso interno (más simple con pandas),
Pydantic en el borde de la API, dataclass para transporte interno con DataFrames,
y los Enums de códigos.

**c) Identificadores en castellano.** Claves `riesgo`/`perdido`, `ultima_compra`,
columnas `monto`/`segmento`/`dia`, y los campos de los schemas.

### 7.3 Plan de corrección

Servicio por servicio, en orden **INGEST → ANALYTICS → OPTIMIZATION**. Cada fase
cierra con tests + Pylint 10.00 + verificación en navegador cuando toca frontend.

| # | Fase | Alcance |
|---|---|---|
| R1 | Schemas primero | DTO Pydantic para cada salida de motor, en `schemas/` |
| R2 | Motores tipados | Los `build_*` devuelven el DTO; se elimina el `**splat` |
| R3 | Texto fuera | Literales → `metric_code` + `value` + `unit` + hechos. Catálogo de etiquetas en el frontend |
| R4 | Inglés | Identificadores **y campos del contrato JSON** |
| R5 | Frontend | Re-cablear los tres módulos y verificar en navegador |
| R6 | Cierre | Suite completa, Pylint, actualizar este documento |

**ANALYTICS — texto fuera (2026-08-29).** Mismo criterio que INGEST:

- `KpiCard` pasa de `label` + `hint` a `metric_code` (Enum `MetricCode`, 25
  códigos) + `value` + `format` + `reference` (el período al que se refiere el
  número, dato y no frase). Los 5 motores emiten códigos.
- `ClientAtRisk.motivo` → `reason_code` (`RiskReason`: LONG_SILENCE, SILENCE,
  PURCHASE_DROP); los hechos (`dias_sin_comprar`, `variacion`) ya viajaban.
- `MarginAlert.motivo` → `reason_code` (`MarginAlertReason`).
- `AbcClass.descripcion` y `ForecastSeries.method_label` eliminados: `clase` y
  `method` ya son códigos.
- `Opportunity.rationale` eliminado; en su lugar `based_on_product_names`, que es
  el único dato que le faltaba al frontend para componer la frase.
- Errores de request como códigos (`AnalyticsError`: INVALID_DATE, NO_DATE_COLUMN,
  EMPTY_PERIOD, DATASET_UNREADABLE).
- `'Sin especificar'` sale del backend: la dimensión vacía viaja vacía y la
  etiqueta la pone la UI.
- Frontend (`excel.js`): catálogos `KPI_LABELS`, `MARGIN_ALERT_REASONS`,
  `ABC_DESCRIPTIONS`, `FORECAST_METHODS`, `ANALYTICS_ERRORS`, `RISK_REASONS` y
  `dimensionLabel`.
- **Verificado:** 51/51 tests, Pylint 10.00, la app levanta.

**Inglés en los tres servicios (2026-08-29).** Identificadores, claves de dicts y
campos del contrato JSON, backend y frontend a la vez:

- **Columnas canónicas:** `id_pedido`→`order_id`, `fecha`→`date`,
  `id_punto_venta`→`pos_id`, `nombre_pdv`→`pos_name`, `monto_total`→`total_amount`,
  `cantidad`→`quantity`, `precio_unitario`→`unit_price`, `costo_unitario`→`unit_cost`,
  `categoria`→`category`, `zona`→`zone`, `vendedor`→`seller`, y el resto.
- **Respuestas de ANALYTICS:** `monto`→`amount`, `mes`→`month`, `variacion`→`change`,
  `en_riesgo`→`at_risk`, `perdidos`→`lost`, `por_categoria`→`by_category`,
  `clase`→`abc_class`, `nombre`→`name`, `periodo`→`period`… más las constantes de
  módulo (`_MONTO`→`_AMOUNT`) y los locales.
- **Tiers:** `Alto/Medio/Bajo` → `HIGH/MEDIUM/LOW`, incluidas las env vars
  `SEGMENTATION_*_TOP_SHARE` y las clases CSS. La palabra en castellano la pone el
  frontend (`TIER_LABELS`).
- **OPTIMIZATION:** `orden`→`stop_order`, `dia`→`day`, `segmento`→`segment`.
- **Frontend:** re-cableado `excel.js` y `routes.js`; el filtro de segmento del
  HTML envía el código y muestra la palabra.

**Lo único en castellano es el archivo modelo.** La plantilla que publicamos, que
el cliente llena siguiendo las instrucciones que la acompañan. `column_mapper`
acepta exactamente esos encabezados y nada más: se eliminaron los alias de ERP
inventados (`Codigo Sap`, `Numero Factura`, `Cliente ID`, `Unidades`…), porque el
formato lo define la plantilla, no una lista de adivinanzas. El bulk de
OPTIMIZATION quedó con encabezados en inglés.

**Verificado:** 80 tests en verde (51 + 14 + 15), Pylint 10.00 en los tres, las
tres apps levantan, y una corrida end-to-end ingest → analytics confirma que el
CSV normalizado encaja con los motores.

### Refactorización estructural (2026-08-30)

Reglas que se aplican ahora y no estaban escritas antes: un archivo por capa con
el nombre del microservicio cuando el servicio es de un solo proceso (patrón de
LOCALIZATION); en `services/` el principal se llama como el servicio y concentra,
y los complementos llevan nombre por funcionalidad; **ningún archivo pasa de 1000
líneas**; los tests se llaman como el módulo que prueban.

**INGEST — hecho.**
- Estructura: `schemas|models|routes|controllers/ingest.py`, `services/ingest.py`
  (dominio, 758) + `services/ingest_utils.py` (Dynamo/S3/FILES), `tests/test_ingest.py`.
  Eliminados `excel_parser`, `excel_validator`, `column_mapper`, `datasets`,
  `s3_storage`, `file_storage` y los tests sueltos.
- **Contrato único:** `SALES_COLUMNS` en `schemas/ingest.py` define nombre
  canónico, encabezado de la plantilla, obligatoriedad y reglas de valor. El
  mapeo de encabezados, el schema de pandera y las listas de obligatorias y
  opcionales se derivan de ahí. Antes lo mismo estaba escrito en cuatro sitios.
- 16 tests, Pylint 10.00, corrida end-to-end con la plantilla real.

**ANALYTICS — hecho.**
- Estructura: `services/analytics.py` (resumen comercial + puerta única del
  dominio, con `__all__`), complementos `affinity.py`, `portfolio.py`, `growth.py`,
  `margin.py`, `efficiency.py`, `concentration.py`, `segmentation.py`,
  `forecast.py`, y `analytics_utils.py` (helpers de frame, filtro de fechas, carga
  del dataset, persistencia de runs). El controller importa solo de `analytics.py`
  y `analytics_utils.py`.
- **DTOs en todas partes:** los ocho `build_*` devuelven su bloque Pydantic
  (`CommercialSummaryBlock`, `PortfolioBlock`, `MarginBlock`…) y cada fila es un
  DTO (`KpiCard`, `RankRow`, `DistRow`, `TrendPoint`, `MarginRow`, `MarginAlert`,
  `PortfolioMovement`, `ClientAtRisk`, `SegmentTier`, `SegmentClient`,
  `PriceDrift`, `SellerProductivity`, `MonthlyChange`, `SeasonIndex`,
  `CategoryMix`, `Opportunity`). Los `Response` heredan de su bloque, así que
  ningún campo se declara dos veces.
- **Umbrales al entorno** con `load_and_validate_env_vars`: los de concentración
  (Pareto, ABC, HHI), eficiencia, estacionalidad y los topes de oportunidades del
  controller. Se eliminaron el `dotenv_values` suelto y los dos lectores de
  configuración caseros que duplicaban el boilerplate.
- **Nivel de concentración como código** (`ConcentrationLevel`), en vez de la
  frase que había en `_hhi_label`. Los nombres de mes en castellano salieron del
  backend: el mes viaja como número.
- Se eliminó el `json_schema_extra` con datos de ejemplo inventados en los
  schemas de ANALYTICS e INGEST.
- 51 tests, Pylint 10.00, respuestas HTTP construidas y verificadas.

**Corregido en los tres servicios:** `security.py` levantaba `UnauthorizedError`
dentro del `try`, donde el `except Exception` lo tragaba y lo reportaba como
error inesperado, ocultando la causa. Ahora sigue el patrón de TRADE.

**OPTIMIZATION — hecho.**
- Estructura: `schemas|models|routes|controllers/optimization.py`,
  `services/optimization.py` (dominio, 737) + `optimization_utils.py` (Dynamo/S3)
  + `route_algorithm.py` (el algoritmo portado del monolito) + `routing.py`
  (OSRM). Tests: `test_optimization.py`, `test_route_algorithm.py`,
  `test_routing.py`.
- **El controller bajó de 573 a 268 líneas.** Salieron de ahí, hacia el dominio,
  el coloreado del mapa, la matriz de distancias, el ordenamiento de la ruta, la
  proyección sobre calles, el parser del CSV de rutas, el filtro por período, el
  listado de vendedores y el armado del día. Y se les puso nombre: `_draw_map`
  → `tag_map_colors`, `_final_data` → `order_route`, `_final_route` →
  `resolve_road_route`, `_parse_csv_text` → `parse_route_csv`.
- **Errores como códigos** (`OptimizationError`: MISSING_COORDINATES,
  NO_GEOCODED_CLIENTS, EMPTY_PERIOD, EMPTY_CSV, INVALID_ROW, INVALID_POINT,
  ROUTING_SERVICE_UNAVAILABLE…). Las frases están en `routes.js`.
- `plan_day` devuelve `RouteStop`, no dicts. `OSRM_BASE_URL` y su timeout pasan
  por `load_and_validate_env_vars`. Corregido el typo heredado `fiter_order_df`.
- 15 tests, Pylint 10.00, plan de rutas verificado sobre la salida real de INGEST.

**Avance:** ✅ INGEST. ✅ ANALYTICS. ✅ OPTIMIZATION. 82 tests, Pylint 10.00 en los
tres, ningún archivo pasa de 1000 líneas (el mayor es `ingest.py` con 758).

### Plantilla y archivos de prueba (2026-08-31)

- **Plantilla publicada** en `s3://ml-data-file-handler/ingest/templates/template_ventas_v1.xlsx`,
  generada desde `SALES_COLUMNS` y verificada: se descarga del bucket y pasa por
  la propia ingesta sin rechazos.
- **Defecto del contrato corregido al generarla:** `Cliente ID` y `Producto ID`
  figuraban obligatorias, pero el servicio las deriva de `Cliente` y `Producto`;
  la plantilla habría exigido códigos que el cliente no tiene. El contrato ahora
  separa `required` (lo que exige el frame validado) de `template_required` (lo
  que el cliente debe llenar) y marca las derivadas con `filled_by_service`.
- **Archivos de prueba regenerados** desde la fuente real
  (`SmartBear/data/DetalleVentas.xlsx`, 121.236 filas × 40 columnas):
  `ventas_demo.xlsx` (22.008 filas, 24 meses) y `ventas_muestra_2k.xlsx` (1.978,
  3 meses). Les faltaban `Region` y `Canal`, así que `by_region` y `by_channel`
  salían vacíos y habrían parecido un bug.
- `tools/build_sample_dataset.py`: deriva los encabezados de `SALES_COLUMNS` (ya
  no repite el contrato ni referencia el desaparecido `template_builder`), lee
  `.xlsx` además de `.csv`, y arrastra `Canal` y `Region`, que la fuente sí trae
  y no se estaban copiando. Fuente por defecto: `../data/DetalleVentas.xlsx`.
- **Dato para la demo:** en la fuente real `Canal`, `Region` y `Ciudad` tienen un
  único valor (DH / Occidente / La Paz), así que esos dos gráficos muestran una
  sola barra. Es fiel al dato; queda decidir si la UI los oculta cuando hay una
  sola categoría.

### Orden de los módulos (decisión de Rafael, 2026-08-31)

Cada vertical es un **módulo distinto** bajo el paraguas SmartDecisions, no un
modo dentro de otro: no se mezclan aunque compartan base. El orden es:

1. Cerrar las pruebas del MVP actual (distribución de consumo masivo).
2. **Minerales** — cotizaciones.

   **Arquitectura acordada (2026-09-02).** `mining_analysis` NO se toca ni se
   vacía: conserva su ETL del Excel del Ministerio, sus boletines y sus regalías,
   porque son la contraparte del intercambio (ellos dan las cotizaciones, nosotros
   los reportes PDF/PNG del Streamlit). SmartDecisions lo **consume como
   microservicio**. Solo las cotizaciones cruzan a SmartDecisions; regalías y el
   resto se quedan sin endpoints hacia afuera.

   **Persistencia conmutable — HECHO para cotizaciones.** `PERSISTENCE_BACKEND`
   en el `.env` elige `sql` (por defecto, sin cambio de comportamiento) o
   `dynamodb`:
   - `models/mining_analysis_dyb.py` — ítems de Dynamo. Claves pensadas por
     patrón de lectura: precios con PK `mineral_id` + SK `date` (ISO), porque
     toda lectura es "este mineral en esta ventana"; el catálogo se resuelve con
     scan, que para nueve filas cuesta menos que mantener un índice.
   - `services/crud_dyb.py` — CRUD boto3, hermano del `crud.py` relacional.
   - `services/prices_store.py` — la capa que usan los servicios. Su interfaz
     habla de negocio ("el promedio de este mineral entre estas fechas"), no de
     SQL, porque **DynamoDB no tiene AVG, COUNT(DISTINCT) ni JOIN**: el backend
     relacional agrega con SQL y el de Dynamo lee la partición y promedia en
     Python. Sin esta capa habría una versión de la misma regla por motor.
   - `_compute_biweekly_average` y `_resolve_mineral_id_map` ya pasan por ahí.
   - 5 tests nuevos, incluido uno de **equivalencia**: ambos motores deben dar
     el mismo promedio para las mismas cotizaciones.

   **Datos disponibles:** 104 días (2026-04-01 → 2026-08-28). Completos para
   Cobre, Estaño, Oro, Plata, Plomo y Zinc; 43 días Antimonio y Bismuto; 22
   Wolfram — en Wolfram hay que declarar baja confianza, no dibujar una línea.

   **Saneamiento de `mining_analysis` (2026-09-03).** Pylint recursivo de
   **9.88 → 10.00**, 56 tests en verde.
   - **El "boilerplate" no era boilerplate.** Cuatro de los ocho archivos
     comunes estaban desactualizados, y ninguna diferencia era mejora propia:
     `security.py` arrastraba el bug del `UnauthorizedError` tragado por el
     `except Exception`; `db_connection.py` tenía el mensaje partido mal
     (`{key\n}.Ensure`), usaba `error_message` en vez de `error_msg` y la
     dependencia en minúscula; `exceptions.py` conservaba docstrings de FORMS.
     Siete de ocho quedaron idénticos a la referencia.
   - **`utils.py` fusionado en ambos sentidos:** entró el `ContextVar` del
     `user_id` por header con su campo en `UsageLogData` y el manejo de
     `datetime.time` (que provocaba un 500 al auditar), y se conservaron el
     truncado de `response_body` a 2000, la guarda de respuesta nula y el
     endpoint de subida condicional. 815 líneas.
   - **El mismo bug de `security.py` estaba en FILES, EVENTS y ML_FUNCTIONS**;
     corregido. Los siete servicios que validan tokens son ahora idénticos.
   - **Funciones partidas:** `clean_currency_pro` (13 ramas) →
     `_normalize_separators`; `get_biweekly_report_service` (22 locales) →
     `_average_with_fallback` + el DTO `_BiweeklyAverage`, y el 24 mágico pasó a
     `_MAX_FALLBACK_PERIODS`; `_iter_daily_rows` → `_row_date` + `_row_prices`;
     `_print_sheet_section` → `_report_columns` + `_report_average_crosscheck`.
   - **`scripts/cli_support.py`**: el andamiaje que los dos scripts repetían
     (sesión, cierre del generador, archivo ausente, log+print) queda escrito
     una vez.
   - Tipos de retorno en los siete endpoints; los seis argumentos del endpoint
     quincenal agrupados en la dependencia `BiweeklyPeriod`.

   **Predictor de precios — HECHO (2026-09-03).**
   `GET /v1/mining-analysis/forecast/prices?days_ahead=30&method=LINEAR`.
   - `services/price_forecast.py`: dos métodos, `LINEAR` (ajuste por mínimos
     cuadrados, por defecto) y `MOVING_AVERAGE` (nivel de los últimos días, sin
     tendencia). Nada más pesado a propósito: con ~100 puntos diarios, un modelo
     con más parámetros daría una curva más convincente sin ser más acertada.
   - **Cada proyección declara su confianza** (HIGH/MEDIUM/LOW/INSUFFICIENT)
     según los días de historia, y **el método que realmente la produjo**.
   - **Defecto encontrado y corregido en la primera corrida real:** Wolfram, con
     22 días de caída pronunciada, proyectaba **0.00 y un −100%** a 30 días. La
     recta ajustada cruzaba el cero y el tope en cero lo maquillaba. Ahora, si la
     proyección lineal cae por debajo del 25% del mínimo observado, se descarta y
     se usa la media móvil, informando el cambio de método. Wolfram pasó de −100%
     a −1.84%.
   - Umbrales al entorno: `FORECAST_MIN_DAYS`, `FORECAST_HIGH/MEDIUM_CONFIDENCE_DAYS`,
     `FORECAST_MOVING_AVERAGE_WINDOW`, `FORECAST_HISTORY_POINTS`.
   - 10 tests propios; 66 en total, Pylint recursivo 10.00, endpoint verificado
     con TestClient contra la base real.

   **Resultado sobre los datos reales (30 días):** Estaño +4.7%, Cobre +1.1%,
   Zinc −1.5%, Plomo −4.2%, Bismuto −7.4%, Oro −14.7%, Plata −25.1%,
   Antimonio −34.5%, Wolfram −1.8% (media móvil).

   **`services/quotes` — construido (2026-09-03).** Microservicio nuevo sobre
   DynamoDB, familia no relacional: los 8 archivos del boilerplate copiados
   **idénticos** a ANALYTICS.
   - `GET /v1/quotes/exchange-rates` — la serie que guardamos.
   - `POST /v1/quotes/exchange-rates/sync` — trae del BCB lo que falte.
   - `services/bcb_source.py` es la **única** pieza frágil: el BCB sirve HTML, no
     JSON. Busca la fila por país + moneda + código ISO, no por posición, y si la
     página cambia de forma **se niega a adivinar** (`SOURCE_UNREADABLE`) en vez
     de guardar un número leído de la celda equivocada. Un tipo de cambio erróneo
     almacenado envenenaría todo escenario construido encima.
   - Tabla `t_exchange_rates`: PK `currency` + SK `date`. Toda lectura es "esta
     moneda en esta ventana".
   - **El quiebre de régimen está en el código, no en un comentario:**
     `FLOAT_REGIME_START` (2026-06-27, configurable). El histórico se sirve desde
     ahí por defecto; los años de 6.86 se piden explícitamente.
   - El sync no re-consulta fechas ya guardadas (el BCB no revisa lo publicado) y
     cuenta aparte las fechas sin publicación.
   - 9 tests, Pylint recursivo 10.00, la app levanta, y el lector verificado
     contra el BCB real: 12.26 (02-sep), 9.73 (27-jun), 6.86 (26-jun).

   **Infraestructura alineada (2026-09-03).** `create_dynamodb_tables.sh` ahora
   admite clave compuesta (`tabla:pk:tipo[:sk:tipo]`), crea todo bajo demanda y
   declara las claves **reales**. Se corrigieron tres desalineaciones que estaban
   ahí desde antes:
   - El script declaraba `ingest_datasets:id`, `analytics_runs:id` y
     `optimization_routes:id`, mientras los `deploy.config` decían `dataset_id`,
     `dataset_id` y `route_day_key`. AWS tiene `id`, `id` y
     `route_day_key`+`client_id`. Un entorno creado desde cero con
     `build_and_deploy.sh` habría nacido con la clave equivocada. Los
     `deploy.config` quedaron alineados con AWS.
   - `ingest_datasets` y `analytics_runs` estaban en capacidad provisionada con
     **5 RCU** (el mismo cuello de botella que sufrió `usage_logs`); pasaron a
     PAY_PER_REQUEST como el resto.
   - Cuatro entradas duplicadas en la lista de tablas, eliminadas.
   - `build_and_deploy.sh` no sabe crear claves compuestas: las dos tablas que
     la tienen se crean con el script y se despliega con `--skip-table-creation`.
     Anotado en sus `deploy.config`.

   **Histórico del dólar cargado:** 69 días, del 27-jun (9.73) al 03-sep (12.32),
   **+26.6%**. Sync verificado como idempotente: la segunda corrida guarda 0.
   Endpoints probados con TestClient contra AWS real.

   **Escenario de venta (cerrado el 2026-09-03).** `POST /v1/quotes/sale-scenario`
   valoriza la misma venta al tipo de cambio de hoy y al proyectado, y devuelve
   la diferencia en bolivianos, que es lo que el vendedor decide. Sobre los 69
   días reales, 100 t a USD 2.500 con el estaño cayendo 3,2%: Bs 3.080.000 hoy
   contra Bs 3.248.471 en 30 días, **+168.471 (+5,47%)** — el dólar sube más de
   lo que el mineral cae.

   Tres decisiones que valen la pena registrar:
   - **`mineral_change_percent` es entrada, no búsqueda.** Viene de la proyección
     de MINING_ANALYSIS. Dejarlo como parámetro permite responder con el supuesto
     que el vendedor quiera probar, incluido ninguno (que valoriza solo el
     movimiento del dólar), y evita acoplar QUOTES a un servicio que además
     todavía no está desplegado.
   - **La proyección se rechaza, no se recorta.** Si la recta cae por debajo de
     la mitad del mínimo observado, `projected` viene en `null` con la confianza
     diciendo por qué. Misma regla que en minerales, donde el Wólfram proyectaba
     0.00 (−100%) porque un `max(value, 0.0)` tapaba el desplome.
   - **`rate_forecast.py` es copia deliberada** de la aritmética de minerales:
     servicios desplegados por separado, la misma razón por la que el boilerplate
     se copia. Lo que no puede divergir es el comportamiento, así que las reglas
     quedaron escritas explícitas en el encabezado.

   **Los umbrales pasaron a `.env`** (`FLOAT_REGIME_START`, `SCENARIO_MAX_DAYS`,
   `SYNC_MAX_DAYS`, los tres `RATE_FORECAST_*`): son hechos del país y del
   criterio, no del código.

   **`tests/test_controllers.py` también en QUOTES.** Era el mismo hueco que
   produjo los 500 en ANALYTICS, INGEST y OPTIMIZATION: dominio en verde y
   endpoint reventado. Verificado rompiendo el controller a propósito — la
   prueba falla. Con `tests/conftest.py` compartiendo el store en memoria,
   **17 tests en verde y Pylint 10.00/10**.

   **`README.md` del servicio**, que no existía.

   **MINING_ANALYSIS quedó desplegable (2026-09-03).** El deploy abortaba porque
   `deploy.config` no declaraba tabla y `build_and_deploy.sh` la exige. Al
   destrabarlo aparecieron tres problemas más, todos previos:
   - **`main.py` creaba el esquema relacional siempre**, y si no alcanzaba la
     base levantaba `RuntimeError`. En Lambda, sin RDS, eso mataba el arranque
     aunque la persistencia fuera DynamoDB. Ahora el `lifespan` saltea la
     verificación cuando corre sobre DynamoDB.
   - **Las tablas no existían en AWS** y los defaults del código apuntaban a
     `t_minerals` / `t_mining_prices`. El prefijo `t_` nombra las tablas MySQL;
     ninguna tabla DynamoDB de la cuenta lo lleva. Creadas como `minerals`
     (`mineral_id`) y `mining_prices` (`mineral_id` + `date`), PAY_PER_REQUEST,
     y los defaults alineados.
   - **La suite seguía a `PERSISTENCE_BACKEND`.** Al poner `dynamodb` en `.env`
     para el deploy, 13 pruebas que arman SQLite se fueron a buscar tablas
     reales en AWS. `tests/conftest.py` ahora fija el camino SQL: una suite no
     puede depender de la configuración de despliegue ni tocar la nube.

   **El paquete pasaba los 250 MB de Lambda** (`Unzipped size must be smaller
   than 262144000 bytes`). No eran las dependencias: era el bytecode que genera
   pip al instalar. El Dockerfile de MINING_ANALYSIS zipeaba todo, mientras que
   los de los servicios que sí despliegan excluyen `__pycache__`. Con la misma
   exclusión el paquete quedó en **185,8 MB, 64 MB de margen**, verificado
   construyendo el zip y midiéndolo, con los binarios x86-64 correctos. De paso
   salieron `kaleido` y `xlsxwriter` de `requirements.txt`: no se importan en
   ningún lado. `xlrd` se queda, el ETL acepta `.xls`.

   **Histórico migrado a DynamoDB (2026-09-03).** 9 minerales y 732
   cotizaciones, del 01-abr al 28-ago. `scripts/migrate_to_dynamodb.py` lee del
   relacional y escribe en Dynamo; es idempotente porque cada escritura es un
   put por clave. La partición es el mismo identificador numérico que expone el
   camino SQL (`str(row.id)`): cualquier otra cosa haría que los dos backends
   discreparan sobre qué mineral es cuál. Verificado leyendo por los dos
   caminos: **fechas y precios idénticos**.

   **Auditoría contra CLAUDE.md (2026-09-03).** Rafael alineó el `Dockerfile` al
   de los otros cuatro servicios: yo había parchado el divergente en vez de
   estandarizarlo, que era lo correcto. Revisando el resto apareció que el
   `.dockerignore` tampoco estaba alineado y **el `.env` viajaba dentro del zip
   del Lambda**, con `SECRET_KEY` y `DB_PASSWORD`. Corregido; el paquete quedó
   en 182,3 MB y verificado que el `.env` ya no viaja.

   También se agregaron los tests de `put_prices_batch` (regla §12, un test por
   función nueva en `services/`) y los dos `logger.warning` de `royalties_etl.py`
   pasaron a usar `error_msg` (§10).

   **`message` convertido a códigos (§7).** MINING_ANALYSIS devolvía frases
   ('Daily report generated.') en 7 respuestas; era el único de los cinco que lo
   hacía. Ahora el campo es `result: MiningResult`, un `Enum` de 8 códigos, y
   `status` dejó de ser un `str` suelto para ser `MiningStatus` (mismo valor en
   el cable: `success`). Los dos textos del ETL que llevaban datos adentro
   ('ETL finished: 12 new records, 3 skipped') se reemplazaron por el código: las
   cifras ya viajaban en `processed_records` y `skipped_records`, donde se leen
   sin parsear prosa.

   Antes de tocarlo se verificó que **ningún consumidor del frontend lee
   `message` ni `status`**, así que el cambio de contrato no rompe nada.
   `tests/test_public_endpoints.py` ahora afirma que las tres respuestas
   públicas traen el código y que `message` ya no existe.

   **Regla de negocio: la cotización OFICIAL de Bolivia (2026-09-03).** Rafael
   corrigió el predictor: lo que la minería usa para liquidar **no es la última
   cotización del día, sino el promedio de la quincena anterior**. La media del
   1 al 15 rige del 16 al 30; la del 16 a fin de mes rige del 1 al 15 del mes
   siguiente. Hoy, con datos hasta el 28-ago, el precio vigente es el promedio
   del 16-31 de agosto y rige del 1 al 15 de septiembre.

   Implementado en `services/price_forecast.py`, reusando `_biweekly_period_bounds`
   y `_prev_biweekly_period` del reporte quincenal para no tener dos versiones de
   la misma regla. La respuesta del pronóstico ahora trae por mineral
   `official_current`, `official_forecast` y `official_change_percent`. Verificado
   contra datos reales: Estaño **25.10138**, idéntico al reporte quincenal y al
   del Streamlit.

   Dos decisiones que hacen que el número signifique algo:
   - **La proyección se lee solo en días hábiles.** De 104 cotizaciones de la
     serie, 104 caen en día hábil. Promediar sobre días calendario pondría un
     denominador de 15 contra uno real de ~10 y bajaría toda cotización oficial
     proyectada.
   - **Lo ya publicado gana sobre lo proyectado.** La quincena en curso se
     promedia mezclando los días reales que ya salieron con los proyectados para
     el resto, y se reporta la composición (`observed_days` / `projected_days`)
     y un `is_complete` cuando el horizonte no cubre toda la ventana.

   En el frontend la tabla pasó a encabezar con **Oficial vigente** y **Próxima
   oficial**, cada una mostrando la quincena que promedia y la que rige; la
   última cotización diaria quedó como columna secundaria. El escenario de venta
   precarga el precio **oficial**, no el diario, y aplica
   `official_change_percent`. **Requiere redesplegar MINING_ANALYSIS.**

   **El plazo seguía sin verse (2026-09-03).** Rafael volvió a reportar que los
   minerales no pasan de 15 días. El backend desplegado sí trae la cadena
   —verificado en su `openapi.json`—, pero yo la había puesto **solo dentro del
   desplegable**, y la columna visible ('Próxima oficial') es por definición la
   quincena en curso, así que a 15, 30 o 60 días mostraba lo mismo. Escondí el
   horizonte detrás de un clic: error de diseño mío, no del servicio.

   Corregido sacándolo a la superficie: columna nueva **'Al final de N días'**
   —la última quincena que alcanza el plazo, la única celda que se mueve al
   cambiarlo—, el encabezado dice el plazo elegido y el resumen del panel dice
   cuántas quincenas alcanza. Cuando el plazo solo llega a una, la celda dice
   'igual que la próxima' en vez de repetir el número.

   **Tabla del dólar día por día.** El panel del dólar tenía solo el gráfico; se
   agregó la serie en números (fecha, día de la semana, Bs por USD, variación
   diaria y acumulada, publicada/proyectada), plegable, con encabezado fijo y
   alto acotado, y un interruptor para incluir o no las proyectadas. Un gráfico
   muestra la forma; una venta se liquida contra una cifra que alguien lee en una
   fila. Las fechas se parsean como fecha local: `new Date('2026-09-03')` se
   interpreta como UTC y al oeste de Greenwich caería un día antes, poniendo cada
   cotización en el día de semana equivocado.

   **Tres consultas de Rafael, resueltas (2026-09-03).**
   1. *"La proyección de minerales nunca pasa de 15 días."* El filtro **sí**
      funcionaba —15 días dan 1 quincena, 30 dan 2, 60 dan 4— pero la tabla solo
      pintaba `official_forecast[0]`, que siempre es la quincena en curso. Se veía
      congelado por mi diseño, no por el backend. **No hay que quitar el filtro:**
      el desplegable de cada mineral ahora muestra la cadena completa (publicadas
      · vigente · proyectadas) y ahí el plazo se ve.
   2. *Los scripts.* Los cinco funcionan y quedaron documentados en el README por
      lo que son: `audit_decimals` + `ingest_pdf_xlsx` + `migrate_to_dynamodb` son
      la **rutina quincenal en orden** (auditar el re-tipeo del PDF, cargar,
      publicar); `cli_support` es andamiaje compartido, no se ejecuta. El único de
      un solo uso ya cumplido era **`backfill_prices`**: borraba `t_mining_prices`
      entero para reparar el bug del `clean_currency_pro`, corregido hace tiempo.
      **Eliminado por decisión de Rafael** el 2026-09-03; queda en git (`81ef57c`)
      si alguna vez hiciera falta. `ingest_pdf_xlsx` reconstruye igual sobre una
      tabla vacía, así que no se perdió ninguna capacidad.
   3. *El Streamlit contra AWS daba `Connection refused` a localhost:3020.*
      `API_BASE_URL` tiene default localhost y hay que exportarla. Pero además
      `/prices` —el endpoint del traceback— era el **último read que quedaba
      solo-SQL**. Se agregó `all_quotations` al store y el endpoint pasó por ahí;
      `id` y `created_at` se hicieron opcionales en los schemas porque en DynamoDB
      no existe un número de fila. Verificado: 732 filas **idénticas** por los dos
      caminos. Ahora contra AWS funcionan todas las lecturas; `POST /etl/upload`
      sigue siendo local, como acordamos en la opción (a).

   **Ajustes a la cotización oficial (2026-09-03, misma sesión).**
   - **Dos decimales, HALF_UP, en el backend.** El servicio devuelve la cifra ya
     redondeada como la publica el boletín, en vez de dejar que la redondee el
     navegador: `toFixed` y las f-strings fallan igual con el medio (12.825 →
     12.82) y la API y el boletín terminarían discrepando sobre el número con el
     que se liquida. Bismuto sale 12.83, correcto.
   - **El promedio ya era por mineral**, sobre los registros que cada uno tenga:
     Estaño 10, Antimonio 4, Wolfram 2 en la misma quincena. Confirmado y
     cubierto con test.
   - **Quincenas anteriores verificables.** `official_history` trae las 6 últimas
     quincenas cerradas (`OFFICIAL_HISTORY_PERIODS` en `.env`) con su promedio,
     cuántos registros lo formaron y qué periodo rigió. En la vista, cada mineral
     se despliega y las muestra. Salta la quincena en vigencia, que ya viaja como
     `official_current` y repetida se leería como dos precios distintos.

   **Versionado automático del portal.** `tools/deploy_demo_portal.py` estampa
   cada `.js`/`.css` con el **hash de su propio contenido** antes de subir, y
   luego sincroniza e invalida. El `?v=` manual era justo el paso que se olvida:
   ahora un archivo que cambia siempre estrena URL y uno que no cambia conserva
   su caché. Aplicado a las 6 páginas del portal, no solo al módulo nuevo.

   **PDF/PNG del boletín: OOM en Lambda (2026-09-03).** Tras el redespliegue los
   endpoints JSON quedaron en 200, pero `/reports/daily/pdf`, `/png` y sus pares
   quincenales devolvían 503/500. CloudWatch fue concluyente:
   `Runtime.OutOfMemory`. Medido localmente: los imports solos ocupan 155 MB y el
   render llega a **437 MB de pico** porque PIL arma la imagen completa en
   memoria. `MEMORY_SIZE` estaba en 256. Subido a **1024**, que es lo que ya usan
   AUTH, FILES, EVENTS e INGEST. **No es una regresión:** el boletín siempre se
   generó contra el backend local; hoy fue la primera vez que corrió en Lambda.

   QUOTES se midió también, por las dudas: 85 MB de pico local, 173 MB reportados
   por Lambda de 256. La proyección suma ~1 MB. **No necesita cambio.**

   **Módulo del frontend: Cotizaciones y proyecciones (2026-09-03).**
   `portal/demo/minerales/`, desplegado. Un solo módulo con tres alcances que el
   usuario elige —solo minerales, solo dólar, o los dos— y un plazo en días
   (1–90) que gobierna todo lo que se ve. El escenario de venta solo aparece con
   los dos activos, porque es la única pregunta donde ambos movimientos se netean.

   Para que el dólar se pudiera proyectar **solo**, hizo falta un endpoint que no
   existía: la proyección del tipo de cambio vivía nada más adentro del escenario
   de venta. Se agregó `GET /v1/quotes/exchange-rates/forecast` con su servicio,
   controller, ruta y 3 tests (QUOTES: 20 tests, Pylint 10.00/10). **Requiere
   redesplegar QUOTES.**

   Decisiones de la vista:
   - **Sin librería de gráficos.** Las tendencias son una línea entre puntos;
     se dibujan como SVG inline. La proyección va punteada y en otro color, para
     que nadie confunda un pronóstico con algo que ya pasó.
   - **El precio unitario del escenario se precarga con `last_price`** del propio
     servicio, no derivándolo de la serie otra vez: una sola fuente de verdad.
   - **Todos los códigos se traducen en el módulo** (`CONFIDENCE_LABELS`,
     `METHOD_LABELS`, `SERVICE_ERRORS`), como en el módulo de rutas.

   **Enganche de la capa de IA, listo y sin UI muerta:** `js/ai.js` expone
   `SD_AI.registerView(id, collect)`; cada panel registra *los datos que está
   mostrando*, así el intérprete nunca tiene que raspar el DOM. El botón
   "¿Qué significa esto?" se monta **solo si `SD_CONFIG.AI_URL` está definida**,
   que hoy no lo está, así que no se publica nada muerto en la demo.

   **La persistencia conmutable estaba a medias (2026-09-03).** El deploy dejó al
   descubierto que solo el promedio quincenal y el catálogo pasaban por
   `prices_store`; el **reporte diario** y los **límites del histórico**
   consultaban SQLAlchemy directo, así que en el Lambda respondían 500
   (`Can't connect to MySQL server on 'localhost'`). Se agregaron al store
   `latest_prices_before` y `date_bounds`, y `query_prices` aprendió a recorrer
   la partición al revés (`ScanIndexForward = False`) porque el diario solo
   quiere las dos últimas cotizaciones. Verificado leyendo por los dos caminos:
   **diario e histórico idénticos**. 74 tests, Pylint 10.00/10.

   Sigue en SQL puro lo que no se usa o es escritura: el ETL, el seed del
   catálogo, `/prices` y las dos consultas de regalías.

   **Flujo quincenal, opción (a) acordada:** el ETL se corre contra MySQL local
   (`PERSISTENCE_BACKEND=sql python main.py`) y después se empuja con
   `migrate_to_dynamodb --yes`. Documentado en el README del servicio. La
   opción (b) —que el ETL escriba por el store, todo en un mismo servicio— queda
   para después de las pruebas, por decisión de Rafael.

   **Corrección a lo que reporté antes:** dije que faltaba dar permiso sobre
   `minerals` porque la política que genera el deploy cubre una sola tabla. El
   rol igual recibe `AmazonDynamoDBFullAccess` del propio `build_and_deploy.sh`,
   así que las dos tablas estaban cubiertas. No hay nada que ajustar en los
   scripts de CI.

   **Deuda a saldar aquí:** `demo/` (Streamlit)
   duplica del microservicio el cálculo del promedio quincenal, el retroceso de
   24 periodos buscando el último dato y todo el renderizado del boletín. Son dos
   implementaciones de la misma regla que hoy coinciden por casualidad. La
   duplicación la introduje yo hace meses; el 2026-08-31 el redondeo del Bismuto
   (12.825 → 12.82) hubo que corregirlo en los dos lados por eso mismo.
3. **Cotización del dólar**, casada a minerales, no como pieza suelta.
4. **Retail** (tiendas, supermercados, almacenes) — módulo nuevo, con su propio
   contrato de datos y sus propias preguntas.

**`services/quotes` (aprobado 2026-09-02, pendiente de construir).** Micro-
servicio nuevo sobre DynamoDB para el dólar: mantiene nuestro propio histórico
porque el dato viene de afuera. Fuente verificada del BCB:
`https://www.bcb.gob.bo/librerias/indicadores/otras/otras_imprimir.php?qdd=DD&qmm=MM&qaa=YYYY`
(también en variantes XLS y ODS). Sirve cualquier fecha, día por día, con el TCO,
~20 monedas y la UFV.

**Aviso para el predictor del dólar:** el 27-jun-2026 hubo quiebre de régimen.
Antes el TCO era fijo en 6.86 durante años; desde entonces flota (9.73 el 27-jun,
11.92 el 30-ago, 12.26 el 2-sep). Entrenar sobre la serie completa daría "seguirá
en 6.86". La serie útil arranca el 27-jun; lo anterior sirve de contexto y para
utilidades históricas, no para proyectar.

**Módulo de IA — intérprete de resultados (idea de Rafael, 2026-09-01).**
Un botón "¿qué es esto?" en cada vista: el usuario lo pulsa, el módulo recibe los
datos de esa vista y los interpreta. Es el destinatario del trabajo de sacar el
texto del backend: el contrato de códigos y hechos existe para alimentarlo.

Criterios a respetar cuando se construya:
- Recibe **el payload JSON del endpoint**, nunca la vista renderizada. Si recibe
  la pantalla, parafrasea frases que el frontend ya compuso en vez de leer datos.
- **No calcula, explica.** Toda cifra de la respuesta sale del payload; el modelo
  aporta sentido, comparación y recomendación. Una cifra inventada frente a un
  cliente cuesta más que no tener el módulo.
- **Bajo demanda**, no en cada carga de pantalla: cada pregunta cuesta tokens y
  latencia.
- Módulo aparte bajo el paraguas SmartDecisions, como el resto de verticales.
- Se envía solo el bloque de la vista consultada, no el payload completo.

*No adelantar trabajo de retail.* Lo que se analizó al respecto: los módulos que
sobreviven sin cliente identificado son Resumen, Crecimiento, ABC, Rentabilidad,
Pronóstico y Oportunidades (la afinidad es incluso más valiosa ahí); los que
necesitan cliente con historial —Segmentación, Cartera y Rutas— no aplican. Eso
es insumo para cuando toque, no una propuesta de mezclarlo con lo actual.

### Fallos encontrados en la revisión del 2026-09-01

Todos introducidos por mí en la refactorización, y **ninguno detectado por los
tests porque no había un solo test de controller**: la suite cubría los motores,
que es justo la capa que no rompí. De ahí los 500 con 55 tests en verde.

| Síntoma | Causa | Corrección |
|---|---|---|
| 500 en summary / portfolio / forecast / segmentation | El controller hacía `**dto` y los motores pasaron a devolver DTOs | `**dto.model_dump()` |
| 500 en el plan de rutas | `build_day` leía `stop['latitude']` sobre un `RouteStop` | Acceso por atributo |
| `VIEW_TO_KIND is not defined` | Un reemplazo masivo borró la constante y dejó sus dos usos | Restaurada |
| Se pierde todo al recargar | Consecuencia del anterior: `restoreLastView()` moría antes de restaurar | Resuelto con lo mismo |
| Campos aún en castellano | `paradas`, `distancia_km`, `duracion_min`, `geometria` en `DayRoute` | A inglés, backend y `routes.js` |
| Playground accesible | Tarjeta viva en `home.html` | Retirada |

**Se agregaron tests de controller en los tres servicios** (`tests/test_controllers.py`),
con dobles para S3 y DynamoDB. Comprobado que fallan contra el código roto: son
regresión real, no decoración. Total: 17 ingest · 55 analytics · 16 optimization.

**Lección para no repetirlo:** un motor verde no dice nada del endpoint. Cada capa
que ensambla una respuesta necesita su prueba, y "tests en verde" no es evidencia
de que algo funcione si no cubren la capa que se tocó.

**Lo que sigue:** Rafael despliega el backend y prueba el frontend en local
(Live Server); tras su aprobación, Claude despliega el frontend. El CORS del
bucket sigue restringido a los puertos 5500/5501 — abrirlo requiere permiso de
escritura sobre infra.

**PUNTO EXACTO DE RETOMADA:** verificar los tres módulos en el navegador contra el
backend desplegado (el deploy del backend lo hace Rafael), y subir la plantilla
`.xlsx` al bucket.

**Decisiones tomadas (2026-08-28):** contrato JSON en inglés · contrato sin texto
(`metric_code`/`value`/`unit`) · capa de IA al final, pero el contrato de R3 debe
alimentarla sin cambios · UI y descargables en castellano hasta que exista el
internacionalizador.

### 7.4 Después de la corrección

1. **Predicciones** (retirar Playground, que sigue publicado y no debería).
2. **Cotizaciones de minerales** (`mining_analysis` como segundo vertical).
3. **Web de BearSoft.**
4. **Exportador `.xlsx`** de resultados — una gerencia siempre lo pide.
5. **Auditoría de solo lectura de TRADE.** Está entregado y cerrado con BINARIA;
   se revisa por responsabilidad profesional, sin apuro, informe antes de tocar
   nada.
6. **Deploy completo** (backend por Rafael con `--platform linux/amd64`,
   frontend por Claude).
7. Más adelante: capa de IA que interprete resultados, e internacionalizador.

---

## 8. Reglas de trabajo

- **Coherencia primero:** un módulo que pide datos aparte del archivo de ventas
  está mal diseñado.
- **Preguntas de negocio, no algoritmos:** la UI habla el idioma de una gerencia.
- **Degradación elegante:** si falta un dato, se oculta la sección; nunca ceros
  que se leen como hechos.
- **Honestidad del dato:** todo número simulado se declara como tal.
- **Umbrales de negocio al `.env`**, no incrustados en el código.
- **Verificar en el repo antes de afirmar.** Buena parte de lo que la versión
  anterior de este documento decía era falso porque se escribió desde un plan y no
  desde el código.
- **Mantener este documento al cerrar cada fase**, no al final de todo. Anotar
  decisiones con su motivo. Si algo queda a medias, dejar escrito el punto exacto
  de retomada.
