---
name: quincena-minerales
description: La rutina de cada 15 días para cargar las cotizaciones de minerales del Ministerio — auditar el re-tipeo del PDF, cargar el Excel y publicar a DynamoDB. Úsala cuando llegue el archivo nuevo de cotizaciones.
argument-hint: [ruta-del-xlsx]
allowed-tools: Bash(cd *), Bash(python -m tools.etl_minerals.*), Bash(python3 *), Bash(aws dynamodb *), Read
---

Ejecuta la carga quincenal de cotizaciones. Fuente por defecto:
`data/cotizaciones_mineras_bolivia.xlsx`, o `$1` si se indica otra.

## Por qué existe este proceso

El Ministerio de Minería entrega las cotizaciones a cambio de que generemos su
boletín en PDF y PNG. Es un intercambio de servicios y **no se toca**. Los datos
llegan en un Excel que un operador arma re-tipeando desde un PDF escaneado, y
ahí se pierden decimales: por eso el primer paso es auditar, no cargar.

## Los tres pasos, en orden

Todo desde la raíz del repositorio (`app/`), con `tools/etl_minerals/`: es
independiente del API, tiene su propio `.env` y su propio MySQL (contenedor
`mining_db`, puerto 3310). El servicio MINING_ANALYSIS sólo lee DynamoDB
desde el 2-nov-2026. Entorno y detalle: `tools/etl_minerals/README.md`.

### 1. Auditar antes de cargar

```bash
python -m tools.etl_minerals.audit_decimals --source ../data/cotizaciones_mineras_bolivia.xlsx
```

Sólo lee. Cruza el promedio que trae el Excel contra el promedio aritmético de
los días y marca las celdas donde no cuadra — casi siempre son decimales
perdidos al copiar del PDF.

**Lee la salida antes de seguir.** Si marca columnas sospechosas, hay que
verificarlas contra el PDF original; cargar sin revisar propaga el error al
boletín que se le entrega al Ministerio.

### 2. Cargar en el MySQL de la herramienta

```bash
python -m tools.etl_minerals.ingest_pdf_xlsx --source ../data/cotizaciones_mineras_bolivia.xlsx        # simulación
python -m tools.etl_minerals.ingest_pdf_xlsx --source ../data/cotizaciones_mineras_bolivia.xlsx --yes  # escribe
```

Idempotente: omite las fechas que ya tienen registro, así que volver a correrlo
sobre el mismo archivo no duplica nada.

### 3. Publicar a la nube

```bash
python -m tools.etl_minerals.migrate_to_dynamodb          # informa qué copiaría
python -m tools.etl_minerals.migrate_to_dynamodb --yes    # copia y verifica los conteos
```

Sin este paso la quincena queda sólo en tu máquina y el servicio desplegado
sigue mostrando la anterior.

## Verificación

El paso 3 ya compara los conteos de MySQL y DynamoDB. Después, el boletín,
que es lo que se entrega: se genera en Streamlit (PDF y PNG de la quincena),
que lee `/v1/mining-analysis/reports/biweekly` con token.

## Reglas de negocio que no se negocian

- **La cotización oficial de una quincena es el promedio de la quincena
  anterior.** La media del 1 al 15 rige del 16 al 30. Es el precio con el que se
  liquida, no la última cotización del día.
- **El promedio va sobre los registros que ese mineral tenga.** Estaño puede
  tener 10 y Wólfram 2 en la misma quincena, y ambos promedios son correctos.
- **El boletín redondea a dos decimales con `ROUND_HALF_UP`**, en su propio
  renderizador. `f'{12.825:.2f}'` da 12.82 y eso sería un error publicado.

## Al terminar

Reporta cuántos días se cargaron, el rango de fechas y si la auditoría dejó algo
por revisar.
