# TRADE — Iteración 6

**Fecha:** 2026-06-22
**Cliente:** Binaria
**Contacto:** Rafael Foronda Ríos — raforios@gmail.com
**Microservicio:** TRADE
**Scripts SQL:**
- `migrations/2026_06_22_binaria_iter6_bandeo.sql`
- `migrations/2026_06_22_binaria_iter6_followups.sql`

---

## 1. Resumen ejecutivo

Cierra las brechas detectadas contra el documento *Requerimientos
funcionales V0.8* en los puntos:

| # | Punto del requerimiento | Cambio |
|---|---|---|
| 1 | 7.3.4.1 Registrar bandeo | Refactor a flujo de 2 pasos (Recibir → Devolver) + N bandeos por visita. |
| 2 | 7.3.4.2 Punto promocional | Se suman `opening_time`, `closing_time`, `description`. |
| 3 | 7.3.4.3 Información de competencia | Se suman `price`, `latitude`, `longitude`, `location_description`. |
| 4 | 7.4 Monitor de Trade | Tres endpoints agregados nuevos para los paneles de Impulsos / Reposiciones / Seguimiento de rutas. |
| 5 | 7.1.1 Rutas de trade | `planned_check_in_time` en el PDV de la ruta. |

---

## 2. Cambios por punto

### 2.1 Bandeo (7.3.4.1)

**Header (`t_trade_complementary_bandeo_header`)**

- Drop `UNIQUE(attendance_id)` (una visita puede tener N bandeos).
- `promotion_id INT` (FK a `t_trade_promotions`) — bandeo planificado.
- `status VARCHAR(20)` — `PENDING → RECEIVED → RETURNED`.
- `received_at`, `returned_at`.
- `UNIQUE(attendance_id, promotion_id)`.

**Detail (`t_trade_complementary_bandeo_detail`)**

- `quantity_planned`, `quantity_received`, `quantity_used`,
  `unit_of_measure`, `observations`.
- `quantity_returned` pasa a nullable.

**Endpoints**

| Método | Ruta | Estado |
|---|---|---|
| `POST` | `/v1/replenishment/complementary/visit/{attendance_id}/bandeo` | **Eliminado** |
| `POST` | `/v1/replenishment/complementary/visit/{attendance_id}/bandeo/receive` | **Nuevo** (Recibir) |
| `PATCH` | `/v1/replenishment/complementary/bandeo/{bandeo_id}/return` | **Nuevo** (Devolver) |
| `GET` | `/v1/replenishment/complementary/visit/{attendance_id}/bandeos` | **Nuevo** (listado por visita) |
| `GET` | `/v1/replenishment/complementary/bandeo/{bandeo_id}` | **Nuevo** (detalle) |

**Validaciones**

- `quantity_used ≤ quantity_received` y `quantity_returned ≤ quantity_received`.
- `observations` obligatorio cuando `quantity_returned ≠ quantity_received - quantity_used`.
- Solo se permite la transición `RECEIVED → RETURNED`.
- El payload del Devolver debe incluir TODAS las filas del header.

---

### 2.2 Punto promocional (7.3.4.2)

**Tabla `t_trade_complementary_promo_point`**

- `opening_time TIME` — obligatorio en el body.
- `closing_time TIME` — obligatorio en el body. Debe ser mayor a `opening_time`.
- `description TEXT` — obligatorio en el body.
- `comments` se mantiene como observación opcional.

**Endpoint sin cambios de URL**:
`POST /v1/replenishment/complementary/visit/{attendance_id}/promo-point`

Ejemplo:

```json
{
    "company_id": 1,
    "client_company_id": 7,
    "pos_id": 42,
    "opening_time": "09:00",
    "closing_time": "13:00",
    "description": "Mesa frente a la entrada con vendedora externa. Materiales: roll-up, samples.",
    "comments": "Buena afluencia."
}
```

---

### 2.3 Información de competencia (7.3.4.3)

**Tabla `t_trade_complementary_competition`**

- `price DECIMAL(12,2)` opcional.
- `latitude`, `longitude` opcionales — obligatorios cuando no hay `pos_id`.
- `location_description TEXT` opcional — obligatorio cuando no hay `pos_id`.

Endpoint sin cambios de URL:
`POST /v1/replenishment/complementary/competition`

Ejemplo:

```json
{
    "company_id": 1,
    "user_id": 1001,
    "pos_id": null,
    "competitor_name": "Marca rival",
    "activity_type": "BANDEO",
    "product_name": "Galletas frutilla",
    "details": "Bandeo 2x1 promocional",
    "price": 15.90,
    "latitude": -17.7833,
    "longitude": -63.1821,
    "location_description": "Av. Banzer 6to anillo, supermercado X."
}
```

---

### 2.4 Monitor de Trade (7.4)

Tres endpoints agregados nuevos. Toda la información que antes requería
4-5 llamadas separadas se devuelve en un solo payload.

| Método | Ruta | Punto del req |
|---|---|---|
| `GET` | `/v1/reports/panel/impulses` | 7.4.1 (Afiliaciones / Impulsos) |
| `GET` | `/v1/reports/panel/replenishments` | 7.4.3 (Reposiciones) |
| `GET` | `/v1/reports/route-tracking` | 7.4.4 (Seguimiento de rutas) |

**Filtros (paneles 7.4.1 / 7.4.3)** — `company_id`, `date_from`,
`date_to` obligatorios; `client_company_id`, `country_id`, `city_id`,
`pos_type_id`, `channel_id`, `pos_id`, `route_id`, `team_id`,
`user_id`, `product_id` opcionales.

**Estructura de respuesta del panel** — incluye:
- `general_indicators` (PDV, actividades, productos, tiempo promedio).
- `route_indicators` (solo si se filtra por ruta).
- `pdv_by_city`, `activities_by_city`, `activities_by_day`.
- `sales_summary` (panel de Impulsos) o `expirations` (panel de Reposiciones).
- `inventory_snapshot` (q en sala/almacén, mínimo, flag de quiebre).
- `sheet` (filas planas, exportables a CSV).

**Seguimiento de rutas (7.4.4)** — filtros: `company_id`, `activity`
(`IMPULSO`/`REPOSICION`), `target_date`, `route_id`, `team_id`,
`user_id`. Devuelve por cada ruta:
- Datos master (nombre, código, color).
- Puntos en orden de `sequence` con estado `PENDING`/`OPEN`/`CLOSED`
  (rojo/amarillo/verde en el mapa) y popup de inventario.

---

### 2.5 Hora de ingreso planificada por PDV (7.1.1)

- `t_trade_planned_points.planned_check_in_time TIME` (nullable).
- Se acepta en `POST /v1/trade/routes/{id}/points`,
  `PUT /v1/trade/points/{id}` y en el bulk-upload de rutas.
- Se devuelve en cualquier `GET` de rutas/puntos y en el endpoint de
  Route Tracking.

---

## 3. Compatibilidad

- **Frontend legacy del bandeo:** debe actualizarse (el POST one-shot
  desaparece). El nuevo flujo es 2 pasos.
- **Frontend que no envíe `opening_time` / `closing_time` / `description`
  en el promo point:** el backend devuelve 422.
- **Filas históricas:** todas siguen siendo válidas — las columnas nuevas
  son nullable salvo `quantity_planned` y `quantity_received` que tienen
  `DEFAULT 0`.

Estamos en fase de pruebas; coordinar con Binaria antes de aplicar los
scripts en cualquier ambiente que ya tenga datos productivos.

---

## 4. Resumen de endpoints — post iter 6

### Replenishment / Complementary

| Método | Ruta |
|---|---|
| `POST` | `/v1/replenishment/visit/{attendance_id}/report` |
| `POST` | `/v1/replenishment/visit/{attendance_id}/reception` |
| `POST` | `/v1/replenishment/complementary/visit/{attendance_id}/bandeo/receive` ⭐ iter6 |
| `PATCH` | `/v1/replenishment/complementary/bandeo/{bandeo_id}/return` ⭐ iter6 |
| `GET` | `/v1/replenishment/complementary/visit/{attendance_id}/bandeos` ⭐ iter6 |
| `GET` | `/v1/replenishment/complementary/bandeo/{bandeo_id}` ⭐ iter6 |
| `POST` | `/v1/replenishment/complementary/visit/{attendance_id}/promo-point` (cuerpo ampliado en iter6) |
| `POST` | `/v1/replenishment/complementary/competition` (cuerpo ampliado en iter6) |
| `GET` | `/v1/replenishment/reports` |
| `GET` | `/v1/replenishment/visit/{attendance_id}/reception` |

### Reports

| Método | Ruta | Estado |
|---|---|---|
| `GET` | `/v1/reports/compliance` | Sin cambios |
| `GET` | `/v1/reports/inventory-alerts` | Sin cambios |
| `GET` | `/v1/reports/sales` | Sin cambios |
| `GET` | `/v1/reports/merchandising` | Sin cambios |
| `GET` | `/v1/reports/photographic` | Sin cambios |
| `GET` | `/v1/reports/attendance` | Sin cambios |
| `GET` | `/v1/reports/panel/impulses` | **Nuevo (7.4.1)** |
| `GET` | `/v1/reports/panel/replenishments` | **Nuevo (7.4.3)** |
| `GET` | `/v1/reports/route-tracking` | **Nuevo (7.4.4)** |

### Trade (rutas)

| Método | Ruta | Estado |
|---|---|---|
| `POST` | `/v1/trade/routes/{id}/points` | Cuerpo gana `planned_check_in_time` |
| `PUT` | `/v1/trade/points/{id}` | Cuerpo gana `planned_check_in_time` |
| `POST` | `/v1/trade/routes/bulk-upload` | CSV opcional `planned_check_in_time` |

---

## 5. Contacto

Cualquier duda escribir a **raforios@gmail.com** mencionando
"TRADE iter 6".
