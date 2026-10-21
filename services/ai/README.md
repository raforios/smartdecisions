# AI — Interpretation Service

Servicio **base** de BearSoft desde el cierre de la fase 8, el 21-oct-2026
(CLAUDE.md §4).

## Para qué sirve

Convierte en palabras lo que el resto del sistema devuelve como datos y
códigos. Un microservicio devuelve **datos y códigos, nunca texto de cara al
usuario** (CLAUDE.md §6); el portal traduce los códigos cortos a etiquetas, y
lo que no puede hacer —**explicar**— lo hace este servicio: qué dice un estado
de resultados, hasta cuándo alcanza el efectivo en cada escenario, si el
modelo de negocio del dueño se sostiene con sus números.

Tres principios:

1. **Explica lo que recibe, y nada más.** Sin bases de datos de otros, sin
   herramientas, sin ir a buscar nada: si una cifra no está en la pantalla, no
   está en la respuesta.
2. **Lee la respuesta del backend tal cual.** `data` es el JSON que devolvió el
   servicio que produjo la vista, ya validado por su modelo Pydantic; volver a
   declararlo aquí serían dos contratos para una sola cosa.
3. **Las vistas y su redacción viven en la base de datos.** Una vista existe si
   tiene un rol activo en `ai_prompts`: un producto nuevo registra las suyas
   sin cambiar el código de AI, y ajustar un texto no exige desplegar.

El modelo es **Claude Haiku 4.5** por Bedrock (`model_id` de cada rol). Toda
respuesta se muestra con «Texto generado por IA; revísalo antes de decidir»
(política de uso de Anthropic).

## Endpoints y quién puede llamarlos

Todos piden el JWT de AUTH. Los roles no se limitan a `ADMIN` (Rafael,
19-oct-2026: quizá se abra un chat más adelante).

| Método | Ruta | Qué hace |
|---|---|---|
| POST | `/v1/ai/explain` | Explica lo que una vista está mostrando: `{view, data}` |
| GET | `/v1/ai/roles` | Las versiones de cada vista y cuál está activa |
| GET | `/v1/ai/roles/{view}/{version}` | Una versión completa |
| POST | `/v1/ai/roles` | Guarda una versión; con `active: false` no retira las demás |
| PATCH | `/v1/ai/roles/{view}/{version}/active` | La activa (retira las otras de esa vista) o la apaga |

Los cambios de roles y cada explicación generada se auditan en EVENTS. Nada se
borra por la API: volver atrás es activar otra versión.

Los fallos viajan como códigos: `EMPTY_PAYLOAD`, `ROLE_NOT_CONFIGURED`,
`ROLE_NOT_FOUND`, `MODEL_UNAVAILABLE`, `MODEL_REFUSED`, `PARAMETER_MISSING` y
los `PARAMETERS_SERVICE_*`; `portal/demo/js/ai.js` los pasa a palabras.

## Qué servicios lo llaman

- **El portal**: `portal/demo/js/ai.js` pone el botón «¿Qué significa esto?»
  en cada pantalla y manda lo que muestra; `portal/demo/js/prompts.js` edita
  los roles en Parámetros › Prompts de la IA.
- **Ningún servicio del backend** lo llama hoy.
- AI llama a **PARAMETERS** (alcance `ai`, guardado `PARAMETERS_CACHE_SECONDS`)
  y a **EVENTS**, por `API_URL`.

## Variables de entorno

Sólo entorno (CLAUDE.md §5.3). Los valores de negocio —horas de caché, tamaño
máximo del payload, muestra de una lista larga, la pregunta y la temperatura—
están en PARAMETERS, alcance `ai` (`docs/parametros.md`).

| Variable | Qué es |
|---|---|
| `HOST`, `PORT`, `APP_ENV`, `ROOT_PATH` | Servidor local y entorno |
| `SECRET_KEY`, `ALGORITHM` | Verificación del JWT de AUTH |
| `TARGET_TIMEZONE` | Zona horaria de las fechas que registra |
| `API_URL` | Gateway `api.bearsoft.com.bo`, para PARAMETERS y EVENTS |
| `REQUEST_TIMEOUT_SECONDS` | Timeout de esas llamadas |
| `PARAMETERS_CACHE_SECONDS` | Cuánto guarda lo leído de PARAMETERS |
| `DYNAMODB_TABLE_NAME_AI_PROMPTS` | Tabla de roles |
| `DYNAMODB_TABLE_NAME_AI_EXPLANATIONS` | Tabla de caché |
| `BEDROCK_REGION`, `BEDROCK_ANTHROPIC_VERSION` | Proveedor del modelo |

Dos hechos de Bedrock que cuesta encontrar: el `model_id` lleva el prefijo
`us.` del perfil de inferencia (sin él: `on-demand throughput isn't
supported`), y los modelos de Anthropic piden un formulario de caso de uso una
vez por cuenta, que tarda hasta 15 minutos en propagar.

## Tablas

| Tabla | Partición | Orden | Qué guarda |
|---|---|---|---|
| `ai_prompts` | `view` | `version` (N) | El rol de cada vista: `role`, `instructions`, `rules`, `max_tokens`, `model_id`, `active`, `created_at` |
| `ai_explanations` | `cache_key` | — | Explicaciones ya generadas, con TTL en `expires_at` |

La clave del caché es la huella de **vista + payload + versión del rol**: si
cambia cualquiera de los tres, la respuesta sería otra. Por eso, para probar
una redacción nueva hace falta una versión nueva. Una respuesta guardada sale
en ~0,3 s contra ~5 s, y sin pagar el modelo.

Las reglas comunes de los textos nacen de errores vistos: contar diez minerales
donde había nueve, el voseo, cuentas propias mal hechas, comparar un año sin
terminar con uno entero. Están escritas como prohibiciones explícitas, con el
ejemplo textual cuando una sola regla no alcanzó.

Las dos tablas las crea `services/ci/api/create_dynamodb_tables.sh`. El rol del
Lambda necesita `bedrock:InvokeModel` sobre los perfiles de inferencia (con
comodín de región: el perfil enruta entre regiones).

## Cómo correrlo y probarlo

```bash
cd services/ai
python main.py            # puerto del .env (PORT)
python -m pytest -q
pylint --fail-under=10.0 .
```

El modelo nunca se llama en las pruebas. Cubren lo que lo rodea: un rol que
nadie configuró, un caché que serviría una respuesta escrita con otras reglas,
un payload que hay que recortar.

Para probar un texto contra el modelo sin tocar la vista real: guardarlo como
`prueba_<vista>` con una versión propia, llamar a `/v1/ai/explain` con el
payload de la pantalla y borrar después las filas `prueba_*`.

Se despliega con `services/ci/api/start.sh --redeploy ai` (lo despliega
Rafael).

## Qué revisa el CI

Todavía no está en la matriz de `.github/workflows/python-package.yml`. Pylint
da 10.00 sin el `.pylintrc` del repositorio, pero sus tests importan módulos que
leen el `.env` al importarse, y sin `.env` no llegan a correr.

## Creado por

**Rafael Ríos Bascón** — [raforios@gmail.com](mailto:raforios@gmail.com)
