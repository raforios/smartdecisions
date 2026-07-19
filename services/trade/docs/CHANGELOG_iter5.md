# TRADE — Iteración 5 (Reposiciones + Inventario unificado)

**Fecha:** 2026-06-20
**Cliente:** Binaria
**Contacto:** Rafael Ríos Bascón — raforios@gmail.com
**Microservicio:** TRADE (`/v1/replenishment/*` + `/v1/impulses/*`)
**Migración SQL:** `migrations/2026_06_20_binaria_iter5_replenishment.sql`

---

## 1. Resumen ejecutivo

Esta iteración cubre las observaciones del email del equipo de Binaria
sobre el módulo de **Reposiciones** + la **unificación del modelo de
inventario** entre Impulsos y Reposiciones (Binaria lo solicitó
explícitamente: "que sean las mismas tablas").

Cambios principales:

1. **Inventario unificado.** La tabla `t_trade_replenishment_inventory`
   se elimina. Tanto Impulsos como Reposiciones operan ahora sobre
   `t_trade_impulse_inventory_start` y `t_trade_impulse_inventory_end`,
   que reciben los campos nuevos (`batch_number`, `expiration_date`,
   `quantity_in_room`, `quantity_in_warehouse`, `client_company_id`).
   Razón funcional: el inventario es un solo concepto físico que
   transita por dos procesos (Impulsos lo mueven, Reposiciones lo
   restituyen).
2. **Compañía cliente** (`client_company_id`) presente en todos los
   reportes de Reposiciones.
3. **Campo `reviewed`** en el reporte de reposición.
4. **Bug corregido en recepción de proveedor** — faltaban
   `batch_number` y `expiration_date`.
5. **3 endpoints `GET` nuevos** para consulta paginada.

> **Nota:** estamos en fase de pruebas, no en producción — la migración
> incluye `DROP TABLE t_trade_replenishment_inventory` y cambio de
> unique constraint. Si en el ambiente de Binaria ya hubiera datos
> productivos que necesiten migrarse, avisar antes de aplicar el script.

---

## 2. Respuesta punto a punto a las observaciones

### General

> *"Es necesario completar la compañía cliente en los puntos donde no se
> haya definido."*

✅ **Resuelto.** Se agregó `client_company_id` (entero opcional) en:

- `ReplenishmentReport`
- `ReplenishmentReception`
- `ComplementaryBandeo`
- `ComplementaryPromoPoint`
- `ImpulseInventoryStart` y `ImpulseInventoryEnd` (compartidos con Reposiciones).

> *"Asumimos que grupo de trabajo, rutas y planificación es lo mismo,
> usando el objeto REPOSICION para diferenciar."*

✅ **Confirmado.** Esa lógica se aplica vía `attendance_id` (proviene
del módulo LOCALIZATION). No hace falta cambio.

---

### Registrar reposición

> *"Falta la compañía cliente y el campo 'Revisado' de tipo si/no."*

✅ `client_company_id` opcional + `reviewed` booleano (default `false`).

> *"Nos está faltando un EP para buscar los registros de reposiciones."*

✅ **Endpoint nuevo:** `GET /v1/replenishment/reports`

Filtros opcionales (query string): `company_id`, `client_company_id`,
`attendance_id`, `reviewed`, `date_from`, `date_to`, `limit` (default 50,
máx 500), `offset`.

Respuesta:

```json
{
    "items": [
        {
            "id": 123,
            "company_id": 1,
            "client_company_id": 7,
            "attendance_id": 456,
            "comments": "...",
            "reviewed": false,
            "photos": [],
            "created_at": "2026-06-20T10:15:00"
        }
    ],
    "total": 142
}
```

---

### Inventario de productos (UNIFICACIÓN con Impulsos)

> *"¿Cómo está previsto diferenciar si el producto está en sala o en
> almacén?"*
> *"Esperaba que serían las mismas tablas del inventario en Impulsos
> con la adición de lotes y vencimientos."*

✅ **Resuelto siguiendo la sugerencia de Binaria.**

`t_trade_replenishment_inventory` se elimina. La lógica vive ahora en
`t_trade_impulse_inventory_start` y `t_trade_impulse_inventory_end`,
ampliadas con:

- `client_company_id` — marca/producto.
- `batch_number` (nullable) — lote.
- `expiration_date` (nullable) — fecha de vencimiento.
- `quantity_in_room` (default 0) — cantidad en sala.
- `quantity_in_warehouse` (default 0) — cantidad en almacén.
- `quantity` legacy queda nullable. El backend lo mantiene poblado como
  `quantity_in_room + quantity_in_warehouse`.

La unique constraint cambia de `(attendance_id, product_id)` a
`(attendance_id, product_id, batch_number)` — un PdV puede reportar el
mismo producto en varios lotes en la misma visita.

**Endpoints de inventario (compartidos por Impulsos y Reposiciones):**

| Método | Ruta |
|---|---|
| `POST` | `/v1/impulses/visit/{attendance_id}/inventory-start` |
| `POST` | `/v1/impulses/visit/{attendance_id}/inventory-end` |
| `GET` | `/v1/impulses/visit/{attendance_id}/inventory-start` |
| `GET` | `/v1/impulses/visit/{attendance_id}/inventory-end` |

Los antiguos `POST` y `GET /v1/replenishment/visit/{id}/inventory`
**dejan de existir**.

Ejemplo de payload nuevo (mismo body para Impulsos y Reposiciones):

```json
{
    "company_id": 1,
    "client_company_id": 7,
    "pos_id": 42,
    "items": [
        {
            "product_sku": "ABC.001.002.003.01",
            "batch_number": "LOT-2026-Q1",
            "expiration_date": "2027-03-15",
            "quantity_in_room": 24,
            "quantity_in_warehouse": 60,
            "observations": "Punta de góndola activa."
        }
    ]
}
```

**Compatibilidad hacia atrás del frontend.** Si un cliente sigue
enviando `quantity` legacy y deja los dos nuevos en cero, el backend
lo trata como "todo en sala". Esto da tiempo al frontend a migrar.

> *"¿Cuál es la lógica para registrar el ingreso / cierre de
> inventarios?"*

✅ **Aclaración.** Reposiciones ahora reusa el patrón de Impulsos:
`inventory-start` al inicio de la visita, `inventory-end` al final.
La diferencia entre apertura y cierre — combinada con las ventas — refleja
el movimiento real del stock que las Reposiciones restituyen.

---

### Registro de productos del proveedor

> *"Aquí también nos está faltando un EP para registrar los vencimientos
> de los productos que se reciben."*

🐛 **Bug.** El modelo `ReplenishmentReception` no tenía
`batch_number` ni `expiration_date`; solo `quantity_received` y
`comments`. Imposible trazar lotes.

✅ **Solución:**

- Modelo amplía con `batch_number` (varchar 50) y `expiration_date`
  (datetime), ambos opcionales.
- Payload de creación los acepta por item.
- **Endpoint nuevo de consulta:** `GET /v1/replenishment/visit/{attendance_id}/reception`
  con filtros `client_company_id`, `product_id`, `batch_number`, paginación.

Ejemplo:

```json
{
    "company_id": 1,
    "client_company_id": 7,
    "pos_id": 42,
    "items": [
        {
            "product_sku": "ABC.001.002.003.01",
            "quantity_received": 120,
            "batch_number": "LOT-2026-Q2",
            "expiration_date": "2027-09-30",
            "comments": "Recepción del proveedor X."
        }
    ]
}
```

---

## 3. Resumen de endpoints (post iter 5)

### Replenishment (`/v1/replenishment/*`)

| Método | Ruta | Estado |
|---|---|---|
| `POST` | `/visit/{attendance_id}/report` | Modificado |
| `POST` | `/visit/{attendance_id}/reception` | Modificado |
| `POST` | `/complementary/visit/{attendance_id}/bandeo` | Modificado |
| `POST` | `/complementary/visit/{attendance_id}/promo-point` | Modificado |
| `POST` | `/complementary/competition` | Sin cambios |
| `GET` | `/reports` | **Nuevo** |
| `GET` | `/visit/{attendance_id}/reception` | **Nuevo** |
| ~~`POST` / `GET`~~ | ~~`/visit/{attendance_id}/inventory`~~ | **Eliminados** → usar Impulses |

### Impulses inventory (compartido con Reposiciones)

| Método | Ruta | Estado |
|---|---|---|
| `POST` | `/v1/impulses/visit/{attendance_id}/inventory-start` | Modificado |
| `POST` | `/v1/impulses/visit/{attendance_id}/inventory-end` | Modificado |
| `GET` | `/v1/impulses/visit/{attendance_id}/inventory-start` | Devuelve campos nuevos |
| `GET` | `/v1/impulses/visit/{attendance_id}/inventory-end` | Devuelve campos nuevos |

---

## 4. Cambios de esquema (DDL)

Archivo: `migrations/2026_06_20_binaria_iter5_replenishment.sql`

| Tabla | Cambio |
|---|---|
| `t_trade_replenishment_reports` | + `client_company_id`, + `reviewed` |
| `t_trade_impulse_inventory_start` | + 5 columnas, `quantity` nullable, unique constraint cambia a `(attendance_id, product_id, batch_number)` |
| `t_trade_impulse_inventory_end` | Mismas 5 columnas que `_start` |
| `t_trade_replenishment_inventory` | **DROP TABLE** |
| `t_trade_replenishment_receptions` | + `client_company_id`, + `batch_number`, + `expiration_date` |
| `t_trade_complementary_bandeo_header` | + `client_company_id` |
| `t_trade_complementary_promo_point` | + `client_company_id` |
| `t_trade_complementary_competition` | (sin cambios) |

### Orden recomendado

1. **Backup** de las tablas afectadas.
2. Aplicar el script en ambiente de pruebas, validar con la colección
   actualizada de Postman (`postman/TRADE_Collection.json`).
3. Re-deploy del microservicio TRADE.
4. Aplicar en producción cuando Binaria lo apruebe.

---

## 5. Compatibilidad

- **Frontend que aún envíe `quantity` legacy:** funciona. Se interpreta
  como "todo en sala".
- **Filas históricas:** todas válidas.
- **Endpoint legacy `/v1/replenishment/visit/{id}/inventory`:** dejó de
  existir. El frontend debe apuntar a los `inventory-start` /
  `inventory-end` de Impulses con el mismo body extendido.

---

## 6. Contacto

Cualquier duda escribir a **raforios@gmail.com** mencionando
"TRADE iter 5 (Reposiciones + inventario unificado)".
