# SMARTDECISIONS

> **Documento único del producto:** qué es, cómo está construido, qué está
> **terminado y aprobado**, cuál es el **estado actual** y qué queda
> **pendiente**. Nada más. Se lee primero al abrir una sesión.
>
> Lo que no vive aquí: las reglas técnicas están en `CLAUDE.md` y
> `.claude/rules/`; los procedimientos en `.claude/skills/`; el guion comercial
> en `GUION_DEMO.md`; el contrato de columnas en el código que lo valida.
>
> **Última actualización: 2026-09-27**

---

## Regla de oro

`CLAUDE.md` manda sobre cualquier patrón que se encuentre en el código. **Si el
código existente la contradice, se avisa — no se propaga.** Todo el código de
AI, ANALYTICS, INGEST, MINING_ANALYSIS, OPTIMIZATION y QUOTES lo escribió
Claude: no hay "código heredado" que sirva de excusa.

---

## 1. El producto

**En una frase:** plataforma SaaS que convierte **un archivo de ventas** en
decisiones comerciales accionables —qué ofrecer a cada cliente, cuánto se va a
vender, a quién estás por perder, cuánto ganas de verdad y en qué orden recorrer
la ruta— **sin ERP, sin instalación y sin proyecto de integración**.

**Concepto diferenciador:** `Afinidad × Drop Size = Oportunidad Comercial Real`

**Tesis de coherencia:** una sola carga alimenta todos los módulos. *Si un
módulo necesita que el usuario cargue datos aparte, está mal diseñado.*

**Mercado:** gerencias comerciales de distribuidoras y consumo masivo en
Bolivia. Segundo vertical: mineras y comercializadoras (cotizaciones).

**Marca:** empresa **BearSoft**, producto **SmartDecisions**.

**Idioma:** todo lo que ve el usuario en castellano (UI, reportes, plantilla);
todo el código en inglés, incluidos los campos del contrato JSON.

### Módulos — cada uno es una pregunta de negocio

| Módulo | Pregunta que responde |
|---|---|
| Resumen Comercial | ¿Cómo vamos? ¿Crece? ¿De quién dependemos? ¿Cuánto ganamos? |
| Fuente de volumen | ¿De qué productos y clientes sale la venta? |
| Oportunidades | ¿Qué le ofrezco a cada cliente y cuánto vale? |
| Pronóstico | ¿Cuánto voy a vender los próximos meses? |
| Segmentación | ¿Quiénes son mis clientes valiosos? |
| Salud de Cartera | ¿A quién estoy por perder? |
| Cuentas por cobrar | ¿Cuánto me deben, qué tan vencido, cuánto recupero? |
| Stock del día | ¿Cuántos días me dura, qué está por quebrar, cuánto capital quieto? |
| Rutas | ¿En qué orden visito, dónde está cada vendedor y qué vendió? |
| Cotizaciones | ¿A qué precio se liquida el mineral y el dólar, y hacia dónde va? |
| Interpretación (IA) | ¿Qué significa esto? — sobre cualquiera de las anteriores |

---

## 2. Descripción técnica

Microservicios Python (FastAPI + Mangum sobre Lambda), cinco capas, DynamoDB.
Todos validan `Authorization` contra AUTH. Frontend Vanilla JS sin build en
`portal/demo/`, sobre S3 + CloudFront.

**Base**, compartidos por todos los productos de BearSoft: **AUTH** (JWT,
usuarios, roles, token de 30 min), **EVENTS** (auditoría y logs de uso),
**FILES** (S3).

| Servicio | Función | Infra |
|---|---|---|
| 📥 INGEST | Plantilla, parseo y validación de ventas, cobros, stock y visitas | 1024 MB / 30 s |
| 📊 ANALYTICS | Los nueve análisis comerciales | 2048 MB / 120 s |
| 🗺️ OPTIMIZATION | Planificación de rutas, seguimiento de vendedores, stock del día | 256 MB / 30 s |
| ⛏️ MINING_ANALYSIS | Cotización oficial de minerales, mercado diario, regalías, boletín | 1024 MB · Dynamo + MySQL local |
| 💵 QUOTES | Tipo de cambio del BCB, proyección y escenario de venta | 256 MB |
| 🧠 AI | Convierte la respuesta de cualquier servicio en una explicación | 512 MB · Bedrock |

**ML_FUNCTIONS** es el servicio de capacitación: sigue desplegado y ningún
producto lo consume.

**Qué entra en una revisión general: los once servicios propios**, en cuatro
grupos:

| Grupo | Servicios |
|---|---|
| **SmartDecisions** (6) | INGEST, ANALYTICS, OPTIMIZATION, MINING_ANALYSIS, QUOTES, AI |
| **SmartBilling** (1) | BILLING (antes SUPPLIES) — facturación de comercios, farmacias como primer vertical |
| **Genéricos y obligatorios** (3) | AUTH, EVENTS, FILES — los usa todo producto |
| **Capacitación** (1) | ML_FUNCTIONS — podría pasar a genérico |

**FORMS, LOCALIZATION, TRADE, CMS y MINING_SUMMIT no se tocan** sin pedido
explícito: son de clientes.

**Límites de infraestructura que condicionan el diseño:** Lambda 250 MB sin
comprimir (por eso no hay scikit-learn, osmnx, Prophet ni mlxtend); API Gateway
29 s y 10 MB (los archivos suben directo a S3 con URL pre-firmada); DynamoDB
400 KB por ítem (un run de analytics recorta a los mejores por producto); OSRM
público con límite de tasa (una sola llamada por día).

**Contrato de datos:** la fuente de verdad es el código, no este documento —
`SALES_COLUMNS`, `COLLECTION_COLUMNS`, `STOCK_COLUMNS` y `VISIT_COLUMNS` en
`services/ingest/schemas/ingest.py`, de donde se derivan el mapeador de
encabezados, el esquema del DataFrame y la plantilla publicada. Una fila = una
línea de venta; `Nro Factura` agrupa la canasta (sin eso no hay afinidad);
`Latitud`/`Longitud` habilitan Rutas y `Costo Unitario` habilita margen; cobros,
stock y visitas son hojas opcionales del mismo libro, cargables después.

**Cómo probarlo:** `/verificar-servicio <nombre>` corre la batería completa
(pytest, Pylint 10.00, firmas, type hints, hardcode, tamaño).
`python tools/build_sample_dataset.py --rows 24000 --months 24` regenera
`ventas_demo.xlsx` (22.008 filas, 24 meses, 266 clientes), cuyas cifras
esperadas están en `GUION_DEMO.md`.

---

## 3. Finalizado y aprobado

Desplegado, probado con datos reales y validado por Rafael.

| Pieza | Cuándo |
|---|---|
| AUTH, INGEST, ANALYTICS, QUOTES, AI, OPTIMIZATION en producción | 21-sep |
| Los nueve análisis comerciales, con Cartera y Cuentas por cobrar | 17-sep |
| **RUTAS backend** — plan → ruta → visita → venta → sobreventa → cierre, con geocercas y descuento transaccional de stock (85 tests) | 21-sep |
| **RUTAS frontend gerencia** — Planificar, Planes, Stock del día, En vivo, Comparación | 21-sep |
| **Pantalla del vendedor** — `routes/vendedor.html`, probada desde celular con `vendedor.demo@bearsoft.com.bo` (SELLER) | 22-sep |
| **Usuarios por cliente y roles** — `client` en el JWT, `MANAGER` y `SELLER`, `require_roles` en las seis APIs | 21-sep |
| Portal demo y `bearsoft.com.bo` publicados, con logs de CloudFront | 17-sep |
| Corrección del contrato de error (el `detail` viaja limpio, sin `"409: CODE"`) en los seis servicios, con test de regresión | 20-sep |
| Estandarización de firmas y type hints en los diez servicios, con verificación mecánica | 17-sep |

---

## 4. Estado actual

**MINING_ANALYSIS en producción (22-sep), sin aprobar.** La cotización
anticipada funciona de punta a punta: la regla diaria `cron(0 23 * * ? *)`
corre el sync, que guardó 42 días de 6 minerales y al repetirlo no reescribió
nada; `/market/estimate` devuelve la quincena en curso con las alícuotas del
Art. 227; el panel del portal está publicado. En el camino se corrigió un 500
del botón de sync —el decorador de auditoría leía `.id` sobre un resumen— y se
alineó el servicio al boilerplate estándar de DynamoDB, dejando lo relacional
en `*_sql.py`. 106 tests, ALL PASS.

**BILLING terminado y desplegado (23-sep).** Backend y las seis pantallas de
`portal/billing/` —mostrador, ventas, catálogo con lotes, recepción, tablero y
configuración—, con impresión térmica de 58 y 80 mm. Probado contra el servicio
local con una farmacia sembrada: FEFO tomó el lote que vence en 45 días y no el
más barato, la sobreventa respondió `INSUFFICIENT_STOCK` sin dejar nota ni
avanzar la numeración, y el tablero detectó el lote vencido. 26 tests, ALL PASS.

De la facturación electrónica está **lo que no depende del SIN**: los
algoritmos del CUF y el módulo 11, verificados contra el ejemplo resuelto de la
norma, gzip+base64, el enmascarado de tarjeta que exige la Fase II, y los tres
códigos de homologación en el producto. El anexo técnico completo está en
`docs/siat/`.

**EVENTS cerrado en los siete servicios (23-sep).** Faltaba la auditoría en
cuatro de los seis de SmartDecisions y las dos cosas en BILLING: nadie podía
decir quién cargó un archivo ni quién anuló una nota. Hoy son 37 eventos
declarados. La causa era que la regla nunca se escribió: ahora está en
`CLAUDE.md` §7 y la comprueba el chequeo `events`, que falla el servicio.

**Los once servicios en verde (27-sep).** `verify_service --all` sólo recorría
siete: **AUTH, EVENTS, FILES y ML_FUNCTIONS nunca entraron**, y por eso
acumularon fallas viejas que nadie veía —45 funciones sin type hints, un
`os.getenv` suelto en FILES, `MESSAGE` en vez de `message` en tres `main.py`—.
BILLING tampoco estaba en 10: `CufInput` nació el 23-sep como dataclass de nueve
atributos y Pylint corta en siete. La causa real no era el número sino la capa
—un DTO viviendo en `services/`—, así que pasó a `schemas/` como modelo Pydantic
V2, que Pylint no cuenta, junto con los códigos del catálogo SIAT, que son
contrato. Sin excepciones: la dependencia va `services/` → `schemas/` y nunca al
revés. Hoy los once pasan los doce chequeos. En el camino se
agregó el chequeo **`comment-language`**, que mira comentarios *y docstrings* e
incluye los tests: encontró 28 comentarios y 23 docstrings en castellano que
ninguna revisión anterior había mirado. EVENTS queda exento del chequeo de
auditoría, con la razón escrita: es el servicio al que los decoradores le
escriben, y auditarse a sí mismo no termina nunca.

---

**Maestro de clientes, en INGEST y sólo ahí (27-sep).** Lo que describe al
cliente —nombre, coordenadas, dirección, zona, ciudad, canal, tipo de local,
contacto— dejó de repetirse en cada fila de venta y vive una vez en
`ingest_clients`, con el dueño como partición. Entra por **tres puertas** que
comparten una sola regla —se crea lo que no está, se completan los campos
vacíos, **nunca se sobrescribe**—: el archivo (ventas y visitas, en las dos
rutas de subida), el API del ERP, y el vendedor que da de alta desde la calle
con `POST /v1/ingest/clients/field`, donde las coordenadas son obligatorias
porque las toma parado en la puerta. Cada carga además **completa el archivo
desde el maestro**, así que un ERP que deja de exportar latitud ya no apaga
Rutas. Corregir es un `PATCH` aparte, que es lo único que sobrescribe.
63 tests. En el camino apareció que el camino multipart de subida **no tenía
ningún test**, y por eso una asignación sobre un dataclass congelado habría
llegado a producción; ya está cubierto.

---

**Los dos canales de carga, para los cuatro contratos (28-sep).** Ventas,
cobros, stock y visitas entran ahora por **API JSON** —`POST
/v1/ingest/{dataset_id}/<contrato>/rows`— y por **archivo vía FILES→S3**
—`.../from-s3`—, además del multipart que ya existía. El API no revalida por su
cuenta: cada pipeline se partió en `prepare_rows` y `validate_rows`, así que la
fila que empuja un ERP atraviesa **el mismo validador** que la del archivo y
responde con los mismos códigos.

**El modo de carga es `APPEND` por defecto**, que es lo que significa integrar a
diario. Cada contrato declara qué hace que dos filas sean la misma: la venta es
factura + producto, el cobro es factura + fecha + monto, el stock es producto +
día, la visita es día + vendedor + cliente + hora. Con eso un reintento del ERP
no cuenta dos veces un cobro, y empujar el stock de hoy corrige hoy sin tocar la
semana pasada. `REPLACE` reproduce el comportamiento del archivo. El resumen
describe **todo lo almacenado**; las incidencias, **sólo esa carga**.

Tres defectos reales salieron de escribir las pruebas antes de creer el código:
la mezcla no deduplicaba porque las filas vuelven del CSV como texto y la clave
no comparaba igual; `GET /v1/ingest/clients` devolvía 422 porque
`/v1/ingest/{dataset_id}` lo capturaba primero; y el camino multipart de ventas
no tenía ningún test. 74 tests.

---

**Un archivo por contrato (28-sep).** El libro de cuatro hojas —Ventas, Cobros,
Stock, Visitas— se eliminó. Era invención nuestra, y era la razón de que INGEST
leyera S3 con su propio `boto3`: el lector de FILES devuelve **una tabla plana**,
correctamente, y no podía servir un libro. Ahora hay **cuatro plantillas**
—`plantilla_ventas|cobros|stock|visitas.xlsx`—, cada una con su hoja de datos y
su hoja de instrucciones, derivadas del contrato por
`tools/build_sales_template.py`. El portal elige qué carga; Ventas crea el
conjunto de datos y los otros tres se enganchan a él, así cada módulo se
enciende con su propio archivo en vez de exigir el libro entero.

---

**El patrón FILES para DynamoDB vive en `ingest/services/utils.py` (28-sep).**
Es la contraparte del bloque que `trade/services/utils.py` tiene para MySQL:
`_handle_files_service` con lectura, creación y borrado, `perform_bulk_upload`
con aceptación parcial fila por fila y borrado del archivo consumido, y
`generic_bulk_processor`. Mismos nombres y mismo flujo de dos pasos —el archivo
va primero a S3 por FILES y el endpoint recibe sólo su **nombre**—; lo que
cambia es que no hay `Session` que confirmar. **Es el modelo que copia todo
servicio nuevo que mueva archivos.**

**INGEST pasa por FILES (28-sep).** Ya no tiene cliente de S3 propio: todo lo
que el cliente manda y todo lo que el servicio guarda va por FILES,
**reenviando el token del que llama** para que autorice al usuario real, como
en TRADE. El token viaja de la ruta al controlador y de ahí al servicio, igual
que el `auth_token` de `perform_bulk_upload`. Queda **una** lectura directa y
está escrita como tal: la plantilla estática, porque FILES no devuelve un
archivo *como archivo* —su lector parsea y devuelve filas— y `CLAUDE.md` §9
nombra justo ese caso.

**Tres chequeos nuevos** en `verify_service.py`, uno por cada error que se me
pasó: **`cross-duplicates`** (comparaba sólo dentro de un servicio, por eso un
maestro copiado en dos no lo vio nadie), **`direct-s3`** (sólo FILES toca el
bucket) y **`comment-language`**. Lo que queda pendiente está en listas con
nombre dentro del chequeo, no silenciado: `to_dynamo`/`from_dynamo` y
`get_caller` son boilerplate sin promover, y **ANALYTICS y OPTIMIZATION leen el
dataset de INGEST directo de S3 con dos funciones duplicadas** — migran cuando
se trabaje cada uno, no por simetría.

---

**RUTAS: pasado y futuro separados (28-sep).** La causa de que el histórico se
presentara como plan era que **un plan no tenía fecha**. Ahora `plan_date` está
en el contrato y el filtro acepta una ventana: **Histórico** pregunta hacia
atrás y **Planes** de hoy en adelante. Una ruta sin fecha es una plantilla
reutilizable y no cae en ninguna ventana salvo que se la pida.

Lo demás de la reunión, resuelto:

- **Inferir del día funcionaba mal** porque `visits_as_stops` descartaba toda
  parada sin `client_id`. Justo esas son los clientes nuevos. Se conservan,
  identificadas por su posición, y el plan queda fechado en su día.
- **Geocerca al registrar la visita** (`OUTSIDE_STOP_GEOFENCE`). Sólo valla lo
  que el plan prometió: una ruta sin plan no se juzga, un lugar nuevo pasa
  —es la evidencia de que la ruta debe crecer— y un plan de un día pasado es
  historia cargándose, no una visita haciéndose.
- **Repetir una ruta** en otra fecha, copiando las paradas enteras.
- **Alta de cliente desde la calle** en la pantalla del vendedor, contra
  `POST /v1/ingest/clients/field`: la posición de quien está en la puerta es
  mejor evidencia que cualquier planilla.
- **«En vivo» dibuja el recorrido completo del día** —polilínea y paradas
  numeradas con su hora—, no sólo el último punto. Sin eso la comparación
  parecía vacía.
- **Plantilla de rutas descargable con cabeceras en castellano**; el servicio
  mapea a los nombres del contrato y sigue aceptando los canónicos.

`localization.py` cruzó las 800 líneas y se partió: **`localization_sources.py`**
son los planes que vienen de otro lado —CSV, día trabajado, repetición—.
87 tests.

---

**OPTIMIZATION optimiza de verdad lo que el cliente tiene (28-sep).** El
planificador armaba la semana desde el archivo de ventas, pero **las rutas que
el cliente maneja nunca volvían al optimizador**: no había forma de tomar una
ruta importada, inferida de un día trabajado o armada en la calle y preguntar
en qué orden convenía. `GET /routes/planned/{id}/optimization` la estudia con
el **mismo** `order_stops` —vecino más cercano mejorado con 2-opt— y la misma
proyección OSRM que el planificador, y responde con **los dos órdenes, los dos
medidos y los dos dibujables**: kilómetros, minutos y el porcentaje que se
ahorra. Si la ruta ya estaba en el mejor orden, lo dice — defender una ruta
bien armada vale tanto como mejorarla.

**No escribe nada.** Aceptar es `repeat` con `optimized = true`, que reordena
**en el servicio** contra el mismo estudio, así lo que se crea no puede
desviarse de lo que se mostró; la ruta estudiada queda intacta. En el portal es
el panel **Optimizar**, con los dos mapas lado a lado y la tabla de en qué
posición estaba cada parada.

---

**Variables fluctuantes y lectura en dólares (29-sep).** Lo que se mueve solo
y cambia lo que un reporte significa —el combustible, un arancel, un índice—
vive en **tabla, no en el `.env`**: un número que el cliente lee de una factura
cada semana no puede necesitar un despliegue. Se declara una vez, se carga **a
mano o por API**, y cada lectura trae el día en que fue cierta.

Un factor es **una cifra y si cuenta o no** — nace ACTIVO, y apagarlo es lo
que lo vuelve inerte. Hubo un `weight` multiplicador que inventé y se eliminó:
no significaba nada concreto y duplicaba lo que ACTIVO/INACTIVO ya hacía. Las
**dos cosas que se mueven —valor y estado— guardan su historia fechada al
momento**.

Y de ahí la regla que lo cierra: **un cálculo usa el estado de SU propia
fecha**, no el de hoy. `active_factors_on(día)` y `state_on(día)` son la única
puerta. Un factor puede valer una cosa en marzo, estar apagado en junio y valer
otra en septiembre: el reporte de marzo conserva lo de marzo, los meses
apagados no cuentan, y septiembre usa lo de septiembre. Leer el estado actual
dejaría que un interruptor movido hoy reescriba en silencio toda cifra
producida antes. Un factor responde **inactivo para cualquier día anterior a su
existencia**, y `effective_from` permite declararlo como vigente desde antes —
sin eso, cargar un año de historia dejaría ese año sin peso y sin estado.

**Costo de distribución local.** `GET /v1/quotes/factors/transport-cost`
responde la cadena entera y no sólo el total: **km ÷ rendimiento × precio del
litro**, sobre el **viaje redondo** —el vehículo termina en el último cliente y
vuelve vacío—, y dividido por las unidades da el costo por unidad, que es la
cifra que llega al margen. Se investigó antes de fijarla: la división **es** la
fórmula estándar, y los factores que uno intuye —tráfico, carga, viento, aire
acondicionado— no se aplican como multiplicadores porque **ya están dentro del
rendimiento medido**. Por eso el rendimiento es el **promedio estimado por la
operación en reparto urbano**, que consume cerca del doble que carretera, y no
el del fabricante: se carga como dato, se fecha y se va afinando. Sólo el
*código* del factor vive en el `.env`; el valor nunca.

**`GET /v1/quotes/exchange-rates/at`** da la cotización vigente en un día: la
última publicada en o antes de él —el BCB no publica todos los días— y, antes
del 27-jun-2026, la del régimen fijo, diciéndolo. En ANALYTICS hay **una sola
costura**: todo análisis lee el marco por `_scoped_dataframe`, así que un
reporte en dólares es **una** conversión y no nueve, y **cada importe se
convierte al cambio de su propio día**. Convertir un año entero a un solo tipo
convertiría una devaluación en crecimiento. Las filas anteriores a la primera
cotización publicada **conservan su importe y se reportan como tales**: un
hueco dicho, no una mentira silenciosa. Las cotizaciones se le piden a QUOTES,
que es su dueño; ANALYTICS no lee esa tabla.

---

**Punto de corte: la versión del 23-sep.** Los once servicios quedaron en
producción el miércoles 23-sep entre las 18:29 y las 20:31, y el **24-sep** el
potencial cliente revisó **exactamente eso**. Todas las observaciones de la
reunión —el guion que faltó, la carga diaria, Rutas, el tipo de cambio— son
contra esa versión. Lo que se escriba desde el 27-sep es la respuesta a esa
revisión, no trabajo suelto: cuando algo no funcione, la pregunta es si ya
estaba roto el 23 o lo rompimos ahora.

---

### Cumplimiento contra objetivo (Fase H)

Los dos libros de cierre que trajo Rafael son de **otra empresa** —un
prospecto— y no son datos: son **la lista de lo que quieren ver**. El archivo
`base 2025.xlsx` es de una tercera, que sí tiene el detalle transaccional. Con
los datos de la segunda se reproduce el reporte de la primera, y eso es la
prueba de que el producto puede darlo.

**El objetivo es la única cifra del producto que ningún movimiento implica.**
Es una decisión que se toma antes de que empiece el mes, y por eso entra por
su propio contrato —quinta plantilla, `objetivos`, por las tres puertas:
archivo, API y S3— idempotente por cliente y mes. Un objetivo para un cliente
que nadie facturó se **reporta y se conserva**: es el cliente que la empresa
quiere activar, y esconderlo borraría justo la fila que el gerente busca.

**Un objetivo se mide dos veces**, contra lo facturado y contra lo cobrado.
Un cliente puede cumplir en el papel y deber hasta el último boliviano. El
cobro cuenta en el mes de la **factura que salda**, no en el mes en que
entró: es la única lectura bajo la cual `facturado = cobrado + deuda`, que es
la identidad sobre la que está armado el libro del prospecto.

El motor reproduce ese libro **a cuatro decimales** —0,6733 amarillo; 1,0008
verde; y el caso que justifica todo, un cliente 0,6099 amarillo en facturado
y 0,3364 rojo en pagado—. Los cortes del semáforo y cuántos bolivianos vale
un punto en cada cluster **no son hechos del dato**: van en la política
comercial por propietario, espejo de la de crédito, con default del `.env`.
El producto **no declara ningún nombre de cluster**: son del cliente.

La matriz cruza cluster × semáforo y pesa cada celda sobre el objetivo total,
que es lo que evita que engañe: veinte clientes rojos que valen el 2 % del
objetivo son otra mañana que tres que valen el 40 %.

**El maestro se alimenta en un solo lugar.** `names_clients` de
`CompanionSpec` era un comentario disfrazado de configuración: no lo leía
nadie, y cada puerta alimentaba el maestro con su propia copia de la llamada
a `sync_master` —salvo la de S3, que se olvidaba—. El mismo archivo de
visitas cargado por subida y por clave dejaba dos maestros distintos: el
prospecto que nombraba existía o no según el endpoint usado. Ahora la bandera
se lee en `store_companion`, por donde pasan las tres puertas, y las tres
copias se borraron. Dos tests lo fijan, incluido el de la puerta que fallaba.

## 5. Pendiente

En orden.

0. **Cobertura de endpoints: 63 sin prueba.** `verify_service.py` tiene dos
   chequeos nuevos. `imports` levanta el servicio y arma su esquema de rutas:
   existe porque un `auth_token` duplicado en `routes/ingest.py` era un
   `SyntaxError` y INGEST no importaba, con 83 tests en verde y Pylint 10.00
   —ningún test importaba las rutas—. `endpoint-coverage` cuenta los endpoints
   que ningún test toca; sale como **TODO y no como FAIL**, porque es trabajo
   planificado y no puede frenar una entrega. **Los tres servicios tocados en
   estas fases quedaron completos**: INGEST 26/26, ANALYTICS 14/14, QUOTES
   11/11. Falta lo que no se tocó: OPTIMIZATION 32, BILLING 16,
   MINING_ANALYSIS 10, AI 1. AUTH, EVENTS, FILES y ML_FUNCTIONS estaban
   completos desde antes y no se tocaron.

1. **Desplegar lo de hoy.** Los **once** quedaron en producción el miércoles
   **23-sep entre las 18:29 y las 20:31**, comprobado contra el `LastModified`
   de cada Lambda. Lo del 27-sep —maestro de clientes en INGEST, type hints e
   `os.getenv` de FILES/EVENTS/ML_FUNCTIONS, `CufInput` a `schemas/` en
   BILLING— todavía no está arriba. La tabla `ingest_clients` se crea antes,
   con `create_dynamodb_tables.sh`. Lo del 29-sep se suma: las dos tablas de
   factores (`quotes_factors`, `quotes_factor_values`), sus variables nuevas
   en el `.env`, y el arreglo de identificadores largos en INGEST.

   **El identificador derivado ya no es una copia del nombre.** INGEST deriva
   `pos_id` y `product_id` del nombre porque la plantilla sólo pide 'Cliente'
   y 'Producto', y el contrato los corta en 64 caracteres. Con el archivo real
   de `base 2025.xlsx` eso rechazaba **1290 de 5079 filas —el 25 %—** por
   exceder un límite en una columna que el cliente nunca llenó y no podía
   corregir. Ahora un nombre largo se acorta y se le pega un digest del nombre
   completo; uno que ya entra se deja idéntico, porque es la clave con la que
   se casó el maestro y reescribirla dejaría huérfano lo ya cargado.

   De la Fase H se suma la tabla `analytics_commercial_policies`, las cinco
   variables `OBJECTIVES_*` del `.env` de ANALYTICS, y publicar la quinta
   plantilla con `python -m tools.build_sales_template --yes`.

2. **Documentos de venta (Fase F) — ENTREGADOS.** `GUIA_PRODUCTO.md` describe
   cada módulo, menú y gráfico del portal, derivado de lo que el portal
   realmente tiene, no de memoria. `GUIA_PRUEBA.md` es el HOW TO: cada paso
   dice qué hacer, qué se va a ver y cómo saber que salió bien, con seis
   pruebas deliberadas de los comportamientos que no se creen hasta que se
   ven —la fila rechazada que no tumba el archivo, el objetivo de un cliente
   sin ventas, la geocerca—. Los dos convertidos a `.docx`.

3. **Facturación electrónica: lo que no depende del trámite.** Hecho el
   **29-sep**: `branch` y `point_of_sale` en `BillingSettings` —van DENTRO del
   CUF, así que son parámetros de cada farmacia y no del servicio— y la
   **nominatividad** como `buyer_required`, que rechaza una venta sin nombre y
   documento del comprador. Es una bandera y no una constante a propósito: una
   farmacia que todavía emite notas internas tiene que seguir vendiendo hasta
   que la autoricen, y el día que la autoricen no cambia nada más.

   Los **códigos de método de pago del SIN** quedaron en `SIN_PAYMENT_CODES`:
   efectivo 1, tarjeta 2, y QR viaja como OTROS (5), que es lo que la norma
   manda usar cuando el método no está en su lista. El **número de tarjeta** se
   enmascara **al entrar** —primeros y últimos cuatro dígitos, ceros al medio—
   y sólo la forma enmascarada se guarda: el número completo no llega a la
   tabla, ni al log, ni a la nota impresa, así que no hay copia que se pueda
   filtrar. Un número de tarjeta con un pago que no es tarjeta se rechaza,
   porque el SIN lo reporta como error.

   **Corrección sobre la nominatividad:** el anexo es explícito —«la
   nominatividad hace referencia al número de documento, no al nombre o razón
   social»—. La primera versión exigía los dos, lo que habría rechazado ventas
   que la norma acepta. Ahora exige el documento y el nombre es opcional.

   En el portal: sección «Facturación electrónica» en la configuración
   (sucursal, punto de venta, exigir documento) y en el mostrador el campo de
   tarjeta, que aparece sólo con pago con tarjeta y se limpia al cambiar de
   método.

   **El XML está armado y valida contra el XSD del SIN.**
   `services/billing_invoice_xml.py` lo construye leyendo el orden del propio
   `facturaComputarizadaCompraVenta.xsd`: el esquema declara un `xs:sequence`,
   así que un elemento fuera de lugar invalida el documento aunque todos los
   valores estén bien. La prueba valida contra el XSD real, no contra nuestra
   idea de él, y eso destapó el error a la primera: **`nillable="true"` no
   significa elemento vacío, significa `xsi:nil="true"`** — un
   `<numeroTarjeta />` vacío no es un entero válido. `lxml` agregado a
   `requirements.txt`; no hay equivalente en la biblioteca estándar para
   validar contra XSD.

   Nada se inventa: un producto sin sus tres códigos del SIN (actividad,
   producto, unidad) **no se factura**, se rechaza con `PRODUCT_NOT_HOMOLOGATED`.
   Una factura con un código inventado la rechaza el SIN *después* de que el
   papel ya está en manos del cliente. Los importes van con dos decimales
   exactos, redondeados half-up: mandar el `repr` de un float es cómo
   0,1 + 0,2 llega al SIN como 0,30000000000000004.

4. **Cliente SOAP del SIAT — hecho, falta poner los WSDL.**
   `services/billing_siat_client.py` implementa CUIS, CUFD, verificación de
   NIT, recepción y anulación con `zeep`. Se eligió `zeep` sobre SOAP a mano
   por medición: sobre `lxml` y `requests`, que ya estaban, suma **283 KB** —
   no es una decisión de infraestructura—, y ahorra diez envelopes escritos a
   mano. El argumento de fondo: el XML a mano falló en `nillable` al primer
   intento y lo cazó el XSD; con diez operaciones sin esquema, el error lo caza
   el SIN.

   **Los WSDL se leen de disco y nunca se bajan.** `zeep` los descargaría en
   cada arranque en frío de la Lambda, y una caída del SIAT sería una caída
   nuestra. Van en `docs/siat/wsdl/` —`codigos`, `facturacion`,
   `sincronizacion`— y **todavía no están**: el anexo describe cada operación
   pero no publica sus URL, que salen del portal del SIAT con el sistema ya
   autorizado. `docs/siat/wsdl/LEEME.md` dice qué archivo va y cómo comprobar
   que quedó bien. Sin ellos el servicio responde `SIAT_WSDL_MISSING`, no falla
   callado.

   Todas las llamadas pasan por **una sola costura** (`_invoke`), que es lo que
   permite probar el armado de parámetros sin WSDL y lo que evita nueve
   caminos de error distintos. El token va en el `.env` como header `apikey`,
   nunca en el cuerpo SOAP que un log podría capturar.

   **`.pylintrc` en la raíz**, pasado con `--rcfile` desde `verify_service.py`
   porque Pylint corre con el servicio como raíz y ahí no se descubre solo.
   Usa `ignored-modules=lxml`: probé primero `extension-pkg-allow-list` y
   estaba mal —hace que Pylint INTENTE inspeccionar la extensión en C y se
   equivoque con falsos positivos de nivel E—.

5. **Facturación electrónica: lo que sí depende del trámite.** Cliente SOAP,
   CUIS (365 días), CUFD (24 h por punto de venta, trae el código de control
   que cierra el CUF), envío y anulación, contingencia con CAFC y paquete en
   48 h, catálogos paramétricos, y la leyenda del pie que cambia
   aleatoriamente por la Ley 453. Rafael tramita la autorización como
   **Sistema Proveedor**, modalidad **Computarizada en Línea**.

4. **Alinear los modelos de AI al patrón de los demás.** `PromptItem` (9
   campos) y `ExplanationItem` (8) son los únicos ítems de DynamoDB modelados
   como `dataclass` con `from_item`; todos los demás servicios usan
   `TypedDict`, que además no dispara `too-many-instance-attributes` y borra
   los dos únicos `disable` de ese tipo que quedan. Toca 32 puntos entre el
   modelo y sus consumidores. **Se hace cuando se trabaje AI**, no antes.

5. **Sección "Usuarios"** para que un MANAGER cree y administre a su gente.

6. **Alinear `mining_analysis/services/utils.py` al boilerplate estándar** — es
   la variante MySQL (828 líneas contra 408); de ahí salió el 500 del sync. Las
   420 líneas extra son la carga masiva que `/etl/upload` y `/royalties/*`
   todavía usan, así que no es un reemplazo directo. Espera a que se verifique
   la carga de fin de mes.

**Lo que falta para vender, no para demostrar:** control de suscripción,
retención de datos y persistencia de lo que produce la capa de IA.

---

## 6. Decisiones vigentes

Las que siguen condicionando el código. Las revertidas no están.

### Negocio

- **La cotización oficial de una quincena es el promedio de la anterior.** La
  media del 1 al 15 rige del 16 al 30; **no** es la última cotización del día.
  El promedio va sobre los días que ese mineral tenga: Estaño puede tener 10 y
  Wólfram 2 en la misma quincena.
- **El BCB publica el viernes de noche una cotización que rige sábado, domingo
  y lunes.** La ventana del sync llega al final del bloque, no a "hoy".
- **El 27 de junio de 2026 el tipo de cambio dejó de estar fijo.** Toda serie
  proyectada arranca ahí; los años de 6,86 son otro régimen.
- **El Ministerio de Minería recibe el boletín en PDF y PNG** a cambio de los
  datos de cotizaciones. Ese intercambio no se toca.
- **SmartDecisions no reserva ni aparta stock del ERP del cliente:** reporta
  `disponible = existencia − comprometido`. Ser dueño de esa verdad sería ser
  dueño de la concurrencia y de la culpa. Lo que sí aporta es cobertura en días,
  fecha estimada de quiebre, capital inmovilizado y clase ABC.
- **Degradación elegante, no ceros.** Sin la columna opcional, la sección se
  declara no disponible y la UI la oculta. Mostrar 0 % de margen sin costos es
  mentir.
- **Aceptación parcial:** las filas inválidas se apartan con su motivo y el
  resto se carga. Coordenada 0 = sin dato.

### Técnicas

- **El backend devuelve datos y códigos, nunca texto de cara al usuario.** La
  interpretación es del frontend o de la capa de IA; no hay catálogos de textos
  en el repositorio.
- **Nada configurable vive en el código.** Las variables son requeridas: un
  `ENV_VARS['X'] or 30` sigue siendo un número elegido por el código. Si falta
  configuración, el servicio no arranca.
- **INGEST es la puerta de entrada de datos, cualquiera sea el dato.** No se
  parte por especificidad todavía: la plantilla, el API del ERP y el maestro de
  clientes entran por ahí, y es **su único dueño**. Quien necesite un cliente
  lo pide a INGEST por HTTP, como se le pide a EVENTS o a FILES; **nadie más
  toca `ingest_clients`**. El 27-sep se duplicó ese maestro en OPTIMIZATION
  —571 líneas con la regla de negocio copiada— y se revirtió entero. Un
  microservicio `CLIENTS` aparte se evaluará cuando haya un segundo consumidor
  real, no antes.

- **El dueño es parte de la consulta, no un filtro posterior.** Hoy el dueño es
  el `client` del token, o el email cuando no lo tiene. En OPTIMIZATION además
  es parte de la clave de partición, porque la carga borra la partición antes de
  escribir.
- **Un archivo se identifica por su contenido.** Misma huella y mismo dueño = el
  mismo dataset.
- **La cuenta por cobrar vive al nivel de factura**, sumando `total_amount` por
  `order_id`. Factura sin cobros es saldo abierto; cobro sin venta es
  incidencia con código, nunca descarte en silencio.
- **El modelo predictivo es suavizado exponencial con tendencia amortiguada**,
  ajustado por backtest, y cada proyección publica su error y el del modelo
  ingenuo.
- **La capa de IA recibe la respuesta del backend tal cual**; `view` sólo elige
  el rol. Los roles viven versionados en DynamoDB y la versión participa de la
  clave de caché.
- **El entorno local corre las mismas versiones que el Lambda.** Sin versiones
  fijadas en `requirements.txt`. El Lambda no tiene pyarrow: en pandas 3 una
  columna de miembros de un `str, Enum` se compara por `.value`.
- **Un libro se abre una sola vez por subida**; tres aperturas de openpyxl
  agotaban los 30 s del Lambda.
- **Los timestamps que llegan de un dispositivo se normalizan a
  `TARGET_TIMEZONE`** antes de decidir a qué día pertenecen. Un equipo en UTC
  ponía la ruta en el día siguiente.
- **No se crean carpetas nuevas dentro de un microservicio.** `scripts/` existe
  sólo en MINING_ANALYSIS, por la carga quincenal manual.
- **Los tests de los servicios base no importan módulos que validen entorno.**
  GitHub Actions corre sin `.env` y la colección falla antes de empezar.

### Infraestructura

- **Sin RDS por presupuesto.** Todo servicio nuevo va a DynamoDB + Lambda + S3.
- **Las tablas se crean con `create_dynamodb_tables.sh`**: `build_and_deploy.sh`
  no crea claves compuestas ni admite dos tablas por servicio. El acceso lo
  cubre `AmazonDynamoDBFullAccess` en el rol.
- **El `.env` completo viaja a las variables del Lambda: ningún valor lleva
  coma ni llave.** La coma separa variables y la llave abre una estructura
  anidada en `--environment Variables={...}`; una plantilla de URL va con `%s`.
  Un `LME_{symbol}_cash` abortó un despliegue **después** de subir el código.
- **Bedrock exige perfiles de inferencia** (`us.` delante) y un formulario de
  caso de uso por cuenta.
- **Los deploys de backend los hace Rafael**; los de frontend, el asistente.
- **Gotchas comprobados:** con red lenta `aws s3 cp` puede devolver 0 sin subir
  y el Lambda recarga el ZIP viejo (comprobar fecha en S3 y `CodeSize`); el
  CORS de un API ya creado no se actualiza desde el script (se agregó `PATCH` a
  OPTIMIZATION y AUTH con `update-api`).
