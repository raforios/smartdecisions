# TRADE iter 6 — Guía de pruebas

**Fecha:** 2026-06-22
**Microservicio:** TRADE
**Para:** Equipo Binaria
**De:** Rafael Foronda Ríos — raforios@gmail.com

Esta guía cubre las **5 mejoras** liberadas en la iteración 6 del
módulo TRADE. Todos los endpoints están listos en la colección Postman
**TRADE Service - V2.1** (archivo `postman/TRADE_Collection.json`).

> Pre‑requisito: importar la colección de Postman y configurar el
> environment con la URL base del backend, las credenciales de un
> usuario válido y los IDs de prueba (compañía, PDV, producto SKU,
> visita activa, etc.).

---

## 0. Antes de empezar

### 0.1 Aplicar las migraciones SQL

Ejecutar **en orden** los siguientes scripts contra la base de TRADE
(ambiente de pruebas):

1. `migrations/2026_06_22_binaria_iter6_bandeo.sql`
2. `migrations/2026_06_22_binaria_iter6_followups.sql`

Después de correrlos, verificar con un cliente SQL:

```sql
DESCRIBE t_trade_complementary_bandeo_header;
DESCRIBE t_trade_complementary_bandeo_detail;
DESCRIBE t_trade_complementary_promo_point;
DESCRIBE t_trade_complementary_competition;
DESCRIBE t_trade_planned_points;
```

Deben aparecer las columnas nuevas listadas en el `CHANGELOG_iter6.md`.

### 0.2 Login

Ejecutar `0. Auth → 0.1 Login` para que Postman guarde el `auth_token`
en el environment. Todos los demás requests lo usan automáticamente
como `Bearer {{auth_token}}`.

### 0.3 Variables de prueba que conviene completar

| Variable | Uso típico |
|---|---|
| `company_id` | Compañía ejecutora |
| `client_company_id` | Compañía cliente (marca) |
| `pos_id` | PDV abierto en la visita |
| `attendance_id` | Visita activa (resultado de un check-in) |
| `promotion_id` | Bandeo planificado a ejecutar (de `/v1/impulses/promotions`) |
| `product_sku` | SKU asignado al PDV |
| `route_id` | Ruta de prueba |
| `point_id` | Punto planificado de la ruta |
| `bandeo_id` / `bandeo_detail_id` | Se rellenan automáticamente al ejecutar 6.4.1 |

---

## 1. Bandeo en ejecución (req 7.3.4.1)

### 1.1 Qué cambió

El antiguo `POST .../bandeo` (one-shot) **fue eliminado**. Ahora el
flujo respeta los 2 pasos de la pantalla mobile: primero la operadora
confirma lo recibido, después lo utilizado y devuelto, y por último
sube fotos.

### 1.2 Paso a paso

#### Paso A — Marcar visita (check-in)
Si todavía no tenés una visita abierta:
- Postman → `4. Execution Cycle (Visit) → 4.1.1 Check-In`.
- Anotar el `attendance_id` que devuelve.

#### Paso B — Recibir bandeo (`status → RECEIVED`)
- Postman → `6. Replenishment Activities → 6.4 Bandeo (iter6) → 6.4.1 Receive bandeo`.
- Body de ejemplo (ajustar IDs):

```json
{
    "company_id": 1,
    "client_company_id": 7,
    "pos_id": 42,
    "promotion_id": 9,
    "comments": "Recepción de productos del bandeo en sala.",
    "details": [
        {
            "product_sku": "ABC.001.002.003.01",
            "quantity_planned": 3,
            "quantity_received": 30,
            "unit_of_measure": "UN"
        }
    ]
}
```

- **Resultado esperado:** `201 Created`, header con `status="RECEIVED"`
  y `received_at` poblado. El test del request guarda
  automáticamente `bandeo_id` y `bandeo_detail_id` en el environment.

#### Paso C — Devolver bandeo (`status → RETURNED`)
- Postman → `6.4.2 Return bandeo`.
- Body:

```json
{
    "details": [
        {
            "id": 41,
            "quantity_used": 24,
            "quantity_returned": 6,
            "observations": null
        }
    ]
}
```

- **Validaciones que conviene probar:**
  - `quantity_used > quantity_received` → `400 Bad Request`.
  - `quantity_returned > quantity_received` → `400 Bad Request`.
  - `quantity_returned != quantity_received - quantity_used` y
    `observations` vacío → `400 Bad Request` (mensaje:
    "observations is required on detail X when …").
  - Repetir la llamada cuando el header ya está en `RETURNED` → `400
    Bad Request` (mensaje: "cannot be returned from status 'RETURNED'").

#### Paso D — Listado por visita
- Postman → `6.4.3 List bandeos for visit`.
- Devuelve todos los bandeos del `attendance_id`.

#### Paso E — Detalle individual
- Postman → `6.4.4 Get bandeo by id`. Útil para reentrar a la pantalla.

#### Paso F — Subir fotos del bandeo
- Postman → `7. Common (Utils) → 7.3 Upload Photo` con
  `entity_type=BANDEO` y `entity_id={{bandeo_id}}`. Se puede subir
  N veces.

### 1.3 Casos para incluir en el test plan

- ✅ Crear 2 bandeos distintos en la misma visita (debe permitir hasta
  que `(attendance_id, promotion_id)` sea único).
- ✅ Re-intentar registrar el mismo `promotion_id` para la misma visita
  → `409 Conflict` (ya existe).
- ✅ Visita inexistente o cerrada → `400` desde
  `validate_active_attendance`.

---

## 2. Punto promocional (req 7.3.4.2)

### 2.1 Qué cambió

El cuerpo ahora acepta y exige `opening_time`, `closing_time` y
`description`. `comments` queda como observación opcional adicional.

### 2.2 Paso a paso

- Postman → `6. Replenishment Activities → 6.5 Promo Point`.
- Body de ejemplo:

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

### 2.3 Casos para incluir en el test plan

- ✅ Faltante de `description` → `422`.
- ✅ `closing_time` ≤ `opening_time` → `400`
  ("closing_time must be later than opening_time").
- ✅ Visita inexistente → `400`.
- ✅ Subir fotos del punto con `entity_type=PROMO_POINT`,
  `entity_id={{promo_point_id}}` (idéntico flujo a iter 5).

---

## 3. Información de competencia (req 7.3.4.3)

### 3.1 Qué cambió

Se agregaron `price`, `latitude`, `longitude` y `location_description`.
Cuando el reporte se hace **fuera de un PDV abierto** (`pos_id = null`),
los tres campos `latitude`, `longitude` y `location_description` son
**obligatorios**.

### 3.2 Paso a paso

- Postman → `6. Replenishment Activities → 6.6 Competition Report`.
- Body de ejemplo (caso fuera de PDV):

```json
{
    "company_id": 1,
    "user_id": 1001,
    "pos_id": null,
    "competitor_name": "Marca rival",
    "activity_type": "BANDEO",
    "product_name": "Galletas frutilla",
    "details": "Bandeo 2x1 promocional en góndola lateral.",
    "price": 15.90,
    "latitude": -17.7833,
    "longitude": -63.1821,
    "location_description": "Av. Banzer 6to anillo, supermercado X."
}
```

### 3.3 Casos para incluir en el test plan

- ✅ `pos_id = null` y falta `location_description` → `400`.
- ✅ `pos_id = null` y faltan `latitude/longitude` → `400`.
- ✅ `pos_id` presente: `latitude/longitude/location_description`
  pueden venir nulos (no se exigen).
- ✅ `price` negativo → `422` (validación Pydantic).

---

## 4. Monitor de Trade (req 7.4)

Tres endpoints agregados nuevos en `8. Analytics: Reports`.

### 4.1 Panel de Impulsos (7.4.1)

- Postman → `8.6 Panel: Impulses`.
- Filtros obligatorios: `company_id`, `date_from`, `date_to`.
  Opcionales: `client_company_id`, `country_id`, `city_id`, `route_id`,
  `pos_id`, `team_id`, `user_id`, `product_id`.
- **Devuelve en una sola llamada:**
  - `general_indicators` (PDV, impulsos, productos, tiempo promedio).
  - `route_indicators` (si se filtró ruta).
  - `pdv_by_city` y `activities_by_city` (datos para los gráficos pie).
  - `activities_by_day` (línea por día).
  - `sales_summary` (resumen por SKU).
  - `inventory_snapshot` (stock al cierre por SKU).
  - `sheet` (planilla plana para exportar).

### 4.2 Panel de Reposiciones (7.4.3)

- Postman → `8.7 Panel: Replenishments`.
- Mismos filtros que el panel de Impulsos.
- **Diferencias en el payload:** trae `expirations` (lista de lotes con
  días restantes y flag de fecha corta) y el `inventory_snapshot` viene
  desagregado por sala (`quantity_in_room`) y almacén
  (`quantity_in_warehouse`) con flag `stockout` por SKU.

### 4.3 Seguimiento de rutas (7.4.4)

- Postman → `8.8 Route Tracking`.
- Filtros: `company_id`, `activity` (`IMPULSO` o `REPOSICION`),
  `target_date` obligatorios. Opcionales: `route_id`, `team_id`,
  `user_id`.
- **Respuesta:** lista de rutas con sus puntos en orden de `sequence`.
  Por cada punto:
  - `status` = `PENDING` (rojo), `OPEN` (amarillo) o `CLOSED` (verde).
  - `check_in_time`, `check_out_time`.
  - `inventory` (popup):
    - Impulsos → `quantity_initial`, `quantity_sold`,
      `quantity_remaining` por SKU.
    - Reposiciones → `quantity_in_room`, `quantity_in_warehouse`,
      `quantity_total`, `quantity_minimum`, `stockout` por SKU.

### 4.4 Casos para incluir en el test plan

- ✅ Período sin datos → response con listas vacías (sin error).
- ✅ Filtrar por `route_id` → debe aparecer `route_indicators`.
- ✅ Filtrar por `product_id` → el `sales_summary` y el `sheet`
  solo deben incluir filas de ese SKU.
- ✅ `route-tracking` con visita abierta (sin check-out) → el punto
  debe venir `status=OPEN` y `check_out_time=null`.

---

## 5. Hora de ingreso planificada por PDV (req 7.1.1)

### 5.1 Qué cambió

`t_trade_planned_points.planned_check_in_time` (TIME, nullable). Es la
hora prevista de llegada del reponedor / impulsadora al PDV, que el doc
exige incluir en el catálogo de la ruta junto con el código del PDV y
el tiempo estimado.

### 5.2 Paso a paso

- Postman → `3. Field Planning → 3.2 Planned Points → 3.2.1 Add Planned Point to Route`.
- Body incluye ahora `planned_check_in_time`:

```json
{
    "sequence": 1,
    "point_of_sale_id": 42,
    "planned_workload_minutes": 30,
    "planned_check_in_time": "08:30",
    "is_adhoc": false,
    "status": "PENDING"
}
```

- Postman → `3.2.3 Update Planned Point` admite el mismo campo (editar
  cuando se cambia la ventana horaria del PDV).
- Postman → `3.1.6 BULK: Upload Planned Routes` admite una columna CSV
  opcional `planned_check_in_time` con formato `HH:MM`.

### 5.3 Casos para incluir en el test plan

- ✅ Crear un punto sin enviar el campo → se persiste como `null`
  (compatibilidad hacia atrás).
- ✅ Crear con valor `"08:30"` → recuperar el punto con `GET
  /v1/trade/routes/{id}` y verificar que aparece en cada `point` del
  array.
- ✅ Aparece en el response del endpoint `8.8 Route Tracking` por
  cada punto.

---

## 6. Resumen para reportar bugs

Por favor, al reportar incluir:

1. Endpoint exacto (método + URL).
2. Body enviado (sin tokens).
3. Status HTTP devuelto.
4. JSON de respuesta completo.
5. Hora aproximada (UTC) para correlacionar con logs en CloudWatch.

Cualquier consulta → **raforios@gmail.com**, asunto
"TRADE iter 6 — <tema>".
