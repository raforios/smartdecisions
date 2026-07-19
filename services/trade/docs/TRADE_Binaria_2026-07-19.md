# TRADE — Respuesta a observaciones (Revisión 3) y guía de pruebas

**Cliente:** BINARIA
**Fecha:** 2026-07-19
**Módulo:** TRADE
**Colección Postman:** `TRADE_Collection.json` — versión **V2.3**
**Migraciones SQL:**
- `migrations/2026_07_17_binaria_review3_phaseA.sql` (Fase A — `sku_quantity`)
- `migrations/2026_07_17_binaria_review3_phaseB_bandeos.sql` (Fase B — rediseño de bandeos)

Este documento responde al correo de revisión (Paula, sobre la versión del 2026-07-08) que
cubre Inventario de Impulsos, Reposiciones y Bandeos. El trabajo se entregó en **dos fases**:
**Fase A** (campos que faltaban en las respuestas + `sku_quantity` + listado global de entregas)
y **Fase B** (rediseño del flujo de bandeos: Planificar → Recibir → Devolver + listados).

Cada endpoint nuevo o modificado está en la colección **V2.3** con ejemplos listos.

---

## 1. Resumen ejecutivo

| # | Observación | Estado |
|---|---|---|
| 1 | Impulsos: inventario inicio devolvía solo `quantity` | Agregados `batch_number`, `expiration_date`, `quantity_in_room`, `quantity_in_warehouse` |
| 2 | Impulsos: inventario final, mismos campos faltantes | Ídem |
| 3 | Impulsos: listado de inventarios sin `company_id`/`pos_id`/`user_id` | Agregados a la respuesta |
| 4 | Reposiciones: listado de puntos promocionales sin `pos_id`/`user_id` | Agregados |
| 5 | Reposiciones: listado de reposiciones sin `pos_id`/`user_id` | Agregados |
| 6 | Reposiciones: registro entrega proveedor sin `company_id` | Agregado (+ `pos_id`/`user_id`) |
| 7 | Reposiciones: entregas por visita sin `company_id` | Agregado (+ `pos_id`/`user_id`) |
| 8 | Reposiciones: faltaba listado global de entregas | **Nuevo** `GET /replenishment/reception` |
| 9 | Inventario de reposiciones (registro) sin `company_id` | Agregado (+ `pos_id`/`user_id`) |
| 10 | Inventario de reposiciones: último por PDV sin `company_id` | Agregado (+ `pos_id`/`user_id`) |
| 11 | "List all inventory items for a POS" | Ya no existe (reemplazado por el listado con filtros) |
| 12 | Inventario de reposiciones: listado sin `client_company_id`/`pos_id`/`user_id` | Agregados |
| 13-15 | Promociones: falta `sku_quantity` por SKU (create/list/get) | Agregado en request y respuesta (+ `product_sku`) |
| 16 | Bandeos: falta paso Planificar | **Nuevo** `POST /complementary/bandeo/plan` |
| 17 | Recibir: no debe persistir `qty_planned`; pedir `bandeo_id`; `pos_id` en respuesta | Rediseñado |
| 18 | Devolver: pedir `attendance_id`; usar `product_sku`; `pos_id` en respuesta | Rediseñado |
| 19 | Get bandeo: falta `pos_id`, `promotion_quantity`, `planned_at`, detalle completo | Agregados |
| 20 | List bandeos por visita: `details`/`photos` vacíos; faltan campos | Corregido + campos |
| 21 | Bandeos: falta listado global filtrable | **Nuevo** `GET /complementary/bandeos` |

---

## 2. Nota importante sobre catálogos y `unit_of_measure`

Se confirmó que los valores de catálogo (por ejemplo `unit_of_measure`) **vienen en el request**
porque provienen de otro sistema. Por eso `unit_of_measure` pasó a ser un **ID entero** (antes
era texto). El backend lo acepta y lo devuelve tal cual; no valida contra un catálogo interno.

---

## 3. Impulsos — inventario (obs. 1, 2, 3)

### 3.1 Inventario inicio / final por visita

**Endpoints:**
`GET /v1/impulses/visit/{attendance_id}/inventory-start`
`GET /v1/impulses/visit/{attendance_id}/inventory-end`

Cada línea de `items` ahora incluye los datos que se registraron:

```json
{
  "attendance_id": 55, "pos_id": 42, "inventory_type": "start",
  "items": [
    {
      "product_id": 10, "product_sku": "ABC.001.002.003.01", "product_name": "Cerveza lata",
      "batch_number": "1234567890", "expiration_date": "2026-06-30T00:00:00",
      "quantity_in_room": 12, "quantity_in_warehouse": 22, "quantity": 34,
      "observations": null
    }
  ]
}
```

### 3.2 Listado de inventarios

**Endpoint:** `GET /v1/impulses/inventory` (`inventory_type` requerido: `START`/`END`).
Cada ítem ahora trae `company_id`, `pos_id` y `user_id` (resueltos vía la asistencia), además de
`client_company_id` y el detalle de lote/vencimiento/ubicación.

---

## 4. Reposiciones — campos que faltaban (obs. 4, 5, 6, 7, 9, 10, 12)

Todos estos listados/registros resuelven `company_id` / `pos_id` / `user_id` **a través de la
asistencia de la visita**, y ahora los exponen en la respuesta:

| Endpoint | Campos agregados |
|---|---|
| `GET /v1/replenishment/reports` | `pos_id`, `user_id` |
| `GET /v1/replenishment/complementary/promo-points` | `pos_id`, `user_id` |
| `POST /v1/replenishment/visit/{attendance_id}/reception` | `company_id`, `pos_id`, `user_id` |
| `GET /v1/replenishment/visit/{attendance_id}/reception` | `company_id`, `pos_id`, `user_id` |
| `POST /v1/replenishment/visit/{attendance_id}/inventory` | `company_id`, `pos_id`, `user_id` |
| `GET /v1/replenishment/pos/{pos_id}/inventory/latest` | `company_id`, `pos_id`, `user_id` |
| `GET /v1/replenishment/inventory` | `company_id`, `client_company_id`, `pos_id`, `user_id` |

> Los request de estos endpoints **no cambian**; solo se enriqueció la respuesta.

### 4.1 Nuevo: listado global de entregas de proveedor (obs. 8)

**Endpoint:** `GET /v1/replenishment/reception`

Listado de todas las entregas de proveedor (recepciones) de todas las visitas, con filtros
opcionales: `company_id`, `client_company_id`, `pos_id`, `user_id`, `date_from`, `date_to`
(+ `limit`/`offset`). Complementa al listado por visita, que sigue disponible.

---

## 5. Promociones — `sku_quantity` por SKU (obs. 13, 14, 15)

Cada SKU de una promoción (bandeo) ahora lleva **`sku_quantity`**: la cantidad de ese SKU que
compone una unidad de la promoción (ej.: 12 salchichas por paquete "san juanero").

**Crear:** `POST /v1/impulses/promotions`

```json
{
  "company_id": 1, "name": "Pack San Juanero",
  "start_date": "2026-06-01", "end_date": "2026-06-30",
  "details": [
    { "product_sku": "ABC.001.002.003.01", "sku_quantity": 12 },
    { "product_sku": "ABC.001.002.003.02", "sku_quantity": 1 }
  ]
}
```

**Listar / Obtener:** `GET /v1/impulses/promotions` y `GET /v1/impulses/promotions/{id}` ahora
devuelven, por cada línea de `details`, `product_sku` y `sku_quantity`.

`sku_quantity` es la base para calcular la demanda planificada del bandeo (ver Sección 6):
`qty_planned = promotion_quantity * sku_quantity`.

---

## 6. Bandeos — nuevo flujo Planificar → Recibir → Devolver (obs. 16-21)

El bandeo ahora se **planifica antes de la visita** (llave POS + fecha), y luego se **recibe** y
**devuelve** dentro de la visita. Estados: `PENDING` (planificado) → `RECEIVED` → `RETURNED`.

### 6.1 Paso 1 — Planificar (nuevo)

**Endpoint:** `POST /v1/replenishment/complementary/bandeo/plan` (pre-visita, sin `attendance_id`)

```json
{
  "company_id": 1, "client_company_id": 7,
  "pos_id": 42, "planned_date": "2026-05-15T09:00:00",
  "promotion_id": 9, "promotion_quantity": 10,
  "comments": "Planificación del bandeo para la visita.",
  "details": [
    { "product_sku": "ABC.001.002.003.01", "unit_of_measure": 1 }
  ]
}
```

- Crea el bandeo con `status=PENDING` y devuelve el **`bandeo_id`** (el test de Postman lo guarda
  en el environment).
- `quantity_planned` **no se envía**: el servidor lo calcula por SKU como
  `promotion_quantity * sku_quantity` (de la promoción).
- Llave de unicidad: `(pos_id, planned_date, promotion_id)` — reintentar el mismo plan → `409`.

### 6.2 Paso 2 — Recibir (`PENDING → RECEIVED`)

**Endpoint:** `POST /v1/replenishment/complementary/visit/{attendance_id}/bandeo/{bandeo_id}/receive`

```json
{
  "company_id": 1, "pos_id": 42,
  "comments": "Recepción de productos del bandeo en sala.",
  "details": [
    { "product_sku": "ABC.001.002.003.01", "quantity_received": 30 }
  ]
}
```

- Ahora pide **`bandeo_id`** en la URL (el que devolvió Planificar) y vincula la visita
  (`attendance_id`).
- **Ya no persiste `quantity_planned`** (viene fijado del plan); solo registra `quantity_received`
  por SKU.
- El bandeo debe estar en `PENDING`; si no → `400`.

### 6.3 Paso 3 — Devolver (`RECEIVED → RETURNED`)

**Endpoint:** `PATCH /v1/replenishment/complementary/visit/{attendance_id}/bandeo/{bandeo_id}/return`

```json
{
  "details": [
    { "product_sku": "ABC.001.002.003.01", "quantity_used": 24, "quantity_returned": 6, "observations": null }
  ]
}
```

- Ahora pide también **`attendance_id`** en la URL, y las líneas se identifican por
  **`product_sku`** (antes por `id`).
- Validaciones (igual que antes): `quantity_used`/`quantity_returned` ≤ `quantity_received`;
  `observations` obligatorio si `quantity_returned` difiere del default
  (`quantity_received - quantity_used`).

### 6.4 Consultas de bandeos

- **Por visita:** `GET /v1/replenishment/complementary/visit/{attendance_id}/bandeos` — ahora trae
  `details` (con las 4 cantidades: planeada/recibida/usada/devuelta) y `photos` **completos**
  (antes venían vacíos), más `pos_id`, `promotion_quantity`, `planned_date`.
- **Individual:** `GET /v1/replenishment/complementary/bandeo/{bandeo_id}` — funciona **con o sin
  visita abierta** (para consultas posteriores), con el mismo detalle.
- **Listado global (nuevo):** `GET /v1/replenishment/complementary/bandeos` — filtros
  `company_id`, `client_company_id`, `pos_id`, `user_id`, `status`, `date_from`, `date_to`
  (+ `limit`/`offset`). Devuelve el registro completo de cada bandeo.

Campos nuevos en la respuesta de bandeo: `pos_id`, `promotion_quantity`, `planned_date`,
`product_sku` por línea, y `unit_of_measure` como ID entero. `attendance_id` es nulo mientras el
bandeo está solo planificado.

### 6.5 Fotos del bandeo

Sin cambios: `7. Common (Utils) → Upload Photo` con `entity_type=BANDEO`,
`entity_id={{bandeo_id}}`. Se sube en el paso Devolver.

---

## 7. Migraciones de base de datos requeridas

Aplicar **en orden** en el ambiente de pruebas (coordinar antes de cualquier ambiente con datos
productivos):

1. `migrations/2026_07_17_binaria_review3_phaseA.sql`
   - `t_trade_promotion_details` + `sku_quantity` (INT NOT NULL DEFAULT 1).
2. `migrations/2026_07_17_binaria_review3_phaseB_bandeos.sql`
   - `t_trade_complementary_bandeo_header` + `pos_id`, `planned_date`, `promotion_quantity`;
     `attendance_id` pasa a NULLABLE; nueva llave única `(pos_id, planned_date, promotion_id)`.
   - `t_trade_complementary_bandeo_detail`: `unit_of_measure` de VARCHAR(20) a INT.

> El resto de las observaciones (campos `company_id`/`pos_id`/`user_id` en las respuestas) **no
> requieren cambios de base**: se resuelven por JOIN con la asistencia en la capa de servicio.

Verificación posterior sugerida:

```sql
DESCRIBE t_trade_promotion_details;               -- sku_quantity
DESCRIBE t_trade_complementary_bandeo_header;     -- pos_id, planned_date, promotion_quantity
DESCRIBE t_trade_complementary_bandeo_detail;     -- unit_of_measure INT
```

---

## 8. Endpoints — referencia rápida

| Método | Endpoint | Nota |
|---|---|---|
| GET | `/v1/impulses/visit/{attendance_id}/inventory-start` | + lote/vencimiento/sala/almacén |
| GET | `/v1/impulses/visit/{attendance_id}/inventory-end` | + lote/vencimiento/sala/almacén |
| GET | `/v1/impulses/inventory` | + company/pos/user en la respuesta |
| POST | `/v1/impulses/promotions` | + `sku_quantity` por SKU |
| GET | `/v1/impulses/promotions` · `/{id}` | + `product_sku` y `sku_quantity` |
| GET | `/v1/replenishment/reports` | + pos/user |
| GET | `/v1/replenishment/complementary/promo-points` | + pos/user |
| POST/GET | `/v1/replenishment/visit/{attendance_id}/reception` | + company/pos/user |
| **GET** | **`/v1/replenishment/reception`** | **Nuevo — listado global de entregas** |
| POST | `/v1/replenishment/visit/{attendance_id}/inventory` | + company/pos/user |
| GET | `/v1/replenishment/pos/{pos_id}/inventory/latest` | + company/pos/user |
| GET | `/v1/replenishment/inventory` | + client/pos/user |
| **POST** | **`/v1/replenishment/complementary/bandeo/plan`** | **Nuevo — Planificar** |
| POST | `/v1/replenishment/complementary/visit/{attendance_id}/bandeo/{bandeo_id}/receive` | Recibir (URL cambió) |
| PATCH | `/v1/replenishment/complementary/visit/{attendance_id}/bandeo/{bandeo_id}/return` | Devolver (URL cambió) |
| GET | `/v1/replenishment/complementary/visit/{attendance_id}/bandeos` | Por visita (detalle completo) |
| GET | `/v1/replenishment/complementary/bandeo/{bandeo_id}` | Individual |
| **GET** | **`/v1/replenishment/complementary/bandeos`** | **Nuevo — listado global de bandeos** |

---

## 9. Guía de pruebas en Postman (V2.3)

### 9.0 Antes de empezar

1. **Aplicar las 2 migraciones** de la Sección 7 y verificar las columnas.
2. **Importar** la colección **TRADE Service - V2.3** y configurar el environment.
3. **Login:** `0. Auth → 0.1 Login` (guarda `auth_token`).
4. **Pre-requisitos de datos:**
   - Producto asignado al PDV — `1.9.1 Create Assignment`.
   - Promoción con `sku_quantity` — `5.1 Create Promotion` (guarda `promotion_id`).
   - Visita abierta — `4.1.1 Check-In` (guarda `attendance_id`).

| Variable | Uso |
|---|---|
| `company_id`, `client_company_id` | Compañía ejecutora / cliente (marca) |
| `pos_id`, `user_id` | PDV / operador de la visita |
| `product_sku` | SKU asignado al PDV |
| `promotion_id` | Promoción (bandeo) — de `5.1` |
| `attendance_id` | Visita activa (del check-in) |
| `bandeo_id` | Se rellena automáticamente al Planificar (`6.4.0`) |

### 9.1 Impulsos — inventario con detalle

- `5. Impulses → 5.2b GET Inventory Start by Attendance` y `5.4b GET Inventory End by Attendance`:
  verificar que cada ítem trae `batch_number`, `expiration_date`, `quantity_in_room`,
  `quantity_in_warehouse`.
- `5.6 List Impulse Inventory (START/END)`: verificar `company_id`, `pos_id`, `user_id` en cada ítem.

### 9.2 Promociones con `sku_quantity`

- `5.1 Create Promotion` con `sku_quantity` por SKU → `201`.
- `GET /impulses/promotions/{id}`: verificar que `details[]` trae `product_sku` y `sku_quantity`.

### 9.3 Reposiciones — campos nuevos y listado global

- Ejecutar los listados (`reports`, `promo-points`, `inventory`) y los registros (`reception`,
  `inventory`, `latest`) y verificar `company_id`/`pos_id`/`user_id` según la tabla de la Sección 4.
- **Nuevo:** `6.9 List Supplier Receptions (global)` → listado global de entregas con filtros.

### 9.4 Bandeos — flujo completo

Secuencia en `6. Replenishment → 6.4 Bandeo (Planificar/Recibir/Devolver)`:

1. **`6.4.0 Plan bandeo (Planificar)`** → `201`, guarda `bandeo_id`. `status=PENDING`, cada línea
   con `quantity_planned = promotion_quantity * sku_quantity`.
2. **`6.4.1 Receive bandeo (Recibir)`** (usa `attendance_id` + `bandeo_id`) → `200`,
   `status=RECEIVED`, `quantity_received` registrado.
3. **`6.4.2 Return bandeo (Devolver)`** (usa `attendance_id` + `bandeo_id`, líneas por
   `product_sku`) → `200`, `status=RETURNED`.
4. **`6.4.3 List bandeos for visit`** → verificar `details` (4 cantidades) y `photos` completos,
   más `pos_id`, `promotion_quantity`, `planned_date`.
5. **`6.4.4 Get bandeo by id`** → mismo detalle; probar también con la visita ya cerrada.
6. **`6.4.5 List all bandeos (global)`** → filtrar por `company_id`, `status`, etc.

**Casos para el test plan:**
- Reintentar Planificar con la misma `(pos_id, planned_date, promotion_id)` → `409`.
- Recibir un bandeo que no está en `PENDING` → `400`.
- Devolver con `attendance_id` distinto al que recibió el bandeo → `400`.
- Devolver con `quantity_used > quantity_received` → `400`.
- `quantity_returned` distinto del default sin `observations` → `400`.

### 9.5 Cómo reportar un problema

Al reportar, incluir: (1) endpoint exacto (método + URL), (2) body enviado (sin tokens),
(3) status HTTP, (4) JSON de respuesta completo, (5) hora aproximada (UTC) para correlacionar con
logs. Asunto del correo: **"TRADE 2026-07-19 — <tema>"**, a **raforios@gmail.com**.
