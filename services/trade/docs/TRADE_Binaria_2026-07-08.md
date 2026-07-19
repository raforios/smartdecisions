# TRADE — Respuesta a observaciones y nuevas funcionalidades

**Cliente:** BINARIA
**Fecha:** 2026-07-08
**Módulo:** TRADE
**Colección Postman:** `TRADE_Collection.json` — versión **V2.2**
**Migración SQL:** `migrations/2026_07_08_binaria_replenishment_detail_inventory.sql`

Este documento responde a las observaciones enviadas por BINARIA sobre Reposiciones,
Puntos Promocionales, Acciones de la Competencia e Inventarios, y detalla los cambios
implementados en el microservicio TRADE. Cada endpoint nuevo o modificado está disponible
en la colección de Postman V2.2 con ejemplos listos para probar.

---

## 1. Resumen ejecutivo

| Tema | Estado |
|---|---|
| Reposición: registro por producto (repuesto sí/no) | Implementado |
| Reposición: listado con filtros (incluye user_id) | Implementado |
| Puntos promocionales: error 500 al guardar | Corregido (servidor + formato de request) |
| Puntos promocionales: listado | Implementado |
| Competencia: pos_id opcional | Ya disponible |
| Competencia: latitud / longitud | Ya disponible |
| Competencia: listado | Implementado |
| Inventario de impulsos: listado con inventory_type | Implementado |
| Inventario de reposiciones: registro línea-libre (lote/vencimiento) | Implementado |
| Inventario de reposiciones: último por PDV | Implementado |
| Inventario de reposiciones: listado | Implementado |

---

## 2. Aclaración conceptual sobre inventarios

Es importante alinear el modelo, porque hay una diferencia respecto a lo que indica el correo.

**El inventario de reposiciones NO vive en `t_pos_inventory`.** En la iteración de junio (iter5)
se decidió que el conteo físico de impulsos y el conteo de reposiciones son procesos con
semánticas distintas. Por eso hoy conviven **dos inventarios**:

- **Inventario de Impulsos** — `t_trade_impulse_inventory_start` / `_end`. Un conteo inicial y
  uno de cierre por visita, **una fila por producto** con desglose SALA / ALMACÉN en columnas
  (`quantity_in_room` / `quantity_in_warehouse`). La diferencia inicial − cierre debe igualar
  las ventas del día.

- **Inventario de Reposiciones** — `t_trade_replenishment_inventory` (nueva tabla, 2026-07-08).
  Es **línea-libre**: el mismo producto puede aparecer en varias filas, cada una con su propia
  cantidad, lote, vencimiento y ubicación. Pensado para el reporte de fecha corta.

Esta separación mantiene limpio el inventario de impulsos (control de ventas) y da a
reposiciones la flexibilidad de lotes/vencimientos que ustedes necesitan.

> **Nota respecto a iter5:** en la iteración anterior habíamos *unificado* el inventario y
> eliminado la tabla `t_trade_replenishment_inventory`. El inventario de **Impulsos sigue
> unificado y no cambia**. Lo que se re-introduce ahora es una tabla **dedicada y distinta**
> para Reposiciones, con estructura línea-libre, porque el modelo unificado (una fila por
> producto) no permitía registrar el mismo producto en varios lotes/vencimientos, que es
> justamente lo que ustedes pidieron. También se reactiva el endpoint
> `POST /v1/replenishment/visit/{attendance_id}/inventory` (que en iter5 se había eliminado),
> apuntando ahora a esta tabla dedicada.

### Confirmaciones a sus preguntas

- **"Available stock per product at a POS"** (`GET /pos/{pos_id}/stock`): **sí, corresponde a
  Impulsos.** Si la visita más reciente está abierta usa `inventario_inicial − ventas`; si está
  cerrada usa el `inventario_de_cierre`.
- **"Latest impulse inventory for POS"** (`GET /pos/{pos_id}/inventory/latest`): también es de
  Impulsos; devuelve el último snapshot (inicial o de cierre) con el flag `inventory_type`.

---

## 3. Reposición — registro por producto

El reporte de reposición ahora acepta el **detalle por producto**, marcando si cada producto
fue repuesto o no. Se conservan cantidad y comentario por producto (por si se necesitan luego).

**Endpoint:** `POST /v1/replenishment/visit/{attendance_id}/report`

```json
{
  "company_id": 1,
  "client_company_id": 7,
  "pos_id": 42,
  "comments": "Reposición ejecutada con éxito en góndola principal.",
  "reviewed": false,
  "details": [
    { "product_sku": "ABC.001.002.003.01", "replaced": true,  "quantity": 12, "comments": "Cerveza en lata repuesta" },
    { "product_sku": "ABC.001.002.003.02", "replaced": false }
  ]
}
```

- `details` es **opcional** (las llamadas existentes sin detalle siguen funcionando).
- `replaced` es el "repuesto sí/no" por producto. `quantity` y `comments` son opcionales.
- El listado de reportes devuelve ahora también este detalle.

**Listado:** `GET /v1/replenishment/reports` — se agregaron los filtros **`user_id`** y
**`pos_id`** (además de los ya existentes: `company_id`, `client_company_id`, `attendance_id`,
`reviewed`, `date_from`, `date_to`). `user_id` y `pos_id` se resuelven a través de la asistencia
de la visita.

---

## 4. Puntos Promocionales

### 4.1 El error 500 al guardar — causa y solución

Se identificaron **dos causas distintas**:

1. **Error del servidor (corregido):** `Object of type time is not JSON serializable`. Los
   campos `opening_time` / `closing_time` son de tipo hora y no se estaban serializando al
   registrar el evento de auditoría. **Ya está corregido en el servidor.**

2. **Formato del request (de su lado):** el segundo error
   `"Input should be a valid dictionary or object to extract fields from"` ocurre cuando el
   body se envía como **cadena de texto** en vez de objeto JSON. Debe enviarse como objeto con
   el header **`Content-Type: application/json`**.

**Forma correcta del request:**

```
POST /v1/replenishment/complementary/visit/{attendance_id}/promo-point
Header: Content-Type: application/json
```

```json
{
  "company_id": 1,
  "client_company_id": 2,
  "pos_id": 1,
  "opening_time": "09:00",
  "closing_time": "13:00",
  "description": "Mesa frente a la entrada con vendedora externa. Materiales: roll-up, samples.",
  "comments": "Buena afluencia."
}
```

- IDs como enteros; horas en formato `HH:MM` o `HH:MM:SS`.
- En la colección Postman V2.2 el request 6.5 ya trae el header correcto.

### 4.2 Listado de puntos promocionales

**Endpoint:** `GET /v1/replenishment/complementary/promo-points`

Filtros opcionales: `company_id`, `client_company_id`, `pos_id`, `user_id`, `date_from`,
`date_to` (+ `limit` / `offset`). `pos_id` y `user_id` se resuelven vía la asistencia.

---

## 5. Acciones de la Competencia

- **`pos_id` opcional:** ya estaba disponible. Cuando no hay PDV asociado (`pos_id: null`),
  `location_description`, `latitude` y `longitude` pasan a ser **obligatorios**.
- **Latitud / longitud:** ya disponibles para geolocalizar la acción.
- **`client_company_id` (nuevo):** se agregó para poder filtrar el listado por marca/cliente.
  (En iter5 se había indicado que esta tabla no se modificaría; se revierte a pedido de ustedes
  para habilitar este filtro.)
- **Listado (nuevo):** `GET /v1/replenishment/complementary/competition`
  Filtros opcionales: `company_id`, `client_company_id`, `user_id`, `date_from`, `date_to`.
  (No usa `pos_id` porque las acciones de competencia no están atadas a una visita.)

---

## 6. Inventario de Impulsos — listado

**Endpoint:** `GET /v1/impulses/inventory`

- `inventory_type` es **requerido**: `START` (inicial) o `END` (cierre).
- Filtros opcionales: `company_id`, `client_company_id`, `pos_id`, `user_id`, `date_from`,
  `date_to` (+ `limit` / `offset`). `company_id`, `pos_id` y `user_id` se resuelven vía la
  asistencia, igual que el listado de ventas.

Sirve para reportes de inventario y de control de ventas (inicial − cierre = ventas).

---

## 7. Inventario de Reposiciones — línea-libre

### 7.1 Respuesta a su pregunta

> *"¿Es posible guardar más de una línea para un mismo producto, con diferentes cantidades y
> vencimientos (no se usa el product_id como llave)?"*

**Sí.** La nueva tabla `t_trade_replenishment_inventory` es línea-libre: cada línea lleva su
propia `quantity`, `batch_number`, `expiration_date` y `location` (`SALA` / `ALMACEN`), y **no**
usa `product_id` como llave. Así se pueden diferenciar lotes y vencimientos por producto para
alertas y reportes de fecha corta, sin necesidad de un detalle por unidad existente.

### 7.2 Registro

**Endpoint:** `POST /v1/replenishment/visit/{attendance_id}/inventory`

```json
{
  "company_id": 1,
  "client_company_id": 7,
  "pos_id": 42,
  "items": [
    { "product_sku": "ABC.001.002.003.01", "quantity": 12, "batch_number": "1234567890", "expiration_date": "2026-06-30", "location": "SALA" },
    { "product_sku": "ABC.001.002.003.01", "quantity": 8,  "batch_number": "1234568522", "expiration_date": "2026-07-10", "location": "SALA" },
    { "product_sku": "ABC.001.002.003.01", "quantity": 22, "batch_number": "1234568522", "expiration_date": "2026-07-10", "location": "ALMACEN" },
    { "product_sku": "ABC.001.002.003.01", "quantity": 18, "batch_number": "1234568522", "expiration_date": "2026-07-15", "location": "ALMACEN" }
  ]
}
```

El ejemplo replica exactamente el caso del correo: el mismo producto en 4 líneas con distintos
lotes, vencimientos y ubicaciones. `expiration_date` en formato `YYYY-MM-DD`.

### 7.3 Último inventario de reposición por PDV

**Endpoint:** `GET /v1/replenishment/pos/{pos_id}/inventory/latest`

Devuelve todas las líneas del último inventario de reposición registrado en el PDV, con el
detalle de producto + lote + vencimiento + ubicación.

### 7.4 Listado de inventarios de reposición

**Endpoint:** `GET /v1/replenishment/inventory`

Filtros opcionales: `company_id`, `client_company_id`, `pos_id`, `user_id`, `date_from`,
`date_to` (+ `limit` / `offset`). Incluye el detalle de lotes/vencimientos por línea.

---

## 8. Migraciones de base de datos requeridas

Para desplegar estos cambios en el ambiente de BINARIA se requiere aplicar:

1. **Nueva tabla** `t_trade_replenishment_report_details` — detalle por producto del reporte de
   reposición (Sección 3).
2. **Nueva columna** `t_trade_complementary_competition.client_company_id` (nullable) — filtro
   por marca/cliente en competencia (Sección 5).
3. **Nueva tabla** `t_trade_replenishment_inventory` — inventario de reposiciones línea-libre
   (Sección 7).

Todo lo anterior está en el script listo para aplicar:
`migrations/2026_07_08_binaria_replenishment_detail_inventory.sql`. Estamos en fase de pruebas;
coordinar antes de aplicar en cualquier ambiente con datos productivos.

---

## 9. Endpoints — referencia rápida

| Método | Endpoint | Descripción |
|---|---|---|
| POST | `/v1/replenishment/visit/{attendance_id}/report` | Reporte de reposición con detalle por producto |
| GET | `/v1/replenishment/reports` | Listado de reportes (+ filtros user_id / pos_id) |
| POST | `/v1/replenishment/complementary/visit/{attendance_id}/promo-point` | Punto promocional (requiere Content-Type: application/json) |
| GET | `/v1/replenishment/complementary/promo-points` | Listado de puntos promocionales |
| POST | `/v1/replenishment/complementary/competition` | Reporte de competencia (+ client_company_id) |
| GET | `/v1/replenishment/complementary/competition` | Listado de reportes de competencia |
| GET | `/v1/impulses/inventory` | Listado de inventario de impulsos (START / END) |
| POST | `/v1/replenishment/visit/{attendance_id}/inventory` | Inventario de reposiciones (línea-libre) |
| GET | `/v1/replenishment/pos/{pos_id}/inventory/latest` | Último inventario de reposición por PDV |
| GET | `/v1/replenishment/inventory` | Listado de inventario de reposiciones |

Todos los endpoints están en la colección Postman **TRADE Service - V2.2** con ejemplos.

---

## 10. Guía de pruebas en Postman (V2.2)

Paso a paso para validar los cambios de esta entrega. Todos los requests referenciados están
en la colección **TRADE Service - V2.2**.

### 10.0 Antes de empezar

1. **Aplicar la migración SQL** en el ambiente de pruebas:
   `migrations/2026_07_08_binaria_replenishment_detail_inventory.sql`. Verificar luego que
   existan las tablas `t_trade_replenishment_report_details` y `t_trade_replenishment_inventory`
   y la columna `t_trade_complementary_competition.client_company_id`.
2. **Importar** la colección V2.2 y configurar el environment (URL base, credenciales, IDs).
3. **Login:** ejecutar `0. Auth → 0.1 Login` para que Postman guarde el `auth_token`.
4. **Pre-requisitos de datos** (los registros validan surtido y visita activa):
   - Producto asignado al PDV — `1.9.1 Create Assignment`.
   - Visita abierta — `4. Execution Cycle → 4.1.1 Check-In` (guarda `attendance_id`).

| Variable | Uso |
|---|---|
| `company_id` | Compañía ejecutora |
| `client_company_id` | Compañía cliente (marca) |
| `pos_id` | PDV de la visita |
| `user_id` | Operador |
| `product_sku` | SKU asignado al PDV |
| `attendance_id` | Visita activa (del check-in) |

### 10.1 Reposición con detalle por producto

- Postman → `6. Replenishment Activities → 6.1 Success Report`. Ajustar los `product_sku` en
  `details` a SKUs asignados al PDV.
- **Resultado esperado:** `201 Created`; la respuesta incluye `details[]` con `replaced`,
  `quantity` y `comments` por producto.
- **Casos para el test plan:**
  - Enviar el body **sin** `details` → se registra igual (compatibilidad hacia atrás).
  - Un `product_sku` no asignado al PDV → `400`.
  - Verificar que `List Replenishment Reports` devuelve el detalle registrado.

### 10.2 Punto Promocional (corrección del 500)

- Postman → `6.5 Promo Point`. **Verificar que el request incluye el header
  `Content-Type: application/json`** (ya viene así en V2.2).
- **Resultado esperado:** `201 Created` (antes daba 500 por el tipo `time`; corregido en el
  servidor).
- **Casos para el test plan:**
  - Reproducir el error histórico: enviar el body como texto/cadena sin
    `Content-Type: application/json` → `"Input should be a valid dictionary…"` (así queda claro
    que era el formato del request).
  - `closing_time` ≤ `opening_time` → `400`.
- Postman → `6.10 List Promo Points` con filtros `company_id`, `pos_id`, `user_id` (habilitar
  los que se quieran probar).

### 10.3 Acciones de la Competencia

- Postman → `6.6 Competition Report` (el body ya trae `client_company_id`).
- **Casos:** con `pos_id: null` deben venir `latitude`, `longitude` y `location_description`
  (si faltan → `400`).
- Postman → `6.11 List Competition Reports` filtrando por `client_company_id` — debe devolver
  solo los de esa marca.

### 10.4 Inventario de Reposiciones (línea-libre)

- Postman → `6.7 Register Replenishment Inventory (line-free)`. El ejemplo trae **4 líneas del
  mismo producto** con distinto lote / vencimiento / ubicación.
- **Resultado esperado:** `201 Created` con las 4 líneas (verifica que se guardan todas, sin
  colapsar por producto).
- Postman → `6.8 Latest Replenishment Inventory by POS` → devuelve las 4 líneas del último
  inventario del PDV con su lote/vencimiento.
- Postman → `6.9 List Replenishment Inventory` con filtros `company_id`, `pos_id`, `user_id`,
  `date_from`, `date_to`.

### 10.5 Inventario de Impulsos — listado

- Postman → `5. Impulses Activities → 5.6 List Impulse Inventory (START/END)`.
- `inventory_type` es **requerido**: probar `START` y `END`. Sin el parámetro → `422`.
- Filtros opcionales `company_id`, `client_company_id`, `pos_id`, `user_id`, `date_from`,
  `date_to`.

### 10.6 Listado de reportes de reposición (filtros nuevos)

- Postman → `List Replenishment Reports` — habilitar los filtros `pos_id` y `user_id` (nuevos)
  y verificar que acotan por la asistencia de la visita.

### 10.7 Cómo reportar un problema

Al reportar, incluir: (1) endpoint exacto (método + URL), (2) body enviado (sin tokens),
(3) status HTTP, (4) JSON de respuesta completo, (5) hora aproximada (UTC) para correlacionar
con logs. Asunto del correo: **"TRADE 2026-07-08 — <tema>"**, a **raforios@gmail.com**.
