# Parameters Service

Servicio **base** de BearSoft, como AUTH, EVENTS y FILES. Guarda los
**valores de negocio que se cambian sin redesplegar**: decimales, medidas,
unidades y, en general, lo que antes estaba en el `.env` de cada servicio
(Rafael, 17-oct-2026). El `.env` queda sólo para el entorno: URLs, tablas,
credenciales, región y timeouts de red (CLAUDE.md §5.3).

Lo propio del dominio de un servicio **no** va aquí: se queda en sus tablas
(por ejemplo, las tasas de ley y los parámetros de cada cliente de FINANCE).

## Cómo se organiza

Cada parámetro tiene un **alcance**: `global` para lo que usa más de un
servicio, o el nombre del servicio que lo lee (`finance`). Tiene además un
tipo (`NUMBER`, `TEXT` o `LIST`), un valor y una descripción de qué gobierna.

## Endpoints

| Método | Ruta | Quién |
|---|---|---|
| GET | `/v1/parameters/{scope}` | Cualquier usuario autenticado (un servicio reenvía el token de quien llama) |
| GET | `/v1/parameters` | `ADMIN` (todos) |
| PUT | `/v1/parameters/{scope}/{code}` | `ADMIN` |
| DELETE | `/v1/parameters/{scope}/{code}` | `ADMIN` |

Un servicio lee su alcance y `global` por HTTP, nunca la tabla, y guarda lo
leído unos minutos: cambiar un valor no exige desplegar nada.

## Stack

- Python 3.14 + FastAPI + Uvicorn, AWS Lambda (`Mangum`) + API Gateway
- DynamoDB: `parameters_values` (`scope` + `code`)
- JWT de AUTH; auditoría y uso en EVENTS

## Local

```bash
cd services/parameters
python main.py        # puerto 3170
python -m pytest -q
```
