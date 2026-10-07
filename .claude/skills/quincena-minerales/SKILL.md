---
name: quincena-minerales
description: La rutina de cada 15 días para cargar las cotizaciones de minerales del Ministerio — auditar el re-tipeo del PDF, cargar el Excel y publicar a DynamoDB. Úsala cuando llegue el archivo nuevo de cotizaciones.
argument-hint: [ruta-del-xlsx]
allowed-tools: Bash(cd *), Bash(python3 -m scripts.*), Bash(python3 *), Bash(aws dynamodb *), Read
---

Ejecuta la carga quincenal de cotizaciones. Fuente por defecto:
`data/cotizaciones_mineras_bolivia.xlsx`, o `$1` si se indica otra.

## Por qué existe este proceso

El Ministerio de Minería entrega las cotizaciones a cambio de que generemos su
boletín en PDF y PNG. Es un intercambio de servicios y **no se toca**. Los datos
llegan en un Excel que un operador arma re-tipeando desde un PDF escaneado, y
ahí se pierden decimales: por eso el primer paso es auditar, no cargar.

## Los tres pasos, en orden

Todo desde `services/mining_analysis/`.

### 1. Auditar antes de cargar

```bash
python3 -m scripts.audit_decimals --source ../../../data/cotizaciones_mineras_bolivia.xlsx
```

Sólo lee. Cruza el promedio que trae el Excel contra el promedio aritmético de
los días y marca las celdas donde no cuadra — casi siempre son decimales
perdidos al copiar del PDF.

**Lee la salida antes de seguir.** Si marca columnas sospechosas, hay que
verificarlas contra el PDF original; cargar sin revisar propaga el error al
boletín que se le entrega al Ministerio.

### 2. Cargar

```bash
PERSISTENCE_BACKEND=sql python3 -m scripts.ingest_pdf_xlsx \
    --source ../../../data/cotizaciones_mineras_bolivia.xlsx        # simulación
PERSISTENCE_BACKEND=sql python3 -m scripts.ingest_pdf_xlsx \
    --source ../../../data/cotizaciones_mineras_bolivia.xlsx --yes  # escribe
```

Idempotente: omite las fechas que ya tienen registro, así que volver a correrlo
sobre el mismo archivo no duplica nada.

**Va contra MySQL local a propósito.** El ETL escribe sólo en el relacional; el
servicio desplegado lee de DynamoDB. Es la opción (a) que se acordó hasta que la
escritura pase por `prices_store`.

### 3. Publicar a la nube

```bash
python3 -m scripts.migrate_to_dynamodb          # informa qué copiaría
python3 -m scripts.migrate_to_dynamodb --yes    # copia y verifica
```

Sin este paso la quincena queda sólo en tu máquina y el servicio desplegado
sigue mostrando la anterior.

## Verificación

Compara los dos caminos: deben dar lo mismo.

```python
python3 - <<'PY'
import asyncio, importlib, os
from datetime import date
from scripts.cli_support import database_session

def leer(backend, sesion):
    os.environ['PERSISTENCE_BACKEND'] = backend
    import services.prices_store as ps; importlib.reload(ps)
    return {m.name: [(p.date, p.price_low) for p in
                     ps.prices_in_window(m.mineral_id, date(2026,1,1), date.today(), sesion)]
            for m in ps.list_minerals(sesion)}

with database_session() as sesion:
    print('idénticos:', leer('sql', sesion) == leer('dynamodb', sesion))
PY
```

Y el boletín, que es lo que se entrega:

```bash
curl -s -o /dev/null -w '%{http_code}\n' \
  'https://api.bearsoft.com.bo/v1/mining-analysis/public/reports/biweekly?year=2026&month=9&half=1'
```

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
