# Supplies Service

Microservicio de inventarios para materiales e insumos del Ministerio.
Forma parte del ecosistema SmartDecisions (BearSoft) y sigue el mismo
boilerplate que `Localization-Service` y `Forms-Service`.

## Procesos cubiertos

1. **Notas de Ingreso (Entries)**
   - Documento de ingreso a almacén (`POST /v1/supplies/entries`) con cabecera
     (tipo: COMPRA / DONACION_TRANSFERENCIA / REINGRESO; proveedor;
     requerimiento, nota de entrega y factura con sus fechas; descuento) y
     detalle multi-artículo.
   - Cada línea del detalle es una **capa de costo PEPS/FIFO** y dispara un
     movimiento `IN` valorado en el kárdex (`unit_cost`, `source_entry_id`).
2. **Solicitudes**
   - Flujo 1 (REQUESTER): crea solicitudes, no puede pedir ítems en o bajo
     el mínimo, sigue el flujo `CREATED → IN_PROCESS → DELIVERED → CLOSED`.
   - Flujo 2 (WAREHOUSE_MANAGER/ADMIN): procesa, rechaza, anula y entrega.
     La entrega consume capas de costo **PEPS/FIFO** (más antiguas primero):
     una entrega que cruza varios lotes genera varias filas `OUT` valoradas,
     cada una etiquetada con su costo y su Nota de Ingreso de origen.
   - La solicitud guarda la identidad que se imprime y se firma en papel
     (`requester_name`, `requester_position`, `requester_unit`).
3. **Reserva de existencias**
   - Crear una solicitud **reserva** las cantidades (`Item.reserved_stock`):
     una segunda solicitud ya no puede comprometer esas mismas unidades.
   - La reserva se libera al rechazar, anular o eliminar la solicitud, y se
     convierte en salida real al entregar (lo no entregado vuelve al pool).
   - `available_stock = current_stock - reserved_stock - min_stock` viaja en
     la respuesta de `/items` para que la UI no recalcule la regla.
   - `recalculate_reserved_stock()` reconstruye el valor materializado desde
     las solicitudes abiertas (lo usa el migrador).
4. **Proveedores**
   - CRUD bajo `/v1/supplies/suppliers`. Toda Nota de Ingreso apunta a un
     proveedor registrado; el nombre se copia al documento para que renombrar
     al proveedor no reescriba notas ya firmadas.
   - Baja lógica (`is_active`); el borrado físico solo procede si el proveedor
     nunca emitió una nota.

## Roles

Consumidos del claim `role` del JWT emitido por AUTH:

| Rol | Capacidades |
|---|---|
| ADMIN | CRUD catálogo (grupos contables, unidades, ítems), reportes, todas las transiciones |
| WAREHOUSE_MANAGER | Reposiciones, recepciones, procesar/entregar/rechazar solicitudes |
| REQUESTER | Crear y cerrar (conformidad) sus propias solicitudes |

## Endpoints principales

```
GET    /v1/supplies/items
POST   /v1/supplies/items                            (ADMIN)
PUT    /v1/supplies/items/{id}/parameters            (ADMIN, WAREHOUSE_MANAGER)
POST   /v1/supplies/entries                          (ADMIN, WAREHOUSE_MANAGER)
GET    /v1/supplies/entries
GET    /v1/supplies/entries/{entry_id}
POST   /v1/supplies/requests
PATCH  /v1/supplies/requests/{id}/process
PATCH  /v1/supplies/requests/{id}/deliver
PATCH  /v1/supplies/requests/{id}/close
PATCH  /v1/supplies/requests/{id}/reject
PATCH  /v1/supplies/requests/{id}/cancel
GET    /v1/supplies/kardex/items/{item_id}
GET    /v1/supplies/reports/low-stock
GET    /v1/supplies/reports/entries
GET    /v1/supplies/reports/requests
GET    /v1/supplies/reports/inventory/physical-valued
GET    /v1/supplies/reports/inventory/stock-on-hand
GET    /v1/supplies/reports/inventory/in-out-by-group
GET    /v1/supplies/reports/kardex-valued
GET    /v1/supplies/reports/outflow-stats
POST   /v1/supplies/suppliers                        (ADMIN, WAREHOUSE_MANAGER)
GET    /v1/supplies/suppliers
GET    /v1/supplies/suppliers/{supplier_id}
PUT    /v1/supplies/suppliers/{supplier_id}          (ADMIN, WAREHOUSE_MANAGER)
DELETE /v1/supplies/suppliers/{supplier_id}          (ADMIN)
GET    /v1/supplies/dashboard/summary
GET    /v1/supplies/dashboard/recent-activity
```

La especificación OpenAPI completa está disponible en `/docs` cuando el
servicio corre con la documentación habilitada.

## Ejecución local

```bash
pip install -r requirements.txt
python main.py
```

Por defecto escucha en `http://0.0.0.0:3004` y crea/verifica las tablas
contra la base configurada en `.env`.

## Importación del catálogo oficial

Los grupos contables (`t_supplies_category`) y los artículos se cargan desde
los CSV oficiales en `docs/` (`grupo-contable.csv` y `articulos.csv`). El
importador maneja el API por HTTP y es idempotente por `code`:

```bash
python scripts/import_catalog.py \
    --admin-email <admin> --admin-password <pass> \
    --base-url http://localhost:3004/v1/supplies
```

- Cada **grupo contable** (p. ej. `32100 PAPEL`) se crea como categoría.
- Las **unidades de medida** se derivan de los artículos.
- Cada **artículo** enlaza a su grupo por la columna `Cuenta contable`.
- La columna legada `Codel old` **se ignora por completo** (no tiene uso en
  el nuevo sistema) y no aparece en ningún registro importado.
- Los ítems se crean con stock 0; los saldos iniciales entran por el kárdex /
  notas de ingreso, no por el importador.

## Variables de entorno

Definidas en `.env` (no se sube al repo). Las principales:

```
HOST, PORT, APP_ENV
SECRET_KEY, ALGORITHM           # Deben coincidir con AUTH
DB_USER, DB_PASSWORD, DB_HOST,
DB_PORT, DATABASE, DB_DIALECT
TARGET_TIMEZONE
EVENTS_SERVICE_URL              # Auditoría y logs
FILES_SERVICE_URL, BUCKET_NAME  # Adjuntos en S3 (recepciones)
ROOT_PATH                       # Prefijo del API Gateway (e.g. supplies)
```

## Despliegue

`deploy.config` define los parámetros de la función Lambda. La build se
genera con el `Dockerfile` (produce `lambda_function.zip` con las
dependencias en `python/`).

## Cobertura de `docs/requerimientos.docx` y `docs/FORMULARIOS.PDF`

Revisión hecha el **2026-08-12** contra el texto y las 11 capturas del docx.

| Requisito | Estado |
|---|---|
| Grupo contable (CRUD) | Cubierto |
| Artículos: buscar, filtro TODOS, código, descripción, unidad, grupo | Cubierto |
| Ver movimiento del artículo (captura 2) | Cubierto — kárdex a pantalla completa |
| Editar / Desactivar artículo (captura 3) | Cubierto — la baja es lógica |
| Ingreso a almacén: tipo, proveedor, requerimiento, nota de entrega, factura, autorización, observaciones, artículos | Cubierto — el proveedor ahora sale del CRUD de proveedores |
| Hoja impresa de ingreso a almacenes | Cubierto |
| Inventario general físico valorado (capturas 4 y 5) | Cubierto, incluidas las columnas Físico/Valorado **Agrupado** |
| Inventario con stock existente (capturas 6 y 7) | Cubierto, con fecha de corte |
| Entradas y salidas valorado por cuenta contable (captura 8) | Cubierto |
| Kardex valorado (captura 9) | Cubierto; el detalle nombra al destinatario y la impresión lleva las dos firmas |
| Estadísticas de salida (captura 10) | Cubierto |
| Formulario SOLICITUD DE ALMACENES | Cubierto (imprimible desde la solicitud) |
| Formulario ENTREGA DE ALMACENES | Cubierto (imprimible desde la solicitud entregada) |

Diferencias conscientes, pendientes de decisión:

- **"Código anterior"**: excluido por decisión del cliente (ninguna fila del
  catálogo oficial lo traía). Aparece en la captura 1 del sistema legado.
- **Exportar CSV / PDF del catálogo**: la captura 1 muestra dos botones que
  la app no tiene. El resto de reportes sí es imprimible.
- **"Genera inventario general y resumen (elegir)"**: la app muestra siempre
  el resumen por grupo y el detalle colapsado por grupo, en vez de pedir al
  usuario que elija uno de los dos.
- **Descargar reporte (PDF)**: se resuelve con la impresión del navegador
  ("Guardar como PDF"), no con generación server-side, para no meter una
  librería de PDF en el bundle de Lambda.
- **Kardex impreso**: las columnas *Nro factura*, *CITE plantillas* y
  *Nro pedido* del formulario legado no existen; la app usa *N° ingreso*.

## Notas

- El kárdex (`t_supplies_kardex`) es append-only. Las correcciones se
  hacen con movimientos `ADJUSTMENT` adicionales.
- `current_stock` en `t_supplies_item` es el balance materializado y se
  mantiene sincronizado por `services/supplies_logic.post_kardex_movement`.
- Las solicitudes nunca eliminan el historial: usar `DELETE` solo es
  válido en estado `CREATED`.
