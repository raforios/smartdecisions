> Guía para probar SmartDecisions por cuenta propia. Cada paso dice qué hacer,
> qué vas a ver y cómo saber que salió bien.
>
> Documento hermano: `GUIA_PRODUCTO.md`, que describe cada módulo en detalle.

# Cómo probar SmartDecisions

Toma unos 40 minutos si haces todo. Los primeros 10 minutos ya muestran la
mitad del producto.

## Antes de empezar

| Necesitas | Detalle |
|---|---|
| Un navegador | Chrome, Edge o Safari actualizados |
| Tu usuario y contraseña | Te los entregamos aparte |
| Un archivo de ventas | El tuyo, o el de ejemplo que trae el portal |

No necesitas instalar nada.

---

# Parte 1 — Entrar y cargar el primer archivo

## Paso 1. Entrar

Abre el portal y entra con tu usuario.

**Qué vas a ver:** la pantalla de carga, con un selector que dice «¿Qué vas a
cargar?» y un botón para descargar la plantilla.

## Paso 2. Descargar la plantilla de ventas

Deja el selector en **Ventas** y presiona **Descargar plantilla**.

**Qué vas a ver:** un archivo `plantilla_ventas.xlsx` con dos hojas. La hoja
**Datos** tiene las cabeceras y unas filas de ejemplo; la hoja
**Instrucciones** explica qué significa cada columna, cuáles son obligatorias
y en qué formato va cada una.

**Cómo saber que salió bien:** las cabeceras están en castellano y la primera
es **Fecha**.

> **Lo que conviene entender acá.** Sólo cinco columnas son obligatorias:
> Fecha, Nro Factura, Cliente, Producto y Cantidad. Todo lo demás es opcional,
> y cada columna que agregues enciende algo más. Puedes empezar con lo mínimo
> y volver después con un archivo más completo.

## Paso 3. Llenar el archivo, o usar el tuyo

Dos caminos:

- **Escribe unas filas** sobre la plantilla, borrando las de ejemplo.
- **Exporta el reporte de ventas de tu sistema** y acomoda las columnas a las
  cabeceras de la plantilla. No hace falta que estén en el mismo orden ni que
  sobren o falten espacios: el sistema reconoce la cabecera aunque tenga
  acentos, mayúsculas distintas o espacios de más.

> Si tu reporte tiene una forma muy distinta —cabeceras en otra fila, columnas
> que se llaman de otro modo— mándanoslo: la conversión la hacemos nosotros,
> una vez, y después tu ERP exporta ya en formato.

## Paso 4. Subirlo

Con el selector en **Ventas**, elige el archivo y súbelo.

**Qué vas a ver:** primero «Validando y procesando el archivo…», y después el
resultado de la validación con cuatro cifras: **filas válidas**, **errores**,
**puntos de venta** y **productos**, más el **rango de fechas** que cubre.

**Cómo saber que salió bien:** dice «Archivo validado» y el número de filas
válidas coincide con lo que mandaste.

### Si aparecen errores

**No pasa nada y no hay que rehacer el archivo.** Las filas con problemas se
apartan con su motivo y el resto entra. Vas a ver una tabla con la fila, la
columna y qué pasó.

Presiona **descargar las filas rechazadas**: te llevas sólo ésas, las
corriges y las vuelves a subir. Se suman a las que ya estaban.

> **Pruébalo a propósito.** Pon una fecha inventada como `32/13/2025` o una
> cantidad negativa en una fila y súbelo. Vas a ver que esa fila se aparta y
> las demás entran. Eso es lo que evita que un archivo de cinco mil líneas se
> caiga entero por dos celdas.

---

# Parte 2 — Las primeras respuestas

Al terminar la carga aparece el menú de análisis. Cada tarjeta abre una
pantalla.

## Paso 5. Resumen Comercial

Presiona **Resumen Comercial**.

**Qué vas a ver:** arriba las cifras grandes —venta total, variación,
concentración—; debajo, la venta por mes, por categoría, los diez productos y
los diez clientes más importantes, y la venta por vendedor.

**Qué preguntarte mirándolo:**

- ¿La venta por mes sube, baja o se mueve por estación?
- En **Top 10 mejores clientes**, ¿cuánto de tu venta está en los tres
  primeros? Ése es tu riesgo real de concentración.
- En **Productos menos vendidos**, ¿cuántos de esos siguen ocupando catálogo
  y almacén?

**Si cargaste Costo Unitario**, baja hasta **Rentabilidad**. Compara **Venta
por categoría** con **Dónde está la ganancia**: casi nunca coinciden. El
producto que más factura rara vez es el que más deja, y ésa suele ser la
primera sorpresa del producto.

## Paso 6. Fuente de volumen

Presiona **Fuente de volumen**.

**Qué vas a ver:** no cuánto vendiste, sino **qué lo empujó**.

**Lo que hay que mirar:** en **Clientes y el producto que los sostiene**,
busca un cliente grande que dependa de un solo producto. Ese cliente es mucho
más frágil de lo que su facturación sugiere: si ese producto falla, se va
entero.

## Paso 7. Segmentación y Salud de cartera

**Segmentación** clasifica a tus clientes por valor. **Salud de cartera**
responde otra cosa: **quién se está yendo**.

**Lo que hay que mirar:** en Salud de cartera, los **clientes en riesgo** son
los que todavía compran pero cada vez menos. Son los únicos a los que se puede
rescatar: los «perdidos» ya se fueron.

---

# Parte 3 — Encender los otros módulos

Cada archivo extra enciende una pantalla más. Puedes hacerlos en cualquier
orden, o sólo el que te interese.

## Paso 8. Cobros → Cuentas por cobrar

Descarga la plantilla **Cobros**, llénala y súbela con el selector en
**Cobros**.

Es un archivo corto: **Nro Factura**, **Fecha Cobro** y **Monto Cobrado**. Se
casa con las ventas por el número de factura.

**Qué vas a ver después, en Cuentas por cobrar:** el saldo, cuánto está
vencido, cuánto se espera recuperar, quién debe, quién cobra y qué vence
cuándo.

**Lo que hay que mirar:** baja hasta **Qué deja el crédito**. Es la resta
completa: margen bruto, menos el costo de tener la plata afuera, menos el
incobrable esperado. El resultado puede ser menor que no haber vendido.

> **Pruébalo.** Deja una factura sin ningún pago. No es un error: aparece como
> saldo abierto, que es exactamente lo que tiene que pasar. Y manda el mismo
> pago dos veces: verás que no se cuenta dos veces.

## Paso 9. Stock → Stock del día

Plantilla **Stock**: **Fecha**, **Producto** y **Existencia**.

**Qué vas a ver:** cuántos días te dura lo que tienes, qué está por quebrar y
cuánto capital está quieto.

**Lo que hay que mirar:** la cobertura se calcula con la demanda que se ve en
**tus** ventas, no con un promedio teórico. Por eso un producto con mucho
stock puede aparecer «por quebrar» si se vende muy rápido.

## Paso 10. Objetivos → Cumplimiento

Plantilla **Objetivos**: **Cliente**, **Periodo** y **Objetivo**. El periodo
es el mes, escrito como `2026-03`.

**Qué vas a ver:** cinco cifras arriba —objetivo, facturado, cobrado, deuda y
puntos— y el detalle cliente por cliente, peor cumplimiento primero.

**Lo que hay que mirar, y es lo más importante de esta pantalla:** cada
cliente tiene **dos semáforos**, uno de facturado y otro de cobrado. Busca un
cliente que esté **amarillo en facturado y rojo en cobrado**. Ése compró
razonablemente bien y no ha pagado. Un reporte que sólo mire el primero lo
daría por aceptable.

En **Cluster por semáforo**, mira la columna **Peso**: veinte clientes rojos
que valen el 2 % del objetivo no son el mismo problema que tres que valen el
40 %.

> **Pruébalo.** Pon un objetivo a un cliente que no aparece en tus ventas.
> Verás que se conserva y aparece en cero: ése es el cliente que la empresa
> quiere activar y que en un reporte de ventas es invisible.
>
> **Pruébalo también:** vuelve a mandar el mismo mes con otro número. Lo
> corrige, no lo duplica.

### Ajustar el semáforo a tu empresa

Los cortes por defecto son rojo por debajo del 50 %, amarillo hasta el 100 %,
verde desde ahí. Si tu empresa los mide distinto, se cambian en la política
comercial, junto con cuántos bolivianos vale un punto en cada cluster.

Los nombres de los clusters son los tuyos: el sistema no define ninguno.

## Paso 11. Visitas y Rutas

Para que Rutas funcione hacen falta **coordenadas**. Vienen de tres lados: del
archivo de ventas, del maestro de clientes, o capturadas por el vendedor en el
terreno.

Plantilla **Visitas**: **Fecha**, **Vendedor**, **Cliente** y **Hora**.

En el módulo de Rutas:

- **Histórico** muestra lo que ya pasó.
- **Planes** muestra lo que va a pasar. Crea uno, o repite una ruta anterior
  con otra fecha.
- **Comparación** cruza los dos sobre el mismo mapa.
- **Optimizar** toma un plan y calcula el mejor orden usando la red vial real.

**Lo que hay que mirar en Optimizar:** vas a ver **las dos rutas, la actual y
la optimizada**, una al lado de la otra, con distancia, duración y el ahorro.
Nada se cambia hasta que lo apliques.

> **Pruébalo.** Desde el teléfono, intenta marcar una visita a un cliente
> estando lejos de él. El sistema la rechaza. Ahora hazlo parado en la puerta:
> la acepta. Eso es lo que hace que la comparación plan-contra-real signifique
> algo.
>
> Y visita un lugar que el plan no conocía: **no se bloquea**. Es un cliente
> nuevo, y es la evidencia de que esa ruta debería crecer.

---

# Parte 4 — Conectar tu ERP

Todo lo que subiste por archivo se puede mandar por API, con los mismos
contratos y los mismos códigos de error. La carga diaria queda automatizada y
nadie vuelve a tocar un archivo.

Pídenos la colección de pruebas: trae cada llamada armada y lista para
ejecutar.

---

# Preguntas que aparecen siempre

**¿Tengo que cargar todo?** No. Con el archivo de ventas ya se enciende la
mitad del producto. Lo demás se agrega cuando lo tengas.

**¿Qué pasa si subo el mismo archivo dos veces?** El sistema lo reconoce por
su contenido y no lo duplica.

**¿Y si me equivoqué en una fila?** Se descarga el archivo de rechazadas, se
corrige y se vuelve a subir sólo eso.

**¿Puede otra empresa ver mis datos?** No. El dueño de cada carga forma parte
de cada consulta. Un dato ajeno responde exactamente igual que uno que no
existe.

**Corregí el nombre de un cliente y volví a subir un archivo viejo. ¿Se pierde
la corrección?** No. Una recarga completa lo que falta pero nunca reescribe lo
que ya está. Sobrescribir es un acto aparte y deliberado.

**¿Los reportes se pueden ver en dólares?** Sí, y cada monto se convierte a la
cotización **de su propio día**. Convertir un año entero a la tasa de hoy
convertiría una devaluación en crecimiento.

**El archivo es de marzo y lo abro en agosto. ¿La mora sale mal?** No. Las
antigüedades se miden contra el último día con movimiento del archivo, no
contra hoy.

---

# Si algo no funciona

| Síntoma | Qué mirar |
|---|---|
| «Formato no soportado» | El archivo tiene que ser `.xlsx` o `.csv` |
| «Falta una columna» | Alguna de las cinco obligatorias no está. Compárala con la plantilla |
| Muchas filas rechazadas por fecha | Revisa que la columna sea fecha y no texto |
| Una pantalla dice que falta un archivo | Es normal: ese módulo necesita su propio archivo |
| Rutas no muestra el mapa | Faltan coordenadas. Cárgalas en ventas, en el maestro o desde el terreno |
| Cumplimiento aparece vacío | Falta el archivo de objetivos |

Si algo se queda trabado, avísanos con el nombre del archivo y la hora: cada
carga queda registrada y podemos ver exactamente qué pasó.
