---
name: revisar-logs
description: Lee los logs reales de CloudWatch de un Lambda antes de diagnosticar nada. Úsala siempre que un servicio desplegado falle, en vez de inferir la causa desde el código.
argument-hint: [servicio] [horas-atras]
allowed-tools: Bash(aws logs *), Bash(aws lambda *), Bash(aws cloudwatch *), Bash(python3 *)
---

Diagnostica el fallo de `$1` **leyendo los logs**, no deduciéndolo.

## La regla

Nunca propongas una causa sin haber visto el error real. Deducir el fallo desde
el código ha llevado a arreglar lo que no estaba roto más de una vez; el mensaje
de CloudWatch suele nombrar el problema con precisión.

## Nombres de los grupos de log

El nombre de la función no siempre coincide con el del servicio:

| Servicio | Función Lambda |
|---|---|
| INGEST | `ingest-handler-service` |
| ANALYTICS | `analytics-handler-service` |
| OPTIMIZATION | `optimization-handler-service` |
| QUOTES | `quotes-handler-service` |
| MINING_ANALYSIS | `mining-handler-service` |
| AI | `ai-handler-service` |
| ML_FUNCTIONS | `ml-functions-handler-service` |
| BILLING | `billing-handler-service` |
| AUTH | `auth-handler-service` |
| EVENTS | `events-handler-service` |
| FILES | `file-handler-service` (singular) |

Si no aparece, búscala:

```bash
aws lambda list-functions --profile deploy_ml \
  --query "Functions[?contains(FunctionName,'$1')].FunctionName" --output text
```

## Los errores

```bash
LG=/aws/lambda/<funcion>
START=$(python3 -c "import time; print(int((time.time() - ${2:-3}*3600)*1000))")

aws logs filter-log-events --log-group-name $LG --start-time $START \
  --profile deploy_ml --filter-pattern 'ERROR' \
  --query 'events[-5:].message' --output text
```

Para el mensaje completo cuando viene truncado, filtra por la palabra clave:

```bash
aws logs filter-log-events --log-group-name $LG --start-time $START \
  --profile deploy_ml --filter-pattern 'ValidationException' \
  --query 'events[-1].message' --output text
```

## Memoria y timeout

Un servicio que “falla sin error” suele estar quedándose sin memoria. La línea
`REPORT` lo dice:

```bash
aws logs filter-log-events --log-group-name $LG --start-time $START \
  --profile deploy_ml --filter-pattern 'REPORT' \
  --query 'events[-10:].message' --output text \
  | grep -oE 'Max Memory Used: [0-9]+ MB|Status: [a-z]+|Duration: [0-9.]+ ms'
```

`Runtime.OutOfMemory` o `Status: timeout` significan `MEMORY_SIZE` o `TIMEOUT`
insuficientes en `deploy.config`. Mide el pico local antes de proponer un número:

```python
import resource
raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
print(raw / (1024*1024) if raw > 10**7 else raw / 1024, 'MB')  # macOS informa bytes
```

## Fallos vistos y su causa real

| Síntoma | Causa |
|---|---|
| `Runtime.OutOfMemory` en el boletín | PIL arma la imagen entera en memoria: 437 MB de pico contra 256 configurados |
| `Unable to marshal response: Object of type date` | El camino programado no tiene FastAPI delante; hay que serializar por el modelo |
| `on-demand throughput isn't supported` | Falta el prefijo `us.` del perfil de inferencia de Bedrock |
| `AccessDenied ... us-east-2` | El perfil de inferencia enruta entre regiones; la política IAM debe llevar comodín |
| `Can't connect to MySQL server on 'localhost'` | Camino de lectura que no pasa por `prices_store` y asume el relacional |
| `NoSuchKey` en la plantilla | Se borró del bucket; se regenera con `tools/build_sales_template.py` |

## Al terminar

Cita **el mensaje literal** que encontraste, di la causa y sólo entonces propón
el arreglo. Si el log no explica el fallo, dilo en vez de inventar una hipótesis.
