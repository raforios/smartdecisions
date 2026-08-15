# TRADE — Respuesta a observaciones (Revisión 5 — cierre)

**Cliente:** BINARIA
**Fecha:** 2026-08-13
**Módulo:** TRADE
**Sobre:** correo de Paula tras reprobar los EP de Reposiciones y Bandeos — dos endpoints
seguían validando los productos contra la compañía ejecutora.
**Colección Postman:** sin cambios (V2.4). Los contratos no se modifican.

---

## 1. Resumen ejecutivo

| # | Observación | Estado |
|---|---|---|
| 1 | Registrar inventario de reposiciones (`POST /replenishment/visit/{attendance_id}/inventory`) | **Corregido** |
| 2 | Recepción de productos del proveedor (`POST /replenishment/visit/{attendance_id}/reception`) | **Corregido** |

Ambos casos quedaron verificados contra base de datos, reproduciendo el error reportado
y confirmando la corrección. Con esto se cierra la entrega del módulo.

---

## 2. Diagnóstico: por qué el arreglo anterior no alcanzó

La corrección del 2026-08-03 cambió la **validación** de estos flujos para resolver el SKU
y el surtido del PDV contra la compañía **cliente**:

```python
catalog_company_id = payload.client_company_id or payload.company_id
for item in payload.items:
    product_id = get_product_id_by_sku(db, catalog_company_id, item.product_sku)
    validate_product_assigned_to_pos(db, catalog_company_id, payload.pos_id, product_id)
```

Lo que faltó ver es que el paso siguiente —el que **escribe** las filas— vuelve a traducir
cada SKU a su `product_id`, y ese segundo paso seguía recibiendo la compañía **ejecutora**:

```python
return await create_bulk_items_from_skus(
    db = db,
    attendance_id = attendance_id,
    company_id = payload.company_id,   # <-- la ejecutora
    ...
)
```

Resultado: la petición pasaba la validación y **fallaba recién al grabar**, con el mismo
mensaje del reporte original:

```json
{ "detail": "404: Product with SKU 000.000.000.HEL.001 not found for company 1." }
```

Por eso los otros endpoints de la misma familia sí funcionaban en la prueba de ustedes:
los que no pasan por ese helper de escritura masiva nunca tuvieron el segundo lookup.

---

## 3. Corrección aplicada

Un solo cambio, en el punto donde nacía el problema
(`services/trade_utils.py :: create_visit_items`): el helper de escritura recibe ahora la
misma compañía de catálogo que ya usaba la validación.

```python
catalog_company_id = getattr(payload, 'client_company_id', None) or payload.company_id
...
return await create_bulk_items_from_skus(
    db = db,
    attendance_id = attendance_id,
    catalog_company_id = catalog_company_id,   # antes: payload.company_id
    ...
)
```

El parámetro se renombró de `company_id` a `catalog_company_id` en
`services/products.py :: create_bulk_items_from_skus`, con su docstring explicando que es
la compañía **dueña de los productos**, para que nadie vuelva a pasarle la ejecutora.

**Alcance.** El helper es compartido por los cuatro flujos de visita, así que la corrección
aplica de forma consistente a:

- `POST /v1/replenishment/visit/{attendance_id}/inventory`
- `POST /v1/replenishment/visit/{attendance_id}/reception`
- `POST /v1/impulses/visit/{attendance_id}/inventory-start`
- `POST /v1/impulses/visit/{attendance_id}/inventory-end`

Los dos de Impulsos ya venían funcionando en las pruebas de ustedes, pero tenían el mismo
defecto latente: habrían fallado con una compañía cliente cuyos productos no existieran
también bajo la ejecutora.

**Compatibilidad.** El comportamiento con cargas antiguas no cambia: si el payload no trae
`client_company_id` (o lo trae en `null`), se sigue usando `company_id` como antes.

---

## 4. Verificación

### 4.1 Contra base de datos

Escenario montado sobre la base local de BINARIA, replicando el caso del reporte:
compañía **ejecutora 1** haciendo una visita en un PDV de la compañía **cliente 14**, cuyos
productos pertenecen a la 14.

| Paso | Antes del fix | Después del fix |
|---|---|---|
| `POST /replenishment/visit/{id}/reception` | `404 Product with SKU 000.000.000.HEL.001 not found for company 1.` | `201` — filas creadas con `product_id` de la compañía 14 |
| `POST /replenishment/visit/{id}/inventory` | mismo `404` | `201` — 2 líneas creadas |
| `POST /impulses/visit/{id}/inventory-start` | mismo `404` | `201` |

Respuesta de ejemplo del inventario de reposiciones (2 líneas, mismo SKU en distinta
ubicación y lote):

```json
{
  "items": [
    {
      "id": 1, "attendance_id": 900, "company_id": 1, "pos_id": 6, "user_id": 10,
      "product_id": 9, "client_company_id": 14, "quantity": 12,
      "batch_number": "L-2026-08", "expiration_date": "2026-12-31T00:00:00",
      "location": "SALA", "observations": null
    },
    {
      "id": 2, "attendance_id": 900, "company_id": 1, "pos_id": 6, "user_id": 10,
      "product_id": 10, "client_company_id": 14, "quantity": 5,
      "batch_number": null, "expiration_date": null, "location": "ALMACEN"
    }
  ],
  "total": 2
}
```

`product_id` 9 y 10 son los productos de la compañía **14**: la resolución quedó del lado
correcto. Los datos de prueba se eliminaron de la base al terminar.

### 4.2 Pruebas automatizadas

`services/trade/tests/test_visit_catalog_company.py` (nuevo, 3 casos) fija la regla para
que no vuelva a perderse:

- con `client_company_id`, las **tres** resoluciones (SKU, surtido y escritura) usan la
  compañía cliente;
- sin `client_company_id`, todas usan la ejecutora (compatibilidad);
- con `client_company_id: null`, se comporta como carga antigua.

Suite completa del servicio: **7/7 en verde**. Pylint 10.00/10 sobre los archivos tocados.

---

## 5. Cómo probarlo de su lado

Requisito de datos, igual que en las revisiones anteriores: los productos y su asignación
al PDV deben existir bajo la **compañía cliente**.

```http
POST {{base_url}}/v1/replenishment/visit/{{attendance_id}}/inventory
Authorization: Bearer {{token}}
Content-Type: application/json

{
  "company_id": 1,            // compañía EJECUTORA (la que hace la visita)
  "client_company_id": 14,    // compañía CLIENTE (dueña de productos y PDV)
  "pos_id": 6,
  "items": [
    {
      "product_sku": "000.000.000.HEL.001",
      "quantity": 12,
      "location": "SALA",
      "batch_number": "L-2026-08",
      "expiration_date": "2026-12-31"
    }
  ]
}
```

```http
POST {{base_url}}/v1/replenishment/visit/{{attendance_id}}/reception
Authorization: Bearer {{token}}
Content-Type: application/json

{
  "company_id": 1,
  "client_company_id": 14,
  "pos_id": 6,
  "items": [
    {
      "product_sku": "000.000.000.HEL.001",
      "quantity_received": 24,
      "batch_number": "L-2026-09",
      "expiration_date": "2027-01-31",
      "comments": "Recepción de prueba"
    }
  ]
}
```

Ambos deben responder **201** con `product_id` resuelto y `client_company_id` en cada fila.

Si aparece `404 ... not found for company <N>`, el `<N>` del mensaje indica contra qué
compañía se buscó: si es la ejecutora, el payload no está enviando `client_company_id`; si
es la cliente, el producto no existe o no está asignado al PDV bajo esa compañía.

---

## 6. Pendiente

- **Despliegue del backend** (lo ejecuta Rafael). El cambio es solo de código: **no
  requiere migración de base de datos** ni cambios en los contratos ni en la colección
  Postman.
