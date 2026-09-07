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
| 📥 INGEST | Plantilla, parseo, validación y normalización del archivo | Lambda 1024 MB / 30 s |
| 📊 ANALYTICS | Resumen, afinidad, pronóstico, segmentación, crecimiento, concentración, eficiencia, margen, cartera | Lambda 2048 MB / 120 s |
| 🗺️ OPTIMIZATION | Días de visita por proximidad y orden de paradas | Lambda 256 MB / 30 s |
| ⛏️ MINING_ANALYSIS | Cotización oficial de minerales, proyección, boletín PDF/PNG del Ministerio | Lambda 1024 MB · persistencia conmutable SQL/DynamoDB |
| 💵 QUOTES | Tipo de cambio oficial del BCB, proyección y escenario de venta | Lambda 256 MB |
| 🧠 AI | Capa de interpretación: convierte la respuesta de cualquier servicio en una explicación | Lambda 512 MB · Bedrock |

**ML_FUNCTIONS** (regresión, gradiente, Z-score) sigue desplegado pero **ningún
servicio lo consume**: su único cliente era el Playground, que se retiró del
portal. Se reubicará como demo de la línea de capacitación en `bearsoft.com.bo`.

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
| Cotizaciones y proyecciones | ¿A qué precio está el mineral y el dólar, y conviene vender hoy o esperar? | ✅ |
| Interpretación (IA) | ¿Qué significa esto? — sobre cualquiera de las pantallas anteriores | ✅ backend, falta encender en el portal |
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

**Semana del 1 al 7 de septiembre de 2026.**

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
