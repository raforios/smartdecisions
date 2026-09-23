# Billing Service

Microservicio de **facturación** de BearSoft. Registra lo que un comercio
compra y lo que vende, y mantiene la estantería al día con cada movimiento.

El primer vertical son las **farmacias**, y por eso el modelo gira alrededor
del **lote**: un medicamento no se vende por caja indistinta, se vende por
partida, y cada partida trae su propio costo, su propio precio de venta y su
propia fecha de vencimiento. El nombre del servicio es genérico a propósito:
una ferretería o una distribuidora entran aquí sin cambiar el modelo.

Se vende **solo o junto a SmartDecisions**. Por sí mismo es el sistema de
mostrador de un comercio; junto al resto, sus ventas son otra fuente de datos
para el análisis comercial.

---

## Por qué el lote manda

Tres decisiones del negocio explican casi todo el código:

1. **El costo y el precio son del lote, no del producto.** El laboratorio o el
   importador los fija en cada compra, así que dos cajas del mismo
   medicamento en el mismo estante pueden costar y valer distinto. El catálogo
   muestra el precio del lote que sale próximo, que es lo que dice la etiqueta.
2. **Sale primero lo que vence antes (FEFO).** Es PEPS con el reloj en vez del
   calendario de llegada. Un lote sin fecha se vende al final: una fecha
   desconocida nunca debe adelantarse a una caja que está por vencer.
3. **Una línea puede abarcar dos lotes, y cada uno cobra su precio.** Si la
   partida más próxima no cubre la venta, el resto sale de la siguiente. Por eso
   la línea guarda sus *asignaciones* —qué unidades salieron de qué lote— y no
   sólo una cantidad.

Esa última decisión es la que hace posible **anular** una nota: las unidades
vuelven exactamente a los lotes de los que salieron, con su costo y su
vencimiento. Devolverlas "al stock" sin más recostaría la estantería en
silencio.

---

## Stack

Python 3.14 · FastAPI + Mangum sobre Lambda · Pydantic V2 · DynamoDB (boto3) ·
pytest + moto. Sin base relacional.

## Estructura

```
billing/
├── models/billing.py          Ítems de DynamoDB y nombres de tabla
├── schemas/billing.py         DTOs y códigos de error
├── services/
│   ├── billing.py             Catálogo, parámetros del comercio y numeración
│   ├── billing_stock.py       Lotes, FEFO y el descuento transaccional
│   ├── billing_sales.py       Nota de venta: emitir, anular, listar
│   ├── billing_purchases.py   Nota de compra / recepción
│   └── billing_reports.py     Tablero de mostrador
├── controllers/billing.py
├── routes/billing.py
└── tests/test_billing.py
```

## Almacenamiento

Cinco tablas, todas particionadas por **dueño** —el comercio, tomado del
token—. El dueño es parte de cada clave y nunca un filtro posterior: un
comercio que pudiera leer la estantería de otro estaría leyendo sus márgenes.

| Tabla | Partición | Orden |
|---|---|---|
| `billing_products` | `owner` | `sku` |
| `billing_lots` | `owner` | `lot_key` = `sku#lot_id` |
| `billing_sales` | `owner` | `sale_id` (empieza con la marca de tiempo) |
| `billing_purchases` | `owner` | `purchase_id` |
| `billing_settings` | `owner` | `setting_key` |

`lot_key` agrupa los lotes de un producto, así que las partidas a vender salen
con un `begins_with` y no con un scan. El identificador de una nota empieza con
la marca de tiempo, que es lo que convierte un rango de fechas en una consulta
acotada por la clave de orden en vez de un filtro sobre toda la partición.

Las tablas se crean con `services/ci/api/create_dynamodb_tables.sh`.

---

## Endpoints

Todo bajo `/v1/billing`. Configurar el comercio, editar el catálogo, recibir
una entrega y anular una nota son de **ADMIN/MANAGER**; vender lo hace quien
está en la caja.

```
GET    /dashboard                        Tablero del mostrador
GET    /settings                         Parámetros y numeración
PUT    /settings                         (ADMIN, MANAGER)
GET    /products                         Catálogo con disponibilidad y precio
POST   /products                         (ADMIN, MANAGER)
GET    /products/{sku}
PATCH  /products/{sku}                   (ADMIN, MANAGER)
GET    /products/{sku}/lots              Lotes en orden de venta
PATCH  /products/{sku}/lots/{lot_id}     Reprecio del lote (ADMIN, MANAGER)
POST   /purchases                        Nota de compra (ADMIN, MANAGER)
GET    /purchases                        Por ventana de fechas
GET    /purchases/{purchase_id}
POST   /sales                            Nota de venta
GET    /sales                            Por ventana de fechas
GET    /sales/{sale_id}
POST   /sales/{sale_id}/cancel           (ADMIN, MANAGER)
```

### El tablero

Responde lo que pregunta un mostrador: cuánto vendí, qué me dejó, qué está por
vencer y qué se me está acabando. Vendido, costo, margen y su porcentaje,
ticket promedio, notas anuladas contadas aparte —nunca como dinero—, capital en
estantería al costo real de cada lote, lotes por vencer y ya vencidos en listas
separadas, productos bajo mínimo y los más vendidos **por monto**.

---

## Errores

El backend responde con **códigos**, nunca con frases: `INSUFFICIENT_STOCK`,
`PRODUCT_NOT_FOUND`, `DUPLICATE_LINE`, `DISCOUNTS_DISABLED`,
`SALE_ALREADY_CANCELLED`, `SETTINGS_NOT_FOUND`… La redacción es del frontend.

**Sobreventa.** El descuento de stock es una transacción de DynamoDB
condicionada a lo que queda en cada lote. Si dos cajas venden la última unidad
al mismo segundo, una recibe `INSUFFICIENT_STOCK` **antes** de que imprima el
papel: la nota no existe y la numeración no avanza.

---

## Configuración

Todo en el `.env`, requerido: `HOST`, `PORT`, `SECRET_KEY`, `ALGORITHM`,
`TARGET_TIMEZONE`, `ROOT_PATH`, las cinco `DYNAMODB_TABLE_NAME_BILLING_*` y
`BILLING_EXPIRY_ALERT_DAYS` —el plazo que mete a un lote en la alerta de
vencimientos—.

## Pruebas

```bash
python tools/verify_service.py services/billing
```

---

## Qué falta

Facturación electrónica boliviana según la **RND 11** del SIAT: firma digital,
códigos de control, CUFD/CUIS y el envío del XML por SOAP a Impuestos
Nacionales. Es la fase siguiente; hoy la nota de venta es un documento interno
del comercio, imprimible en térmica de 58 y 80 mm.
