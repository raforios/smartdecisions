# Supplies Service

Microservicio de inventarios para materiales e insumos del Ministerio.
Forma parte del ecosistema SmartDecisions (BaarSoft) y sigue el mismo
boilerplate que `Localization-Service` y `Forms-Service`.

## Procesos cubiertos

1. **Reposiciones**
   - Detección de ítems en o bajo el stock mínimo (`GET /v1/supplies/replenishments/pending`).
   - Generación de órdenes de reposición (individual o en bulk) que alimentan
     el listado consumido por el sistema externo de Compras.
   - Recepciones independientes por orden (lote, vencimiento, proveedor,
     factura, archivo S3 opcional), cada una dispara un movimiento `IN`
     en el kárdex y actualiza `current_stock`.
2. **Solicitudes**
   - Flujo 1 (REQUESTER): crea solicitudes, no puede pedir ítems en o bajo
     el mínimo, sigue el flujo `CREATED → IN_PROCESS → DELIVERED → CLOSED`.
   - Flujo 2 (WAREHOUSE_MANAGER/ADMIN): procesa, rechaza, anula y entrega.
     La entrega dispara movimiento `OUT` en el kárdex.

## Roles

Consumidos del claim `role` del JWT emitido por AUTH:

| Rol | Capacidades |
|---|---|
| ADMIN | CRUD catálogo, parámetros, reportes, todas las transiciones |
| WAREHOUSE_MANAGER | Reposiciones, recepciones, procesar/entregar/rechazar solicitudes |
| REQUESTER | Crear y cerrar (conformidad) sus propias solicitudes |

## Endpoints principales

```
GET    /v1/supplies/items
POST   /v1/supplies/items                            (ADMIN)
PUT    /v1/supplies/items/{id}/parameters            (ADMIN, WAREHOUSE_MANAGER)
GET    /v1/supplies/replenishments/pending
POST   /v1/supplies/replenishments
POST   /v1/supplies/replenishments/bulk
POST   /v1/supplies/replenishments/{id}/receptions
POST   /v1/supplies/requests
PATCH  /v1/supplies/requests/{id}/process
PATCH  /v1/supplies/requests/{id}/deliver
PATCH  /v1/supplies/requests/{id}/close
PATCH  /v1/supplies/requests/{id}/reject
PATCH  /v1/supplies/requests/{id}/cancel
GET    /v1/supplies/kardex/items/{item_id}
GET    /v1/supplies/reports/low-stock
GET    /v1/supplies/reports/replenishments
GET    /v1/supplies/reports/requests
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

## Notas

- El kárdex (`t_supplies_kardex`) es append-only. Las correcciones se
  hacen con movimientos `ADJUSTMENT` adicionales.
- `current_stock` en `t_supplies_item` es el balance materializado y se
  mantiene sincronizado por `services/supplies_logic.post_kardex_movement`.
- Las solicitudes nunca eliminan el historial: usar `DELETE` solo es
  válido en estado `CREATED`.
