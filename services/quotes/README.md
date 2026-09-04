# Quotes Service

Microservicio backend del producto **SmartDecisions** (de BearSoft). Guarda y
sirve la **cotización oficial del dólar** que publica el Banco Central de
Bolivia, y sobre esa serie responde la pregunta que un minero se hace antes de
cerrar: **¿vendo hoy o espero?**

La comparación existe porque se mueven las dos puntas: el mineral se cotiza en
dólares y el dólar se cotiza en bolivianos. Esperar puede ganar de un lado y
perder del otro, y lo que el vendedor decide es la diferencia en bolivianos.

## El quiebre de régimen del 27 de junio de 2026

Es el hecho que ordena todo lo demás. Antes de esa fecha el tipo de cambio
estuvo fijo en 6.86 durante años; desde entonces flota, y se movió más en dos
meses que en la década anterior. Una proyección ajustada sobre la historia
completa concluiría que el dólar se queda en 6.86. Por eso la serie que se
sirve y la que se proyecta **arrancan en el régimen flotante**, y la fecha vive
en `.env` (`FLOAT_REGIME_START`): es un dato del país, no del código.

## Stack

- Python 3.14 + FastAPI + Uvicorn
- AWS Lambda (handler `Mangum`) + API Gateway
- AWS DynamoDB (`boto3`), tabla `exchange_rates`
- numpy para el ajuste por mínimos cuadrados
- Autenticación JWT delegada al servicio AUTH

## Estructura

```text
quotes/
├── controllers/        # Orquestación entre rutas y servicios.
│   └── quotes.py
├── models/             # Definición del ítem DynamoDB.
│   └── quotes.py
├── routes/             # Endpoints FastAPI.
│   └── quotes.py
├── schemas/            # Modelos Pydantic V2 y códigos de error.
│   └── quotes.py
├── services/           # Lógica de negocio + boilerplate compartido.
│   ├── quotes.py         # Módulo principal del dominio.
│   ├── bcb_source.py     # Lectura de la publicación del BCB.
│   ├── quotes_utils.py   # Acceso a DynamoDB.
│   └── rate_forecast.py  # Proyección del tipo de cambio.
└── tests/
    ├── conftest.py         # Store en memoria compartido.
    ├── test_quotes.py      # Dominio.
    └── test_controllers.py # Cada endpoint devuelve su modelo armado.
```

## Almacenamiento

Tabla `exchange_rates`, clave compuesta: partición `currency`, ordenamiento
`date`. La clave de ordenamiento es lo que permite leer un rango de fechas en
una sola consulta; sin ella cada gráfico costaría un scan.

**Por qué guardamos una copia.** El BCB sirve **una fecha por request**, así
que armar una serie en vivo significaría una llamada por día de historia en
cada pantalla. Guardarla también hace que la serie sobreviva a que la fuente se
caiga, que para una cifra con la que se cierra una venta es la diferencia entre
una respuesta vieja y ninguna respuesta.

## Endpoints

Todos exigen el header `Authorization` validado contra AUTH.

| Método | Ruta | Qué hace |
|---|---|---|
| `GET` | `/v1/quotes/exchange-rates` | Devuelve la serie almacenada. Sin cota inferior arranca en el régimen flotante. |
| `POST` | `/v1/quotes/exchange-rates/sync` | Trae del BCB las fechas recientes que falten. Idempotente. |
| `POST` | `/v1/quotes/sale-scenario` | Compara vender hoy contra esperar. |

### `POST /v1/quotes/sale-scenario`

```json
{
  "quantity": 100,
  "unit_price_usd": 2500,
  "days_ahead": 30,
  "mineral_change_percent": -3.2
}
```

`mineral_change_percent` es **entrada del llamador**, no algo que este servicio
salga a buscar: viene de la proyección de MINING_ANALYSIS. Mantenerlo como
entrada permite responder con el supuesto que el vendedor quiera probar —
incluido ninguno, que valoriza solo el movimiento del dólar.

La respuesta trae las dos puntas valorizadas y `difference_bob`, que es lo que
vale la decisión. Ejemplo real sobre 69 días de historia, 100 t a USD 2.500:

| | Tipo de cambio | USD | Bolivianos |
|---|---|---|---|
| Hoy | 12.32 | 250.000 | 3.080.000 |
| En 30 días | 13.4234 | 242.000 | 3.248.471 |
| | | | **+168.471 (+5,47%)** |

## Qué pasa cuando no se puede responder

El backend devuelve **datos y códigos**, nunca frases: la interpretación es del
frontend o de la capa de IA.

- **La proyección no se fuerza.** Si la historia no alcanza, `projected` viene
  en `null` y `rate_confidence` dice por qué (`INSUFFICIENT`). El llamador
  igual recibe la cifra de hoy.
- **Un ajuste que se desploma se rechaza, no se recorta.** Si la recta
  proyectada cae por debajo de la mitad del mínimo observado, deja de describir
  la moneda: se descarta en lugar de publicar un número que nadie debería creer.
- **La confianza siempre viaja.** `HIGH` desde 90 días de historia, `MEDIUM`
  desde 45, `LOW` por encima del mínimo de 15. Una serie flaca nunca se
  presenta con el mismo peso que una completa.
- **Si el BCB cambia de forma**, `bcb_source` responde `SOURCE_UNREADABLE` en
  vez de adivinar qué columna es el tipo de cambio.

Códigos en `schemas/quotes.py`: `SOURCE_UNAVAILABLE`, `SOURCE_UNREADABLE`,
`NO_RATE_PUBLISHED`, `EMPTY_PERIOD`, `INVALID_DATE_RANGE`.

## Configuración

Toda variable se lee con `load_and_validate_env_vars` de
`services/environment.py`, en el módulo que la usa. Los umbrales de negocio
están en `.env`, no incrustados en el código:

| Variable | Default | Qué gobierna |
|---|---|---|
| `DYNAMODB_TABLE_NAME_EXCHANGE_RATES` | — | Tabla de la serie. |
| `FLOAT_REGIME_START` | `2026-06-27` | Dónde arranca la serie comparable. |
| `SYNC_MAX_DAYS` | `400` | Techo de un sync, para no golpear al BCB una hora. |
| `SCENARIO_MAX_DAYS` | `90` | Horizonte máximo del escenario. |
| `SCHEDULED_SYNC_DAYS` | `7` | Días que repara cada corrida programada. |
| `RATE_FORECAST_MIN_DAYS` | `15` | Debajo de esto la proyección describe el ruido. |
| `RATE_FORECAST_MEDIUM_CONFIDENCE_DAYS` | `45` | Umbral de `MEDIUM`. |
| `RATE_FORECAST_HIGH_CONFIDENCE_DAYS` | `90` | Umbral de `HIGH`. |

**Gotcha:** a las variables opcionales ausentes `load_and_validate_env_vars` les
asigna `None` explícito, así que el default se aplica con `or`, no con
`dict.get(name, default)`.

## Actualización automática del tipo de cambio

El BCB sirve **una fecha por request**, así que la serie no se llena sola: hay
que pedirle cada día. Eso lo hace una regla de EventBridge que invoca este mismo
Lambda una vez al día.

```text
EventBridge  cron(0 13 * * ? *)   →  Lambda  →  handler() ve {"task":"sync_rates"}
      13:00 UTC = 09:00 La Paz                  →  scheduled_sync_service()
```

**El Lambda atiende dos tipos de llamador.** API Gateway manda eventos HTTP, que
Mangum convierte en ASGI; EventBridge manda un evento programado, que no trae
petición alguna y haría fallar a Mangum buscándola. El `handler` de `main.py` es
el único lugar que conoce esa diferencia; todo lo demás sigue igual.

**La ventana la decide el dominio, no el cron.** Cada corrida cubre
`SCHEDULED_SYNC_DAYS` días (7 por defecto), no solo ayer: el BCB no publica fines
de semana ni feriados, y una corrida que falló tiene que repararla la siguiente.
Releer una fecha ya guardada no cuesta nada — el sync la saltea sin preguntarle a
la fuente.

**Si el sync falla, la invocación falla.** El handler convierte el error en
`RuntimeError` a propósito, para que EventBridge reintente y el fallo se vea en
las métricas. Devolver un éxito silencioso dejaría un hueco en la serie que nadie
notaría hasta que alguien liquide una venta con una cotización vieja.

### Crear la regla

```bash
bash services/ci/api/create_schedules.sh
```

Idempotente. **Se corre después de desplegar**, no antes: la regla invoca al
Lambda que esté publicado, y una versión sin el dispatch fallaría al recibir un
evento sin petición HTTP.

### Probarla sin esperar al horario

```bash
aws lambda invoke --function-name quotes-handler-service \
    --payload '{"task":"sync_rates"}' --cli-binary-format raw-in-base64-out \
    --profile deploy_ml /dev/stdout
```

## Ejecución local

```bash
pip install -r requirements.txt
python main.py
```

## Tests

```bash
python3 -m pytest tests/ -q      # 17 tests
python3 -m pylint --recursive=y . # 10.00/10
```

`test_controllers.py` existe por una falla real de producción en los servicios
hermanos: los servicios pasaron a devolver DTOs mientras los controllers
seguían expandiéndolos con `**`, lo que revienta solo cuando corre el endpoint.
Las pruebas de dominio quedaban en verde y la API devolvía 500.

## Nota sobre `rate_forecast.py`

Es la misma aritmética que la proyección de minerales de MINING_ANALYSIS, y es
una **copia deliberada**: son servicios que se despliegan por separado con
dependencias empaquetadas por separado, la misma razón por la que el
boilerplate se copia en vez de importarse. Lo que no puede divergir es el
comportamiento, y por eso las reglas están escritas explícitas en el encabezado
del archivo.

## Despliegue

`deploy.config` declara la tabla con clave compuesta. `build_and_deploy.sh`
todavía no crea claves compuestas: la tabla se crea con
`services/ci/api/create_dynamodb_tables.sh`, que sí las soporta. El `.env`
completo viaja a las variables de entorno del Lambda.
