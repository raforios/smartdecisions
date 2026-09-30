> Guía del producto SmartDecisions, para entregar a un cliente. Describe cada
> módulo, cada menú y cada gráfico del portal, con qué pregunta responde y qué
> hace falta para que se encienda.
>
> Documento hermano: `GUIA_PRUEBA.md`, el paso a paso para probarlo uno mismo.
> `GUION_DEMO.md` es el guion de la demostración de diez minutos.

# SmartDecisions

## Qué es

SmartDecisions convierte los archivos que tu sistema ya emite —el reporte de
ventas, el de cobros, el de inventario— en las decisiones comerciales que hoy
se toman de memoria: a quién visitar mañana, a quién dejar de dar crédito, qué
producto está a punto de quebrar, qué cliente se está yendo sin que nadie lo
haya notado.

No es un ERP y no reemplaza al tuyo. Se conecta al que tienes.

## Lo que hay que entender antes de empezar

**Un archivo por tema.** Ventas, cobros, stock, visitas y objetivos son cinco
archivos distintos, y eso es a propósito. Una factura a 90 días se cobra tres
meses después del archivo que la registró; el inventario cambia todos los días
mientras las ventas se cargan una vez al mes. Forzarlos a un solo libro
significaría volver a subir todo cada vez que alguien paga.

**Ventas es el primero.** Es el archivo que crea el conjunto de datos; los
otros cuatro se enganchan a él. Los demás se cargan cuando los tengas, y cada
módulo se enciende con el suyo.

**Dos puertas, siempre.** Todo lo que se puede subir como archivo se puede
mandar también desde tu ERP por API, con el mismo validador y los mismos
códigos de error. Nada está disponible por una sola vía.

**Nada se pierde por una fila mala.** Si una fecha viene mal escrita, esa fila
se aparta con su motivo y el resto entra. Las filas apartadas se descargan en
un archivo aparte para que las corrijas y las vuelvas a subir: no hay que
rehacer el archivo entero.

**Tus datos son tuyos.** El dueño de cada carga es el usuario que la hizo, y
forma parte de cada consulta. Un dato de otra empresa responde exactamente
igual que uno que no existe.

---

# Los cinco archivos que puedes cargar

Cada uno se descarga como plantilla desde el portal, con sus cabeceras en
castellano y una hoja de instrucciones. La plantilla se genera del mismo
contrato que valida el archivo, así que nunca se desfasan.

## 1. Ventas — el que enciende casi todo

Una fila por línea de factura. Las columnas mínimas son **Fecha**, **Nro
Factura**, **Cliente**, **Producto** y **Cantidad**; el resto es opcional y
cada columna que agregues enciende algo más:

| Si cargas… | Se enciende |
|---|---|
| Precio Unitario y Monto Total | Todo el análisis de dinero, no sólo de unidades |
| Costo Unitario | Rentabilidad: margen por categoría y dónde está la ganancia |
| Latitud y Longitud | Rutas: el mapa y la optimización |
| Zona, Ciudad, Canal | Los cortes geográficos y comerciales de cada reporte |
| Vendedor | Productividad por vendedor y su cartera |
| Condición Venta y Plazo Días | Cuentas por cobrar completo |

## 2. Cobros — qué se pagó de lo que se facturó

Una fila por pago: **Nro Factura**, **Fecha Cobro** y **Monto Cobrado**. Se
casa con las ventas por el número de factura. Una factura sin pagos no es un
error: es un saldo abierto, que es exactamente lo que hay que ver.

Un pago puede venir en cuotas, y se suman. Mandar el mismo pago dos veces no
lo cuenta dos veces.

## 3. Stock — la foto del almacén

Una fila por producto y día: **Fecha**, **Producto** y **Existencia**.
Opcionalmente **Comprometido** —lo que tu ERP ya reservó en pedidos—, **En
Tránsito**, **Almacén** y **Costo Unitario**.

Es una foto, no un libro de movimientos. SmartDecisions lee el stock, nunca lo
escribe: la verdad del inventario es de tu ERP y no se le disputa.

## 4. Visitas — lo que hizo la fuerza de ventas

**Fecha**, **Vendedor**, **Cliente** y **Hora**. Es el único archivo que
alcanza clientes que las ventas nunca facturaron —el prospecto al que se
visitó y no compró— y el que puede traer la coordenada GPS de la puerta. Los
dos se guardan en el maestro de clientes.

## 5. Objetivos — la única cifra que ningún movimiento implica

**Cliente**, **Periodo** (el mes, como `2026-03`) y **Objetivo**.

Este archivo es distinto de todos los demás y vale la pena entender por qué.
Los otros cuatro reportan algo que pasó: una venta, un pago, un conteo, una
visita. El objetivo es una **decisión**, tomada antes de que empiece el mes, y
no hay forma de deducirlo de ningún historial.

Volver a mandar un mes lo corrige, no lo duplica. Un objetivo para un cliente
que nunca facturó se conserva y se reporta: ése es justamente el cliente que
la empresa quiere activar.

---

# El maestro de clientes

Lo que describe **al cliente** —nombre, coordenadas, dirección, zona, ciudad,
canal, tipo de negocio, contacto, cluster, supervisor, mercado— vive **una
sola vez**, en el maestro. Los archivos de transacciones sólo lo identifican.

Tres reglas que hacen que esto funcione en la práctica:

1. **Un cliente que no existe se da de alta. Uno que existe no se reescribe**:
   sólo se completan los campos que estaban vacíos. Una recarga nunca puede
   deshacer una corrección.
2. **Lo que el archivo no traiga se toma del maestro.** Cargar ventas sin
   coordenadas no apaga Rutas si esas coordenadas ya se conocían.
3. **Sobrescribir es un acto aparte y explícito**, nunca el efecto secundario
   de volver a leer un archivo.

Se alimenta desde tres puertas: el archivo, el API de tu ERP, y **el terreno**
—un vendedor que llega a una dirección nueva da de alta al cliente ahí mismo,
desde el teléfono, con la coordenada del lugar donde está parado—.

---

# Módulo 1 — Análisis comercial

Se entra subiendo el archivo de ventas. Cada tarjeta del menú abre una
pantalla.

## Resumen Comercial

La foto de arriba: venta total, margen, variación, índice de concentración.
Debajo, seis bloques:

| Gráfico | Qué responde |
|---|---|
| **Venta por mes** | La tendencia, y si el mes que va es mejor o peor |
| **Venta por categoría** | De dónde sale el dinero |
| **Top 10 productos más vendidos** | Qué sostiene la venta |
| **Top 10 mejores clientes** | Quién sostiene la venta |
| **Venta por vendedor** | Cómo se reparte el esfuerzo |
| **Productos menos vendidos** | Qué está ocupando catálogo sin rotar |

**Rentabilidad** aparece sólo si el archivo trae Costo Unitario: margen por
categoría y **dónde está la ganancia**, que casi nunca coincide con dónde está
la venta. El producto que más factura suele no ser el que más deja.

**Crecimiento** compara mes a mes y expone la **estacionalidad**, para no
confundir un mal mes con una caída.

**Concentración y riesgo** mide cuánto de tu venta depende de pocos clientes.
Se ve en la **curva de Pareto**, en las **clases ABC del catálogo** y en el
**peso del top 10**.

**Eficiencia comercial** cruza productividad por vendedor con la **deriva del
precio realizado**: cuánto se alejó el precio efectivamente cobrado del precio
de lista, que es donde se escapa el margen sin que nadie firme un descuento.

## Fuente de volumen

Responde una pregunta que el resumen no puede: **de dónde vino el movimiento**.
No cuánto se vendió, sino qué lo empujó.

- **Productos que hacen el volumen** y **clientes y el producto que los
  sostiene**: si un cliente grande depende de un solo producto, ese cliente es
  más frágil de lo que su facturación sugiere.
- **Qué categorías ganan y pierden peso**: el cambio de composición, que
  precede a la caída de la venta.
- **Cruce cliente × producto**: la matriz completa, con vistas por producto y
  por cliente.

## Cumplimiento de objetivos

Compara lo que se vendió contra **lo que se debía vender**. Necesita el
archivo de objetivos.

El objetivo se mide **dos veces**, y ésa es la razón de ser del módulo:

- **contra lo facturado** — ¿el cliente compró lo que tenía que comprar?
- **contra lo cobrado** — ¿la empresa efectivamente recibió ese dinero?

Un cliente puede cumplir en el papel y deber hasta el último boliviano. Un
reporte que sólo mire lo primero lo daría por bueno.

Cinco cifras arriba: **Objetivo**, **Facturado**, **Cobrado**, **Deuda** y
**Puntos**. Siempre se cumple que facturado = cobrado + deuda, porque el cobro
cuenta en el mes de la factura que salda, no en el mes en que entró.

| Gráfico | Qué responde |
|---|---|
| **Clientes por semáforo** | Cuántos están en verde, amarillo y rojo |
| **Peso de cada semáforo** | Cuánto del objetivo representa cada color |
| **Cluster por semáforo** | La matriz, con el peso de cada celda |
| **Cliente por cliente** | El detalle, peor cumplimiento primero |

El **peso** es lo que evita que la matriz engañe: veinte clientes rojos que
valen el 2 % del objetivo son una mañana muy distinta de tres que valen el
40 %.

**Los cortes del semáforo y los puntos son tuyos, no del sistema.** Por
defecto rojo por debajo del 50 %, amarillo hasta el 100 %, verde desde ahí; y
los bolivianos que vale un punto se fijan por cluster. Todo se cambia desde la
política comercial. Los nombres de los clusters también son tuyos: el producto
no define ninguno.

## Cuentas por cobrar

Necesita el archivo de cobros, o al menos las columnas de crédito en ventas.

Arriba: **saldo por cobrar**, **vencido**, **recuperable**, **incobrable
estimado**, **venta a crédito**, **DSO** —cuántos días tarda en volver la
venta a crédito—, **mora promedio** y **efectividad de cobranza**.

| Gráfico | Qué responde |
|---|---|
| **Antigüedad del saldo** | Cuánto se debe en cada tramo de atraso |
| **Recuperable vs incobrable** | Cuánto de eso va a volver |
| **Quiénes deben** | El detalle por cliente |
| **Responsables de cobro** | Quién tiene cada saldo a su cargo |
| **Cobros pendientes por fecha** | Qué vence cuándo |
| **Curva de cobro** | Cómo entra el dinero en el tiempo |
| **A quién llamar hoy** | La agenda del día, priorizada |

**Qué deja el crédito** es el bloque que cierra la pregunta comercial: margen
bruto del crédito, menos el costo financiero de tener la plata afuera, menos
el incobrable esperado, igual al **margen neto del crédito**. Vender a crédito
puede dejar menos que no vender.

Las antigüedades se miden contra **el último día con movimiento del archivo**,
no contra hoy: un archivo de marzo leído en agosto no debe mostrar cinco meses
de mora inventados.

## Stock del día

Necesita el archivo de stock.

**Disponible**, **valor del inventario**, **sin stock**, **por quebrar**,
**capital quieto** y **cobertura promedio**, más la **venta diaria en riesgo**.

| Gráfico | Qué responde |
|---|---|
| **Situación del catálogo** | Cuántos productos en cada estado |
| **Dónde está el capital** | En qué está inmovilizado el dinero |
| **Por quebrar** | Qué se acaba primero, según la demanda observada |
| **Capital inmovilizado** | Qué no rota y cuánto cuesta tenerlo |

La cobertura se calcula con la demanda que se ve en las ventas, no con un
promedio teórico.

## Salud de cartera

Quién se está yendo, sin que nadie lo haya notado.

**Nuevos**, **recuperados**, **perdidos** y **clientes activos**, con el
**movimiento de clientes por mes** y los **clientes en riesgo** —los que
todavía compran pero cada vez menos, que son los únicos a los que se puede
rescatar—.

## Pronóstico de demanda

Proyección de los próximos meses, total o por categoría, con varios métodos.
Cuando la serie es corta el sistema **lo dice** en vez de proyectar igual: una
proyección con tres meses de historia no es una proyección.

## Segmentación de clientes

Clasifica por valor —alto, medio, bajo— para priorizar el esfuerzo. Es una
clasificación **calculada** a partir de la venta, distinta del **cluster**,
que es una decisión comercial tuya y viene en el maestro.

## Oportunidades comerciales

Qué producto ofrecerle a qué cliente, a partir de lo que compran juntos los
clientes parecidos. Cada sugerencia viene con la venta potencial estimada.

---

# Módulo 2 — Rutas

Necesita coordenadas: las del archivo de ventas, las del maestro de clientes o
las que capture un vendedor desde el terreno.

## Histórico

Lo que **ya pasó**: las rutas ejecutadas, con sus paradas y sus resultados.

## Planes

Lo que **va a pasar**: las rutas planificadas. Se cargan una por una, de forma
masiva por archivo, o se repiten desde una ruta anterior.

Histórico y Planes están separados a propósito. Mezclarlos —presentar lo
ejecutado como si fuera un plan— era el error que hacía imposible comparar.

## En vivo

El recorrido del día sobre el mapa, completo, a medida que ocurre.

## Comparación

El plan contra lo real, sobre el mismo mapa: qué paradas se cumplieron, cuáles
no y adónde se fue el vendedor que no estaba planificado.

Una visita sólo cuenta como cumplida si **el vendedor estaba ahí**. Marcar un
cliente a quince kilómetros de distancia ya no es posible: la geocerca lo
rechaza. Aplica sólo a rutas planificadas de hoy en adelante, porque un
histórico cargado por archivo nunca pasó por esa puerta.

Un lugar que el plan no conocía **no se bloquea**: es un cliente nuevo, y es
justamente la evidencia de que la ruta debería crecer.

## Optimizar

Toma una ruta planificada y calcula el mejor orden de visita, usando la red
vial real. Muestra **las dos rutas, la actual y la optimizada**, una al lado
de la otra, con distancia, duración y el ahorro. Si convence, se aplica.

## Stock del día

El inventario disponible, para que el vendedor no ofrezca lo que no hay.

---

# Módulo 3 — Cotizaciones y variables que se mueven

Hay cifras que cambian solas y cambian lo que un reporte significa: el tipo de
cambio, el precio del combustible, un arancel, un índice. No pueden vivir en
la configuración del sistema, porque un número que el cliente lee de una
factura cada semana no puede necesitar un despliegue para cambiarse.

**Tipo de cambio.** Se publica a diario y queda su historia. Cualquier reporte
se puede leer en dólares, y cada monto se convierte **a la cotización de su
propio día**: convertir un año entero a la tasa de hoy convierte una
devaluación en crecimiento.

**Factores.** Cada uno tiene nombre, unidad, valor y estado. Nace activo;
apagarlo lo deja de contar sin borrar nada. Tanto el valor como el estado
guardan su historia fechada, así que un reporte de marzo se reproduce en
septiembre con las cifras de marzo.

**Costo de distribución local.** Kilómetros ÷ rendimiento × precio del litro,
sobre el **viaje redondo** —el vehículo termina en el último cliente y vuelve
vacío—, y dividido entre las unidades da el costo por unidad, que es la cifra
que llega al margen. El rendimiento es el **promedio estimado de tu flota en
reparto urbano**, que consume cerca del doble que carretera; se carga como
dato y se va afinando.

---

# Módulo 4 — Interpretación

Donde está configurado, cada pantalla ofrece una lectura en lenguaje natural
de lo que se está viendo. No inventa números: lee los mismos que están en
pantalla y explica qué implican.

---

# Cómo se conecta con tu sistema

**Por archivo.** Descargas la plantilla, la llenas o la exporta tu ERP, la
subes. El archivo viaja a un almacenamiento propio y el servicio lo lee de
ahí, así que el tamaño no es un problema.

**Por API.** Tu ERP manda las filas directamente, con los mismos contratos y
los mismos códigos de error. Sirve para automatizar la carga diaria sin que
nadie toque un archivo.

**Desde el terreno.** El vendedor da de alta un cliente y registra su visita
desde el teléfono.

Las tres puertas escriben en el mismo lugar y se validan igual.

---

# Qué necesitas para empezar

| Quieres ver… | Necesitas cargar |
|---|---|
| Resumen comercial, crecimiento, concentración | Ventas |
| Rentabilidad y margen | Ventas con Costo Unitario |
| Cuentas por cobrar | Ventas con crédito, y Cobros |
| Stock del día | Ventas y Stock |
| Rutas y optimización | Ventas con coordenadas, o el maestro de clientes |
| Comparación plan contra real | Planes y Visitas |
| Cumplimiento de objetivos | Ventas y Objetivos |

Con el archivo de ventas solo ya se enciende la mitad del producto. Lo demás
se agrega cuando lo tengas.
