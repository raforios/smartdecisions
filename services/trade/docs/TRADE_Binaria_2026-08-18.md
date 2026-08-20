# TRADE / EVENTS — Respuestas y cierre de observaciones

**Cliente:** BINARIA
**Fecha:** 2026-08-18
**Módulos:** TRADE, EVENTS
**Sobre:** correo de Paula del 2026-08-17 (cierre de Reposiciones, consultas de
`entity_type` y `microservice`, incidentes de filtros en Events y formalización de la
entrega).

---

## 1. Palabras clave para subir fotografías (`entity_type`)

El campo `entity_type` de `t_trade_photos` identifica a qué transacción pertenece la
fotografía. Los valores son estos y son sensibles a mayúsculas:

| Transacción | `entity_type` |
|---|---|
| Reposiciones — reporte de la visita | `REPLENISHMENT_REPORT` |
| Bandeos (recibir / devolver) | `BANDEO` |
| Promociones — punto de promoción | `PROMO_POINT` |
| Competencia | `COMPETITION` |
| Venta de impulso | `IMPULSE_SALE` |
| Producto (catálogo) | `PRODUCT` |
| Punto de venta | `POS` |

El `entity_id` que acompaña al `entity_type` es el identificador del registro de esa
transacción: por ejemplo, para `BANDEO` es el `id` de la cabecera del bandeo, y para
`REPLENISHMENT_REPORT` el `id` del reporte de reposición.

---

## 2. Palabras clave del filtro `microservice` en Events

El valor lo estampa cada microservicio al emitir el log. Los que existen hoy en las tablas
de la cuenta de BINARIA son:

| `microservice` | Origen |
|---|---|
| `LOCALIZATION` | Localization Service |
| `FORMS` | Forms Service |
| `FORMS-REPORTS` | Módulo de reportes de Forms |
| `PLANNING` | Planning Service |
| `TRADE` | Trade Service |

---

## 3. Incidentes de los filtros de Events (Logs y Audit)

Se reprodujo el problema contra la tabla real y se identificaron **tres causas
independientes**: dos defectos de código y una limitación de la infraestructura. Las tres
quedaron resueltas.

### 3.1. Defecto corregido: las fechas se comparaban como si fueran campos

El servicio construía el filtro tratando **todos** los parámetros de la consulta como
igualdades. Es decir, `start_date` y `end_date` se buscaban como si fueran atributos del
registro:

```python
# Antes: start_date y end_date NO son campos del registro.
filter_expressions = [Attr(key).eq(value) for key, value in filters.items()]
```

Como ningún registro tiene atributos llamados `start_date` ni `end_date`, **cualquier
consulta que incluyera fechas devolvía cero resultados**. Reproducido con la consulta del
reporte:

```
GET /v1/events/usage-log?microservice=LOCALIZATION&method=POST
    &start_date=2026-07-01T00:00:00&end_date=2026-07-01T23:59:59
→ {"records": [], "last_evaluated_key": "..."}
```

Corregido: las fechas se aplican ahora como un rango sobre el campo `timestamp`, que es
donde el servicio guarda la marca de tiempo (`between`, o `>=` / `<=` si solo se envía una
de las dos).

### 3.2. Defecto corregido: páginas vacías con más datos por detrás

DynamoDB aplica el `limit` a los registros que **lee**, no a los que devuelve después de
filtrar. Una página podía por tanto volver vacía aunque quedaran coincidencias más
adelante, que es exactamente el síntoma de `"records": []` acompañado de un
`last_evaluated_key` con valor.

Corregido: el servicio ahora encadena lecturas hasta completar la página solicitada,
agotar la tabla o consumir su presupuesto de tiempo. Un `records` vacío significa ahora
que no hay más coincidencias, no que la página leída no tenía ninguna.

### 3.3. Causa de fondo: la tabla no estaba indexada para estas consultas

Medición sobre `usage_logs` en la cuenta de BINARIA:

| Dato | Valor |
|---|---|
| Registros | 827.474 |
| Tamaño | 10,6 GB |
| Tamaño medio por registro | 13,5 KB |
| Capacidad de lectura (antes) | 5 RCU |
| Índices secundarios (antes) | **ninguno** |
| Timeout del Lambda | 30 s |

Sin un índice, filtrar por `microservice` o por fecha obliga a recorrer la tabla entera y
descartar lo que no coincide. Con 5 RCU sobre 10,6 GB, una prueba real recorrió **2.828 de
827.474 registros en 112 segundos**: a ese ritmo, una búsqueda completa tardaría horas,
mientras que el Lambda corta a los 30 segundos.

Es decir: las correcciones de código evitan resultados equivocados, pero por sí solas no
alcanzaban — sin índice el endpoint habría seguido devolviendo páginas parciales. Las
consultas que antes parecían funcionar eran las que encontraban coincidencias entre los
primeros registros leídos.

**Medidas aplicadas** (con la autorización recibida):

1. **Índice secundario global creado** en `usage_logs` y `audit_records`:
   `microservice-timestamp-index`, particionado por `microservice` y ordenado por
   `timestamp`, con proyección completa para no alterar la respuesta del endpoint. Convierte
   la búsqueda en una consulta directa que lee únicamente los registros que coinciden, en
   lugar de recorrer la tabla entera.
2. **Tablas pasadas a capacidad bajo demanda.** Los 5 RCU aprovisionados eran el segundo
   factor de lentitud: cualquier lectura quedaba limitada a esa cuota. Bajo demanda, la
   capacidad se ajusta al uso real.
3. **Los cuerpos de las peticiones y respuestas se acotan antes de almacenarse.** Guardar
   `request_body` y `response_body` completos es lo que llevaba el registro medio a 13,5 KB
   y la tabla a 10,4 GB. Ahora se recortan a **2.000 caracteres**, dejando una marca
   visible (`…[truncado por EVENTS]`) para que nunca se confunda un cuerpo recortado con el
   original. Los cuerpos por debajo de ese tamaño se conservan intactos y con su estructura.
   El límite es configurable por entorno mediante la variable `MAX_BODY_CHARS`.

Medido sobre un registro real de los que hoy pesan más: **20.107 bytes → 2.104 bytes**, una
reducción del 90% por registro, sin perder la información de diagnóstico.

Ninguna de las tres medidas interrumpió el servicio ni eliminó registros existentes. El
recorte de cuerpos aplica a los registros nuevos; los ya almacenados se conservan tal como
están.

**Queda a consideración de BINARIA** una cuarta medida que no se aplicó por implicar el
borrado de información: definir una **política de retención (TTL)** sobre `usage_logs`, por
ejemplo 6 o 12 meses. Los logs de uso son datos operativos que crecen indefinidamente; sin
retención, la tabla seguirá aumentando aunque cada registro ahora pese menos. La auditoría
(`audit_records`) conviene evaluarla por separado, ya que puede tener requisitos de
conservación distintos.


### 3.4. Límite de tamaño de respuesta (detectado al verificar en producción)

Una vez activo el índice, las consultas empezaron a devolver realmente sus 100 registros y
apareció un efecto secundario: la respuesta superaba el **límite de 6 MB** de AWS Lambda y
el endpoint respondía error 500.

```
Exceeded maximum allowed payload size (6291556 bytes)
```

La causa es la misma de fondo: los registros anteriores conservan sus cuerpos completos.
Medido en producción, **21 registros de LOCALIZATION en julio pesaban 3,38 MB**; una página
de 100 superaba ampliamente el límite.

Corregido aplicando el recorte de cuerpos **también en la lectura**, no solo al almacenar.
Los registros históricos no se modifican; se recortan al devolverlos.

| Consulta | Sin recorte | Con recorte |
|---|---|---|
| LOCALIZATION julio (21 registros) | 3,38 MB → error 500 | 38 KB |
| LOCALIZATION junio (100 registros) | 1,31 MB | 181 KB |
| TRADE agosto (100 registros) | 0,39 MB | 101 KB |

---

## 4. Compatibilidad con FORMS y LOCALIZATION

La corrección se hizo sobre la capa de acceso a datos que comparten los tres módulos, por
lo que se verificó explícitamente que no altera su funcionamiento:

- **No cambia el contrato de la API**: mismos parámetros y misma forma de respuesta
  (`records` + `last_evaluated_key`).
- **No cambia la escritura de logs**: la emisión desde FORMS, LOCALIZATION, PLANNING y
  TRADE es la misma.
- **Las consultas sin fechas se comportan igual**, salvo que ahora completan la página en
  lugar de devolverla a medias.

---

## 5. Entrega del código fuente

Última versión en el Drive compartido, con la carpeta de **TRADE** incluida. Los datos
técnicos de cada microservicio se detallan en el documento **«HOW-TO — Despliegue de
microservicios con Docker»**, que se entrega junto a este: versión de Python, puerto,
comando de arranque, dependencias externas y el procedimiento completo para levantar el
entorno con `build_infra.sh` y `docker-compose.yml`.

---

## 6. Estado

| Punto | Estado |
|---|---|
| Reposiciones — inventario y recepción | Cerrado (confirmado por BINARIA) |
| `entity_type` para fotografías | Respondido (§1) |
| `microservice` para el filtro de Events | Respondido (§2) |
| Events / Logs — filtro de fechas | Corregido (§3.1, §3.2) |
| Events / Audit — filtro de fechas | Corregido, misma corrección |
| Índice de las tablas de Events | Creado y en línea (§3.3) |
| Capacidad de las tablas de Events | Pasadas a bajo demanda (§3.3) |
| Tamaño de los registros de Events | Cuerpos acotados a 2.000 caracteres (§3.3) |
| Política de retención (TTL) | A definir por BINARIA (§3.3) |
| Tamaño de respuesta (error 500) | Corregido (§3.4) |
| Código fuente | Entregado en Drive |
| Documento de despliegue | Se entrega con este informe |
| Documento de infraestructura AWS | Actualizado y entregado |
| Despliegue de la versión final en AWS | Pendiente del despliegue |
