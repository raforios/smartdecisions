# TRADE — Respuesta a observaciones (Revisión 4)

**Cliente:** BINARIA
**Fecha:** 2026-08-03 (act. 2026-08-04)
**Módulo:** TRADE
**Sobre:** correos de Paula (revisión de la entrega del 2026-07-19) — propiedad de SKU /
promoción por compañía, consultas de Bandeos y filtro de listado de asistencias.
**Colección Postman:** `TRADE_Collection.json` — versión **V2.4** (agrega
`4.1.5 List Attendances by Company` y `4.1.6 List Attendances by Client Company`).

Este documento consolida las notas abiertas de la última revisión y sirve como guía de
pruebas para cerrar el módulo. Todas las correcciones tienen las pruebas unitarias del
servicio en verde y quedan a la espera del despliegue del backend.

---

## 1. Resumen ejecutivo

| # | Observación | Estado |
|---|---|---|
| 1 | Registrar reposiciones (`/replenishment/visit/{id}/report`): valida SKU contra la compañía ejecutora | **Corregido** |
| 2 | Registrar inventario de reposiciones (`/replenishment/visit/{id}/inventory`): mismo error | **Corregido** |
| 3 | Recepción de proveedor (`/replenishment/visit/{id}/reception`): mismo error | **Corregido** |
| 4 | Planificar bandeo (`/complementary/bandeo/plan`): valida la promoción contra la compañía ejecutora | **Corregido** |
| 5 | Recibir bandeo (`.../bandeo/{id}/receive`): no permitía la compañía cliente / no verificaban el cálculo del plan | **Corregido** |
| 6 | Devolver bandeo (`.../bandeo/{id}/return`): mismo patrón (barrido preventivo) | **Corregido** |
| 7 | Listar asistencias obliga `pos_id`/`user_id`; falta `client_company_id` | **Corregido** |
| 8 | Consultas de Bandeos (status, cálculo del plan, campos de `details[]`) | **Confirmadas** (ver §4) |

---

## 2. Corrección: propiedad de SKU y promoción por compañía cliente

**Diagnóstico.** En los flujos de **visita** (registro dentro de un PDV), los SKU, el
surtido del PDV y **las promociones que los agrupan** pertenecen a la **compañía CLIENTE**
(dueña del PDV/productos), no a la **compañía EJECUTORA** que corre la visita. Varios
servicios resolvían el SKU/promoción con la compañía ejecutora, por lo que no se
encontraban los registros de la compañía cliente:

```json
{ "detail": "404: Product with SKU EMB.000.000.000.001 not found for company 1" }
```

**Regla aplicada** (ya existente en Venta de Impulso desde 2026-05-31, ahora replicada de
forma consistente en todos los flujos de visita):

```python
catalog_company_id = client_company_id or company_id
```

El `client_company_id` manda; la compañía ejecutora queda solo como respaldo para registros
antiguos que no lo tienen. La corrección afecta **la resolución del SKU**, **la validación
de surtido del PDV** y **la búsqueda de la promoción**.

| Flujo | Endpoint | Se valida contra |
|---|---|---|
| Registrar reposiciones | `POST /replenishment/visit/{id}/report` | compañía cliente |
| Registrar inventario de reposiciones | `POST /replenishment/visit/{id}/inventory` | compañía cliente |
| Recepción de proveedor | `POST /replenishment/visit/{id}/reception` | compañía cliente |
| Planificar bandeo | `POST /complementary/bandeo/plan` | compañía cliente (promoción **y** SKU) |
| Recibir bandeo | `POST /complementary/visit/{id}/bandeo/{bandeo_id}/receive` | compañía cliente (del header) |
| Devolver bandeo | `POST /complementary/visit/{id}/bandeo/{bandeo_id}/return` | compañía cliente (del header) |

**No cambia el contrato de request.** El `client_company_id` ya viajaba en el payload (o
quedó registrado en el header del bandeo al Planificar); solo cambia contra qué compañía se
valida. En **Recibir** y **Devolver** el bandeo toma el `client_company_id` que quedó
fijado en el paso **Planificar**, por lo que ya no es necesario reenviarlo.

**Sobre las promociones.** No hizo falta cambiar el modelo ni migrar datos: la promoción ya
vive bajo el `company_id` de su compañía dueña. Basta con buscarla con
`catalog_company_id`, tal como lo hace Venta de Impulso. Requisito operativo: las
promociones deben crearse bajo la **compañía cliente** (su `company_id`), que es la dueña de
los productos que agrupan.

**Fuera de alcance (a propósito).** Los flujos de **catálogo** (crear/editar productos,
asignación producto↔PDV, inventario de PDV, crear/listar promociones) son de un solo tenant
—el dueño del catálogo— y se mantienen sin cambio.

---

## 3. Barrido preventivo

Se revisaron **todos** los puntos del servicio que resuelven un SKU o una promoción por
compañía. Resultado:

- **Corregidos** (flujos de visita): reposiciones (report / inventory / reception) y bandeos
  (plan / receive / return).
- **Sin cambio** (correctos): catálogo de productos, asignación producto↔PDV, inventario de
  PDV, y la creación/listado de promociones (operan sobre el tenant dueño del catálogo).

No quedan otros flujos de visita validando contra la compañía ejecutora.

---

## 4. Consultas de Bandeos — confirmaciones

Verificadas contra el código de la entrega vigente:

| Consulta | Respuesta |
|---|---|
| **Planificar**: ¿guarda `quantity_planned`? | **Sí.** Header en `status = PENDING` y un detalle por SKU con `quantity_planned = promotion_quantity × sku_quantity`, calculado en el servidor (no se envía). |
| **Recibir**: ¿cambia a `status = RECEIVED`? | **Sí.** El header pasa de `PENDING` a `RECEIVED`. |
| **Recibir**: ¿`details[]` incluye `quantity_planned` y `quantity_received`? | **Sí**, ambos. |
| **Devolver**: ¿cambia a `status = RETURNED`? | **Sí.** El header pasa de `RECEIVED` a `RETURNED`. |
| **Devolver**: ¿`details[]` incluye las 4 cantidades? | **Sí**: `quantity_planned`, `quantity_received`, `quantity_used`, `quantity_returned` (+ `observations`). |
| **Get bandeo por id**: ¿requiere PDV abierto? | **No.** Funciona con o sin visita abierta. |
| **Get bandeo por id**: ¿`details[]` completo? | **Sí**: `product_sku`, las 4 cantidades, `unit_of_measure`, `observations`. |
| **Bandeos por visita** / **Listado paginado**: ¿`details[]` completo? | **Sí** (mismos campos). |

---

## 5. Listar asistencias — filtro (corregido)

`GET /trade/attendances`:
- `pos_id` y `user_id` ahora son **opcionales** (el `company_id` ejecutor sigue siendo el
  tenant obligatorio, así que el listado siempre queda acotado a la compañía).
- Se agregó el filtro **`client_company_id`** (opcional), que deriva directamente de la
  asistencia. Con esto se puede armar el reporte de rutas ejecutadas por compañía cliente
  en una sola llamada (evita los timeouts de llamar N veces).

---

## 6. Guía de pruebas sugerida

> **Prerrequisito Postman:** importar la colección **V2.4** y configurar la variable de
> entorno `client_company_id` con la compañía cliente real (p. ej. `14`, dueña de los
> productos/PDV). Los requests de reposiciones y bandeos ya envían `client_company_id` en el
> body; asegúrese de que apunte a la compañía cliente y que la promoción de prueba (bandeo)
> se haya creado bajo esa misma compañía.

| # | Prueba | Resultado esperado |
|---|---|---|
| 1 | `POST /replenishment/visit/{id}/report` con SKU de la compañía cliente | Graba (antes: 404 "not found for company 1"). |
| 2 | `POST /replenishment/visit/{id}/inventory` con SKU de la compañía cliente | Graba el inventario. |
| 3 | `POST /replenishment/visit/{id}/reception` con SKU de la compañía cliente | Graba la recepción. |
| 4 | `POST /complementary/bandeo/plan` con una promoción de la compañía cliente | Crea el bandeo `PENDING` y calcula `quantity_planned` por SKU. |
| 5 | Recibir → Devolver el bandeo planificado | Status `PENDING → RECEIVED → RETURNED`; `details[]` con las cantidades. |
| 6 | `GET /trade/attendances` solo con `company_id` | Devuelve todas las asistencias de la compañía. |
| 7 | `GET /trade/attendances` con `company_id` + `client_company_id` | Devuelve las asistencias de esa compañía cliente. |

---

## 7. Estado y próximos pasos

- **Correcciones (§2, §3, §5):** aplicadas y con las pruebas unitarias del servicio en
  verde. Pendiente el deploy del backend (lo realiza el equipo de BearSoft).
- **Consultas (§4):** sin cambios de código (comportamiento confirmado).
- **Requisito operativo:** las promociones deben crearse bajo la compañía cliente (dueña de
  los productos). Con eso, el circuito completo de Reposiciones y Bandeos queda funcional.

Quedamos atentos para coordinar el deploy y cerrar el módulo.
