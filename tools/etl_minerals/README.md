# etl_minerals — carga quincenal de cotizaciones

Carga el Excel de cotizaciones del Ministerio de Minería en el MySQL local y lo
publica en DynamoDB, que es lo que lee el servicio desplegado. Es independiente
del API (Rafael, 19-oct-2026): tiene su propio `.env` y sus propias
dependencias, y no importa nada de `services/mining_analysis`.

## Qué necesita

- El MySQL local de minerales corriendo (contenedor `mining_db`, puerto 3310).
- Un `.env` en esta carpeta (no se sube al repositorio) con:

| Variable | Para qué |
|---|---|
| `DB_DIALECT`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DATABASE` | El MySQL local |
| `TARGET_TIMEZONE` | La hora con que se estampa cada fila (`America/La_Paz`) |
| `AWS_PROFILE`, `AWS_REGION` | La cuenta de las tablas (`deploy_ml`, `us-east-1`) |
| `DYNAMODB_TABLE_NAME_MINERALS`, `DYNAMODB_TABLE_NAME_MINING_PRICES` | Las tablas que lee el servicio |

- Las dependencias: `pip install -r tools/etl_minerals/requirements.txt`.

## Los tres pasos

Desde la raíz del repositorio (`app/`). El Excel por defecto es
`../data/cotizaciones_mineras_bolivia.xlsx`; otro se indica con `--source`.

1. **Auditar** (sólo lee): marca los decimales perdidos al re-tipear el PDF.

   ```bash
   python -m tools.etl_minerals.audit_decimals
   ```

2. **Cargar en MySQL**: sin `--yes` sólo informa; con `--yes` escribe. Omite
   las fechas que ya están, así que repetirlo no duplica.

   ```bash
   python -m tools.etl_minerals.ingest_pdf_xlsx
   python -m tools.etl_minerals.ingest_pdf_xlsx --yes
   ```

3. **Publicar en DynamoDB**: copia el catálogo y las cotizaciones y verifica
   los conteos.

   ```bash
   python -m tools.etl_minerals.migrate_to_dynamodb
   python -m tools.etl_minerals.migrate_to_dynamodb --yes
   ```

## El catálogo de minerales

Es la tabla `t_minerals`. La carga compara las cabeceras del Excel contra esa
tabla; una columna cuyo mineral no está ahí (HIERRO CONCENT, PELLET) se informa
y se salta. Un mineral nuevo se da de alta en la tabla, no en el código.
