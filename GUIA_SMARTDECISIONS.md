> **Guía interna de SmartDecisions** para BearSoft: para quien presenta el
> producto y para el equipo técnico que lo acompaña. No se entrega a nadie de
> afuera: todavía no hay clientes, se están buscando.
>
> Reúne en un solo lugar qué es el producto, con qué datos se muestra, el guion
> de la demo, qué hace cada pantalla y cómo responder lo que siempre preguntan.
> El estado técnico y lo pendiente están en `SMARTDECISIONS.md`.
>
> Cifras leídas en el portal el 05-oct. Si se recargan los datos de prueba, se
> actualizan aquí.

# Guía de SmartDecisions

## Índice

1. Qué es y qué problema resuelve
2. Las dos empresas de demostración
3. Antes de presentar
4. Guion de la demo (12 minutos)
5. Pantalla por pantalla
6. Cómo entran los datos
7. Pruebas que convencen en vivo
8. Preguntas que siempre hacen
9. Si algo falla

---

## 1. Qué es y qué problema resuelve

Una distribuidora mediana decide con la intuición del gerente y un reporte que
sólo dice cuánto se vendió. Un ERP analítico cuesta caro, tarda meses y
necesita un consultor. Pero **la empresa ya tiene sus archivos**: ventas,
cobros, inventario.

SmartDecisions convierte esos archivos en las decisiones comerciales que hoy se
toman de memoria: a quién visitar mañana, a quién dejar de dar crédito, qué
producto está por quebrar, qué cliente se está yendo sin que nadie lo note.
**Sin ERP nuevo, sin instalación y sin proyecto de integración.** No reemplaza
al ERP: se conecta al que la empresa tiene.

**El diferenciador:** `Afinidad × Drop Size = Oportunidad Comercial Real`. No
muestra lo obvio: le dice al vendedor qué ofrecer en cada tienda y cuánto vale.

**Cuatro módulos:** Análisis comercial, Rutas, Factores externos y tipo de
cambio, y Minerales. Encima de todos,
una lectura en lenguaje natural de lo que se está viendo (IA), que no inventa
números: lee los de la pantalla.

**Roles:** el **gerente** ve y configura todo; el **vendedor** entra desde el
teléfono a *Mi ruta*; el usuario de **consulta** lee los reportes.

---

## 2. Las dos empresas de demostración

Las dos son **inventadas por BearSoft** sobre datos de ejemplo de operaciones
de consumo masivo, y las dos están **completas**: ventas con costo, cobros,
stock, visitas y objetivos. Son el escenario al que debería apuntar una
empresa que use el producto.

| | **Comercial Illimani S.R.L.** | **Distribuidora Andina S.R.L.** |
|---|---|---|
| Ingresa con | `gerente@raforios.com` | `gerente@bearsoft.com.bo` |
| Historia | 24 meses (feb-2022 → ene-2024) | 7 meses (jun → dic-2025) |
| Venta | Bs 1,17 M | Bs 4,23 M · 1.299 ventas |
| Clientes / productos | 266 / 159 | 275 / 256 |
| Margen bruto | 22,8 % | 22,4 % |
| Cuentas por cobrar | Bs 187.961 · 57,9 % vencido | Bs 881.944 · 39 % vencido · 16 % incobrable estimado |
| Stock | 159 productos · Bs 139.630 | 256 productos · Bs 3,4 M · 41 sin stock · 78 por quebrar |
| Oportunidades | 964 acciones en 260 puntos de venta | — |
| Cumplimiento | — | 64,7 % del objetivo facturado (275 clientes) |
| Se usa para | **Qué vender y a quién**: tendencia, rentabilidad, oportunidades, pronóstico, cartera | **Cómo cobrar y cumplir**: cumplimiento, cobros, stock, rutas por vendedor |

Por qué dos: Illimani tiene la historia larga que necesitan el pronóstico y la
estacionalidad; Andina tiene el semestre reciente que un gerente revisa hoy. Y
dos cuentas que no se ven entre sí son la prueba de que los datos de cada
empresa son sólo suyos.

Usuarios de cada empresa (gerente, vendedor, consulta): `SMARTDECISIONS.md` §2.

---

## 3. Antes de presentar

| Cosa | Cómo |
|---|---|
| Rutas del día | La mañana de la demo: `python -m tools.seed_demo_routes --date AAAA-MM-DD --yes --reset`. Arma, para las dos empresas, los planes del día que empiezan en BearSoft, un plan en mal orden para Optimizar, los recorridos de los tres días anteriores para Comparación y el stock de cada día |
| Dos navegadores (o una ventana normal y una de incógnito) | Uno con Illimani y otro con Andina, **ya ingresados**. La sesión dura unos 30 minutos: ingresar justo antes |
| Pantallas precalculadas | Abrir una vez cada análisis que se va a mostrar: la segunda vez sale de la memoria y es inmediata |
| Cumplimiento de Illimani | Si se muestra, filtrar el período a los últimos meses: con 24 meses la respuesta pesa y con mala conexión tarda |
| Teléfono | Si se va a mostrar *Mi ruta*, ingresado con el vendedor de Andina |
| Respaldo | Capturas de las pantallas clave de cada empresa por si falla la red |

---

## 4. Guion de la demo (12 minutos)

### El problema (1 min)

> "Una distribuidora mediana decide con la intuición del gerente y un reporte
> que sólo dice cuánto se vendió. Un ERP analítico cuesta caro, tarda meses y
> necesita un consultor. Pero **sí tiene** sus archivos. SmartDecisions los
> convierte en una lista de acciones con su valor en bolivianos."

### Illimani — ¿qué vendo y a quién? (5 min)

**Resumen Comercial.** Bs 1,17 M en 24 meses, tendencia y estacionalidad.

**Rentabilidad — el momento que engancha.** En *Margen por categoría*, mostrar
la categoría de más venta y menor margen contra la de menos venta y mayor
margen (leer las cifras en pantalla).

> "El reporte que reciben hoy ordena por lo que más se vende. Acá está ordenado
> por lo que más **deja**. **El que más vende casi nunca es el que más deja**,
> y esa diferencia no la ve nadie hasta que alguien la calcula."

**Oportunidades.** 964 acciones en 260 puntos de venta. Abrir el detalle de un
producto: los comercios interesados con su motivo.

> "Le dice a su vendedor: *a esta tienda no le estás vendiendo esta categoría y
> deberías, porque tiendas con su mismo patrón de compra la venden bien*. Con
> el monto esperado al lado."

**Pronóstico.** Con 24 meses la proyección tiene de dónde aprender: tendencia
contra media móvil.

**Salud de Cartera.**

> "No son cien clientes en riesgo: son los que **cayeron contra su propio
> promedio**, ordenados por lo que está en juego. Los que se fueron hace más de
> seis meses van aparte: eso es una campaña de reactivación, no una visita."

### Andina — ¿cobro y cumplo? (5 min)

Cambiar al navegador de Andina.

> "Otra empresa, otra cuenta. No ve nada de la anterior ni la anterior de
> ésta."

**Cumplimiento.** 275 clientes con objetivo, 64,7 % facturado. Mostrar el
semáforo doble y *Cliente por cliente*.

> "Facturar no es cobrar. Este cliente está amarillo por lo que compró y rojo
> por lo que pagó. Un reporte que sólo muestra lo facturado lo llamaría
> aceptable."

**Cuentas por cobrar.** Bs 881.944 por cobrar, 39 % vencido. Bajar a *Qué deja
el crédito* y a *A quién llamar hoy*.

> "No es sólo cuánto le deben: es cuánto **le cuesta** que le deban. El crédito
> tiene un costo financiero y un incobrable, y acá se ve cuánto deja de verdad
> la venta a crédito."

**Stock del día.** 256 productos, Bs 3,4 M.

> "41 productos en cero que sí se venden y 78 por quebrar: ésa es la compra de
> esta semana. Y del otro lado, el capital parado en lo que no rota."

**Rutas — el cierre visual.** Plan por vendedor sobre el mapa.

> "Los mismos clientes del archivo, repartidos por vendedor y ordenados para
> recorrer menos. El vendedor lo ve en su teléfono, marca la visita en el
> punto, y al final del día se compara lo planificado con lo que pasó."

### Cierre (1 min)

> "Todo lo que vieron salió de **los archivos que la empresa ya tiene**. El
> siguiente paso es que traigan sus archivos a una sesión de trabajo y vean
> sus propios números. ¿Cuándo les queda?"

---

## 5. Pantalla por pantalla

Arriba de los análisis hay dos controles que valen para todas las pantallas:
el **período** y la **moneda** (bolivianos o dólares; cada monto se convierte a
la cotización **de su propio día**). Al ingresar, el portal abre la última
carga de la empresa.

### Análisis comercial

| Pantalla | Qué responde | Qué mostrar |
|---|---|---|
| **Resumen Comercial** | ¿Cómo vamos, de quién dependemos, cuánto ganamos? | Venta por mes, por categoría, top 10 de productos y clientes, venta por vendedor, menos vendidos |
| ↳ Rentabilidad | ¿Dónde está la ganancia? | Margen por categoría: casi nunca coincide con la venta. Sólo aparece si hay costo |
| ↳ Crecimiento | ¿Es un mal mes o una caída? | Variación mes a mes y estacionalidad |
| ↳ Concentración | ¿Cuánto depende de pocos? | Pareto, clases ABC, peso del top 10 |
| ↳ Eficiencia comercial | ¿Dónde se escapa el margen? | Productividad por vendedor y **deriva del precio realizado** contra la lista |
| **Fuente de volumen** | ¿Qué empujó la venta? | Un cliente grande que depende de un solo producto es más frágil de lo que parece |
| **Oportunidades** | ¿Qué le ofrezco a cada cliente? | Producto → comercios interesados, con venta potencial |
| **Pronóstico** | ¿Cuánto voy a vender? | Si la serie es corta, el sistema **lo dice** en vez de proyectar igual |
| **Segmentación** | ¿Quiénes valen más? | Alto, medio, bajo. Es calculada; el **cluster** es una decisión de la empresa |
| **Salud de Cartera** | ¿A quién estoy por perder? | Nuevos, recuperados, perdidos y **en riesgo** (los únicos rescatables) |
| **Cuentas por cobrar** | ¿Cuánto me deben y cuánto recupero? | Antigüedad, recuperable vs incobrable, quiénes deben, curva de cobro, **A quién llamar hoy**, **Qué deja el crédito** |
| **Cumplimiento** | ¿Cumplió cada cliente? | Doble semáforo facturado/cobrado; matriz cluster × semáforo con su **peso** |
| **Stock del día** | ¿Cuánto me dura, qué quiebra? | Situación del catálogo, por quebrar, capital inmovilizado |

Detalles que conviene saber decir:

- **Cumplimiento:** el cobro cuenta en el mes de la factura que salda, así
  siempre se cumple `facturado = cobrado + deuda`. Una venta al contado está
  cobrada al momento. Los cortes del semáforo (por defecto rojo < 50 %,
  amarillo < 100 %, verde desde ahí), el valor del punto y los nombres de
  cluster son de cada empresa.
- **Cuentas por cobrar:** las antigüedades se miden contra el último día con
  movimiento del archivo, no contra hoy. *Qué deja el crédito* = margen bruto −
  costo financiero − incobrable esperado: vender a crédito puede dejar menos
  que no vender.
- **Stock:** la cobertura sale de la demanda que se ve en las ventas.
  SmartDecisions lee el stock del ERP y nunca lo escribe.
- **Sin un dato, la pantalla se oculta**, no muestra ceros: un 0 % de margen
  sin costos sería mentir.

### Rutas

| Pantalla | Qué hace |
|---|---|
| **Histórico** | Lo que ya se hizo, sobre el mapa. Desde ahí se repite una ruta |
| **Planes** | Lo que viene. Se importan, se infieren de un día trabajado, se repiten, o **se arma un plan por vendedor** desde su propia cartera, se asigna y se activa |
| **Stock del día** | Lo que hay para vender hoy: existencia menos lo comprometido |
| **En vivo** | El recorrido de cada vendedor en el día |
| **Optimizar** | La ruta actual contra la optimizada, en dos mapas, con kilómetros, minutos y ahorro. Nada cambia hasta aplicarla |
| **Comparación** | Plan contra lo real: paradas cumplidas, visitas y ventas |
| **Vendedores** | Une el vendedor del archivo ("Ana", "V-017") con su usuario: así ve sólo lo suyo |
| **Clientes** | La cartera, incluidos los que los vendedores dieron de alta en la calle |
| ***Mi ruta*** (teléfono) | El plan del día del vendedor, la visita y la venta |

Una visita sólo cuenta si **el vendedor estaba ahí** (geocerca). Un lugar que
el plan no conocía no se bloquea: es un cliente nuevo y la prueba de que la
ruta debe crecer. Una venta mayor al stock disponible se rechaza.

### Factores externos y tipo de cambio

**Dólar oficial** (BCB) diario con su historia y proyección, y el **dólar
paralelo** (USDT de Binance P2P) junto a él, día por día, con la brecha.
**Factores** que se mueven (combustible, aranceles, índices) con su valor
fechado; **costo de distribución** por unidad (km ÷ rendimiento × precio del
litro, ida y vuelta). Lo que el dólar le hace a la venta y al margen se ve en
Análisis comercial › Efecto del tipo de cambio.

### Minerales

Cotización oficial quincenal y anticipada, y el escenario «vender hoy o
esperar». Hoy es el módulo de menos interés comercial.

---

## 6. Cómo entran los datos

**Cinco archivos, uno por tema.** Ventas crea el conjunto de datos; los otros
cuatro se enganchan a él y cada uno enciende su pantalla. Cada uno tiene su
plantilla en castellano con hoja de instrucciones, generada del mismo contrato
que valida el archivo.

| Archivo | Columnas mínimas | Enciende |
|---|---|---|
| **Ventas** | Fecha, Nro Factura, Cliente, Producto, Cantidad | Casi todo. Con Costo: rentabilidad. Con coordenadas: Rutas. Con Vendedor: productividad y planes por vendedor. Con condición y plazo: cobranza |
| **Cobros** | Nro Factura, Fecha Cobro, Monto Cobrado | Cuentas por cobrar y lo cobrado en Cumplimiento |
| **Stock** | Fecha, Producto, Existencia | Stock del día (análisis y Rutas) |
| **Visitas** | Fecha, Vendedor, Cliente | Comparación plan contra real; clientes que nunca compraron |
| **Objetivos** | Cliente, Periodo (`2026-03`), Objetivo | Cumplimiento |

**Tres puertas, el mismo validador:** el archivo que sube la empresa, el API
que alimenta su ERP, y el vendedor desde el teléfono (alta de cliente en la
calle). El binario no pasa por el API: sube al almacenamiento y el servicio lo
lee de ahí, así que el tamaño no es problema.

**Nada se cae por una fila mala.** Las filas con problemas se apartan con su
motivo, el resto entra, y las apartadas se descargan para corregirlas.

**El maestro de clientes** guarda una sola vez lo que describe al cliente. Un
cliente nuevo se da de alta; uno existente sólo completa lo que le faltaba,
nunca se reescribe; lo que el archivo no traiga se toma del maestro.

**Si el reporte de la empresa tiene otra forma,** la conversión la hace BearSoft
una vez (`tools/convert_sales_export.py`), y después el ERP exporta ya en
formato.

---

## 7. Pruebas que convencen en vivo

Cosas que no se creen hasta que se ven:

| Prueba | Qué pasa |
|---|---|
| Subir un archivo con una fecha `32/13/2025` | Esa fila se aparta con su motivo y las demás entran |
| Cobro de una factura sin pagos | Aparece como saldo abierto: no es un error |
| Mandar el mismo pago dos veces | No se cuenta dos veces |
| Objetivo a un cliente que nunca compró | Se conserva y aparece en cero: es el cliente que la empresa quiere activar |
| Volver a mandar un mes de objetivos con otro número | Lo corrige, no lo duplica |
| Marcar una visita lejos del cliente | Se rechaza; parado en la puerta, se acepta |
| Registrar una venta mayor que el stock | Se rechaza sin tocar el inventario |
| Ingresar con la otra empresa | No ve nada de la primera |

---

## 8. Preguntas que siempre hacen

| Pregunta | Respuesta |
|---|---|
| **¿Tengo que cargar todo?** | No. Con el archivo de ventas ya se enciende la mitad del producto; lo demás se agrega cuando lo tengan |
| **¿Y mis datos?** | Cada archivo queda en el almacenamiento de su cuenta y ninguna otra empresa lo ve, como se acaba de comprobar con las dos empresas. Sin terceros y sin entrenamiento cruzado |
| **¿Los datos de la demo son reales?** | La verdad: las dos empresas son de demostración, armadas sobre datos de ejemplo de operaciones de consumo masivo. Costo, cobros, stock y visitas son simulados para mostrar el producto completo |
| **¿Se conecta con mi ERP?** | Sí, por API, con los mismos contratos y códigos de error que el archivo |
| **¿Subo el mismo archivo dos veces?** | Lo reconoce por su contenido y no lo duplica |
| **Corregí un cliente y subí un archivo viejo** | No se pierde la corrección: una recarga completa, nunca reescribe |
| **¿Se ve en dólares?** | Sí, cada monto a la cotización de su propio día. Convertir un año entero a la tasa de hoy convertiría una devaluación en crecimiento |
| **El archivo es de marzo y lo abro en agosto** | La mora se mide contra el último día del archivo, no contra hoy |

---

## 9. Si algo falla

| Falla | Cómo recuperar |
|---|---|
| Un análisis tarda | Hablar mientras calcula: es el momento de explicar qué hace. Con mala red, filtrar el período |
| La sesión se venció | Volver a ingresar: los datos y lo ya calculado siguen ahí |
| El mapa no carga | Depende de OSRM público. Pasar a Cobros y volver; si insiste, mostrar la captura |
| Una pantalla dice que falta un archivo | Es normal: ese módulo necesita su propio archivo |
| Sin internet | Ir a las capturas. No improvisar con la consola |
