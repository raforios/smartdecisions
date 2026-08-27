# SMARTDECISIONS.md — Plataforma de Inteligencia Comercial (SaaS)

> Documento de visión y estado real del producto. Es la fuente de verdad sobre
> **qué es SmartDecisions, para quién es y qué está construido de verdad**.
>
> USO: en la terminal, indícale a Claude "lee SMARTDECISIONS.md" para cargar el contexto.
> Complementos: `CLAUDE.md` (estándares de código), `POC_PROGRESS.md` (bitácora),
> `POC_EVALUATION.md` (cómo probarlo).
>
> **Última revisión: 2026-08-27** — reescrito tras el giro a MVP vendible.
>
> ⚠️ NOMBRE: empresa **BearSoft**; producto / API / SaaS **SmartDecisions**.
> SmartBear fue descartado. "TRADE" y "FORMS" NO son parte de SmartDecisions:
> son módulos exclusivos del cliente **Binaria** y viven en este monorepo solo
> por conveniencia. Igual "SUPPLIES", "CMS", "MINING_SUMMIT".
> Nota de marca: "Smart Decisions" es una combinación genérica en inglés; el
> dominio y la defensa legal exactos podrían ser difíciles. Verificar antes de
> un lanzamiento público.

---

## 1. Qué es (en una frase)

Plataforma SaaS que convierte **un archivo de ventas** en decisiones comerciales
accionables: qué ofrecer a cada cliente, cuánto se va a vender, a quién estás por
perder, cuánto ganas de verdad y en qué orden recorrer la ruta — **sin ERP, sin
instalación y sin proyecto de integración**.

**Concepto diferenciador del motor comercial:**
```
Afinidad × Drop Size = Oportunidad Comercial Real
```

**Tesis de coherencia (lo que hace que sea un producto y no tres herramientas):**
una sola carga de ventas alimenta todos los módulos. El mismo archivo que produce
el dashboard comercial produce el pronóstico, la segmentación, el análisis de
rentabilidad y el mapa de rutas. Si un módulo necesita que el usuario cargue
datos aparte, ese módulo está mal diseñado.

---

## 2. Restricciones REALES del proyecto

- **Presupuesto acotado.** Sin RDS. Todo nuevo va a DynamoDB + Lambda + S3/CloudFront.
  Cada decisión técnica debe justificar su costo.
- **Equipo:** medio tiempo. Mantener el alcance realista.
- **Lambda: 250 MB sin comprimir.** Restricción dura que ya eliminó `mlxtend`,
  `osmnx`, `networkx` y `scikit-learn` del stack (ver §6).
- **API Gateway: 29 s de timeout, 10 MB de payload.** Ambos límites ya nos
  golpearon en producción; las soluciones están en §5.
- **Mercado objetivo:** gerencias comerciales de distribuidoras y empresas de
  consumo masivo en Bolivia; y, como segundo vertical, mineras y comercializadoras
  (módulo de cotizaciones, §4).

---

## 3. Qué responde el producto (módulos)

Cada módulo es una pregunta de negocio, no un algoritmo. **El usuario nunca lee
"regresión logística"; lee la pregunta que le importa.**

| Módulo | Pregunta que responde | Estado |
|---|---|---|
| **Resumen Comercial** | ¿Cómo vamos? ¿Crece? ¿De quién dependemos? ¿Cuánto ganamos? | ✅ Backend |
| **Oportunidades** | ¿Qué le ofrezco a cada cliente y cuánto vale? | ✅ Completo |
| **Pronóstico** | ¿Cuánto voy a vender los próximos meses? | ✅ Completo |
| **Segmentación** | ¿Quiénes son mis clientes valiosos? | ✅ Completo |
| **Salud de Cartera** | ¿A quién estoy por perder? | ✅ Backend |
| **Rutas** | ¿En qué orden visito y qué le llevo a cada uno? | 🔨 En reforma |
| **Predicciones** | ¿Qué cliente va a dejar de comprarme? | 📋 Planificado |
| **Cotizaciones** | ¿Cómo se movió el precio del mineral? | 📋 Planificado |

**Decisión (2026-08-26): el módulo "Playground ML" se retira.** Exponía las
tripas de una implementación de descenso de gradiente (pestañas "Z-Score sobre
una matriz", "Sigmoid en batch") — un laboratorio de curso, no un producto.
Ninguna gerencia lo va a usar. `ml_functions` sobrevive como **motor de cálculo**
detrás del módulo "Predicciones", nunca como pantalla.

---

## 4. Arquitectura y servicios REALES

Microservicios Python (FastAPI + Mangum sobre Lambda), Clean Architecture.
Todos validan el header `Authorization` contra AUTH.

### Base (recurrentes, compartidos con todos los productos de BearSoft)

| Servicio | Función | Datos |
|---|---|---|
| 🔐 **AUTH** | JWT, usuarios, login. Token de 30 min. | MySQL |
| 🔔 **EVENTS** | Auditoría y logs de uso | DynamoDB |
| 📁 **FILES** | S3: subida, lectura, borrado, URLs pre-firmadas | S3 |

### SmartDecisions

| Servicio | Función | Notas de infra |
|---|---|---|
| 📥 **INGEST** | Plantilla, parseo, validación y normalización del archivo de ventas | Lambda 1024 MB / 30 s |
| 📊 **ANALYTICS** | Resumen, afinidad, pronóstico, segmentación, crecimiento, concentración, eficiencia, margen, cartera | Lambda 2048 MB / 120 s |
| 🗺️ **OPTIMIZATION** | Orden de visita y proyección sobre red vial | Lambda 256 MB / 30 s |
| 🧠 **ML_FUNCTIONS** | Motor de cálculo (regresión lineal/logística, gradiente, Z-score) | Lambda 256 MB |
| ⛏️ **MINING_ANALYSIS** | Cotizaciones de minerales, regalías, reportes | MySQL. Libre de compromiso tras el cierre con el Ministerio; entra como módulo para otro vertical bajo la misma marca. |

> **LOCALIZATION NO es parte de SmartDecisions.** Es de Binaria. Las rutas de
> SmartDecisions las resuelve OPTIMIZATION. (Los documentos anteriores decían lo
> contrario; era un error.)

### Frontend

`app/portal/demo/` — Vanilla JS, sin build, desplegado en S3 + CloudFront.
`app/frontend/` es el prototipo Streamlit original: **está muerto, no se
mantiene**. Streamlit fue descartado para el SaaS (sin modelo de auth propio, sin
multi-tenant, sin marca).

> Los notebooks `frontend.ipynb` y `routes.ipynb` que citaban las versiones
> anteriores de este documento **ya no existen en el repo**. La referencia viva
> para rutas es `notebooks/rutas_optimizadas.ipynb`.

---

## 5. Contrato de datos (una fila = una línea de venta)

Los encabezados de cara al cliente son **en español familiar**; `column_mapper`
los traduce a los nombres canónicos internos y acepta además los alias típicos de
un export de ERP (`Numero Factura`, `Codigo Sap`, `Cliente ID`, `Unidades`,
`Monto Final`…).

| Columna (plantilla) | Canónico | Oblig. | Para qué sirve |
|---|---|---|---|
| Fecha | `fecha` | Sí | Tendencia, pronóstico, estacionalidad |
| Nro Factura | `id_pedido` | Sí | Agrupa la canasta — **sin esto no hay afinidad** |
| Cliente | `id_punto_venta` / `nombre_pdv` | Sí | Segmentación, cartera |
| Producto | `id_producto` / `nombre_producto` | Sí | Afinidad, ABC |
| Cantidad | `cantidad` | Sí | Drop size |
| Zona | `zona` | No | Análisis por sector |
| Ciudad | `ciudad` | No | Distribución geográfica |
| Vendedor | `vendedor` | No | Productividad de la fuerza de venta |
| Latitud / Longitud | `latitud` / `longitud` | No | **Habilita el módulo de rutas** |
| Categoria | `categoria` | No | Afinidad por categoría, mix, ABC |
| Precio Unitario | `precio_unitario` | No | Valorizar oportunidades en Bs |
| **Costo Unitario** | `costo_unitario` | No | **Habilita margen y rentabilidad** |
| Monto Total | `monto_total` | No | Si falta se calcula cantidad × precio |

**Reglas de diseño del contrato:**

- **Degradación elegante, no ceros.** Si falta una columna opcional, la sección
  correspondiente se declara no disponible y la UI la oculta. Mostrar 0% de
  margen cuando no hay costos es mentir.
- **Aceptación parcial.** Las filas inválidas se apartan en un CSV con su motivo
  y el resto se carga. Solo falla el archivo entero si falta una columna obligatoria.
- **Coordenada 0 = sin dato.** Un ERP rellena el GPS faltante con 0; una lectura
  real siempre trae decimales. Se anula el par completo para que el mapa no se
  vaya al Golfo de Guinea.
- **Fechas: ISO y dd/mm/aaaa.** Se elige el formato que más fechas resuelva.
  Forzar day-first sobre texto ISO hacía que pandas dedujera `%Y-%d-%m` y perdiera
  el 61% de las filas.

**Cómo se sortean los límites de AWS:**

- Archivos grandes suben **directo a S3** con URL pre-firmada de FILES, sin pasar
  por API Gateway (evita el 413 de 10 MB).
- La ingesta es **síncrona**: 120k filas se parsean en menos de 1 s; lo lento es
  la subida del navegador a S3, que no cuenta para el timeout del endpoint.
- ANALYTICS corre con 2048 MB porque con 256 MB la afinidad excedía los 29 s.
- El resultado de un run se recorta a los mejores por producto: 18.851
  oportunidades no caben en un ítem de DynamoDB (400 KB).

> Regla de arquitectura: **el motor de análisis es uno solo.** Excel, CSV y una
> futura integración con ERP son adaptadores de ingesta intercambiables. La
> normalización ocurre una sola vez, en INGEST, y todos los consumidores leen las
> columnas canónicas.

---

## 6. Stack tecnológico

- **Lenguaje:** Python 3.14. **API:** FastAPI + Pydantic V2 + Mangum.
- **Datos:** pandas, numpy. **Validación:** pandera + Pydantic.
- **Persistencia:** DynamoDB (vía boto3) y S3. MySQL solo en servicios heredados.
- **Frontend:** Vanilla JS + Chart.js + Leaflet, por CDN. Sin build.
- **Tests:** pytest. **Calidad:** Pylint 10.00/10 por servicio.

**Librerías descartadas y por qué** (no reintroducir sin releer esto):

| Librería | Motivo |
|---|---|
| `mlxtend` | Arrastra scikit-learn + scipy + matplotlib. Apriori reimplementado en pandas puro en `affinity_engine.py`. |
| `osmnx`, `networkx` | Arrastran geopandas, shapely, fiona, pyproj, rtree. Reemplazados por la API de OSRM vía `requests`. |
| `Prophet`, `statsmodels` | Peso desproporcionado para el valor: el pronóstico usa `numpy.polyfit` y media móvil. |
| `folium` | Genera HTML estático; es un artefacto de notebook, no una UI web. Se usa Leaflet. |
| `OR-Tools` | Innecesario a esta escala: vecino más cercano + 2-opt resuelve rutas de decenas de paradas. |
| `Streamlit` | Sin auth propia, sin multi-tenant, sin marca. Callejón sin salida para un SaaS. |

**OSRM** (Open Source Routing Machine) traduce coordenadas a rutas por calles
reales. Hoy usamos el servidor público de demostración
(`router.project-osrm.org`), que tiene límite de tasa y sus dueños piden no usar
en producción. Mitigación inmediata: una sola llamada a `/table` en vez de N
llamadas por tramo. Si un cliente real lo usa a diario, se levanta un OSRM propio
en contenedor.

---

## 7. Datos de prueba y demo

`tools/build_sample_dataset.py` genera los archivos de muestra a partir del export
real de un distribuidor. **Muestrea por cliente, nunca por fila** — un muestreo
aleatorio de filas rompe las canastas y la afinidad deja de encontrar reglas.

| Archivo | Filas | Período | Uso |
|---|---|---|---|
| `tools/samples/ventas_muestra_2k.xlsx` | ~2.000 | 3 meses | Fixture rápido de pruebas |
| `tools/samples/ventas_demo.xlsx` | ~23.000 | 24 meses | Demo de venta |

Ambos traen `Costo Unitario`, geo limpia al 100% y una hoja **"Origen de los
datos"** que declara qué es real y qué es simulado. Esa hoja no es decorativa: el
costo unitario y el historial anterior a nov-2023 son sintéticos, y el archivo se
entrega a prospectos.

**Limitaciones honestas del dato base:** el export real cubre solo 4 meses, una
sola ciudad, una sola región y un solo canal, y su último mes está incompleto.
Por eso el archivo de demo recorta el mes parcial y extiende el historial hacia
atrás con tendencia, estacionalidad y ruido.

---

## 8. Principios de trabajo

- **Coherencia primero:** un módulo que pide datos aparte del archivo de ventas
  está mal diseñado. La coherencia entre módulos es el producto.
- **Preguntas de negocio, no algoritmos:** la UI habla el idioma de una gerencia.
- **Degradación elegante:** si falta un dato, se oculta la sección; nunca se
  muestran ceros que se leen como hechos.
- **Honestidad del dato:** todo número simulado se declara como tal.
- **Costo consciente:** verificar el peso de cada dependencia contra los 250 MB.
- **Partir de lo que existe:** reutilizar AUTH, EVENTS, FILES, ML_FUNCTIONS.
- **Output accionable** (oportunidad en Bs), no solo métricas.
- **Español neutro, sin voseo**, en toda la UI y documentación de cara al cliente.
- **Verificar en el repo antes de afirmar.** Buena parte de lo que este documento
  decía antes era falso porque se escribió desde un plan y no desde el código.
