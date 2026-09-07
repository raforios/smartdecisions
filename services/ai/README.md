# AI Interpretation Service

Microservicio backend del producto **SmartDecisions** (de BearSoft). Es la capa
que convierte en palabras lo que el resto del sistema devuelve como datos y
códigos.

La regla que ordena todo el backend es que un microservicio devuelve **datos y
códigos, nunca texto de cara al usuario**: hay 14 enumeraciones y 165 códigos
estables repartidos entre INGEST, ANALYTICS, OPTIMIZATION, QUOTES y
MINING_ANALYSIS. El frontend traduce los cortos a etiquetas. Lo que no puede
hacer —y por eso existe este servicio— es **explicar**: por qué la proyección de
un mineral es confiable y la de otro no, o qué implica que la próxima cotización
oficial esté marcada como parcial.

## Los tres principios

1. **Explica lo que recibe, y nada más.** Sin acceso a bases de datos, sin
   herramientas, sin ir a buscar nada. Si una cifra no está en la pantalla, no
   está en la respuesta.
2. **Lee lo que el backend respondió, tal cual.** La entrada es el JSON que
   devolvió el servicio que produjo la vista — el mismo objeto que armó su
   propio modelo Pydantic. Volver a declarar esa forma acá serían dos contratos
   para una sola cosa, y escondería campos que el experto podría haber usado.
3. **El rol vive en la base de datos.** La redacción es lo que más se ajusta, y
   ajustarla no debe requerir un despliegue.

## Stack

- Python 3.14 + FastAPI + Uvicorn
- AWS Lambda (handler `Mangum`) + API Gateway
- AWS Bedrock (`boto3`) — Claude Haiku 4.5 por defecto
- AWS DynamoDB: `ai_prompts` y `ai_explanations`
- Autenticación JWT delegada al servicio AUTH

## Estructura

```text
ai/
├── controllers/ai.py     Orquestación entre rutas y servicios.
├── models/ai.py          Ítems DynamoDB: rol versionado y respuesta cacheada.
├── routes/ai.py          Endpoints FastAPI.
├── schemas/ai.py         DTOs, códigos de error y el payload tipado de cada vista.
├── services/
│   ├── ai.py             Módulo principal del dominio.
│   ├── ai_utils.py       Acceso a DynamoDB y clave de caché.
│   └── bedrock_client.py Lo único que habla con Bedrock.
└── tests/
```

## Endpoints

| Método | Ruta | Qué hace |
|---|---|---|
| `POST` | `/v1/ai/explain` | Explica lo que una vista está mostrando. |
| `GET` | `/v1/ai/roles` | Los roles configurados y su versión. |
| `POST` | `/v1/ai/roles` | Guarda una versión del rol de una vista. |

```json
POST /v1/ai/explain
{ "view": "rate_forecast", "data": { ...lo que la vista muestra... } }

200 OK
{ "view": "rate_forecast", "text": "El dólar oficial cierra…",
  "role": "Analista cambiario boliviano…", "model": "us.anthropic.claude-haiku-4-5…",
  "prompt_version": 2, "cached": false, "generated_at": "…" }
```

`data` es **la respuesta del servicio que produjo la vista, sin tocar**. Ya pasó
por un modelo Pydantic del otro lado; volver a declararla acá crearía dos
contratos para una sola cosa. `view` sólo elige el rol con el que se escribe la
respuesta. Los únicos límites son que no venga vacía y que no exceda
`MAX_PAYLOAD_CHARACTERS`.

## Los roles

Viven en `ai_prompts`, partición `view` y ordenamiento `version`. Cada rol trae
quién es el experto, cómo leer esa vista y una lista de reglas. **Se administran
por la API**, con `POST /v1/ai/roles`, no desde el repositorio: la redacción es
un dato del negocio y no código.

Escribir una versión nueva **desactiva la anterior sin borrarla**: un rollback
es cambiar una bandera, no restaurar nada. Y como la versión participa de la
clave de caché, reajustar la redacción deja de servir lo que la versión vieja
había producido, también sin borrar nada.

Las reglas comunes existen por errores reales observados: pedirle que leyera
nueve minerales y que contara diez, y que dedujera el día de la semana de una
fecha y se equivocara. Están escritas como prohibiciones explícitas.

## Caché

`ai_explanations`, partición `cache_key`, con TTL en `expires_at`. La clave es
la huella de **vista + payload + versión del rol**: si cualquiera de los tres
cambia, la respuesta sería otra y no debe servirse de ahí.

Importa más de lo que parece: en una demo se aprieta el mismo botón muchas
veces, y la diferencia entre una respuesta fresca y una guardada es de **~5 s a
~0,3 s** y de pagarla a no pagarla. Un fallo del caché se registra y se ignora:
la respuesta ya se produjo y el llamador tiene que recibirla.

## Bedrock

Dos hechos que cuesta encontrar:

- **Los perfiles de inferencia son obligatorios.** El model ID pelado responde
  `ValidationException: on-demand throughput isn't supported`. Hay que usar el
  prefijo `us.`.
- **Los modelos de Anthropic exigen un formulario de caso de uso**, una vez por
  cuenta, antes de la primera llamada, y tarda hasta quince minutos en propagar.
  Hasta entonces todo falla con `ResourceNotFoundException`.

## Configuración

Toda variable se lee con `load_and_validate_env_vars` y es **requerida**: un
respaldo escrito en el código sigue siendo un número que eligió el código.

| Variable | Qué gobierna |
|---|---|
| `DYNAMODB_TABLE_NAME_AI_PROMPTS` | Tabla de roles. |
| `DYNAMODB_TABLE_NAME_AI_EXPLANATIONS` | Tabla de caché. |
| `BEDROCK_REGION` | Región del proveedor. |
| `BEDROCK_ANTHROPIC_VERSION` | Versión del payload que Bedrock espera. |
| `BEDROCK_TEMPERATURE` | Baja: la misma pantalla no debe leerse distinto. |
| `BEDROCK_DEFAULT_MODEL_ID` | Modelo con el que se siembran los roles. |
| `BEDROCK_DEFAULT_MAX_TOKENS` | Techo de una respuesta. |
| `EXPLANATION_CACHE_HOURS` | Vida de una respuesta cacheada. |
| `MAX_PAYLOAD_CHARACTERS` | Techo de lo que una vista puede mandar. |

## Ejecución local

```bash
pip install -r requirements.txt
python main.py
```

## Tests

```bash
python3 -m pytest tests/ -q       # 14 tests
python3 -m pylint --recursive=y . # 10.00/10
```

El modelo nunca se llama en las pruebas. Lo que cubren es todo lo que lo rodea,
que es donde viven los fallos que importan: un rol que nadie configuró, un caché
que sirve una respuesta escrita bajo otras reglas, una respuesta del backend que
llega recortada. Ninguno de esos aparece como error del proveedor; aparecen
como una explicación segura de la cosa equivocada.

## Despliegue

Las dos tablas se crean con `services/ci/api/create_dynamodb_tables.sh`
(`ai_prompts` tiene clave compuesta, que `build_and_deploy.sh` no sabe crear).
El rol del Lambda necesita **`bedrock:InvokeModel`** sobre los perfiles de
inferencia; el acceso a las dos tablas lo cubre `AmazonDynamoDBFullAccess`, que
el deploy adjunta.
