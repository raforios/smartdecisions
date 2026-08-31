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
3. **Cotización del dólar**, casada a minerales, no como pieza suelta.
4. **Retail** (tiendas, supermercados, almacenes) — módulo nuevo, con su propio
   contrato de datos y sus propias preguntas.

*No adelantar trabajo de retail.* Lo que se analizó al respecto: los módulos que
sobreviven sin cliente identificado son Resumen, Crecimiento, ABC, Rentabilidad,
Pronóstico y Oportunidades (la afinidad es incluso más valiosa ahí); los que
necesitan cliente con historial —Segmentación, Cartera y Rutas— no aplican. Eso
es insumo para cuando toque, no una propuesta de mezclarlo con lo actual.

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
