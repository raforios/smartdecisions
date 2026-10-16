# Finance Service

Microservicio backend del producto **SmartDecisions** (de BearSoft): el
**Análisis Financiero**. Con cifras agregadas por cuenta —diarias, mensuales o
anuales, en bolivianos— arma el Estado de Resultados y el Balance General, y
responde las preguntas del gerente con escenarios.

No es un sistema contable: busca cifras lo más reales posible sin seguir la
norma al detalle. El contrato de datos vive en
`docs/cambios/smartdecisions/contrato.md` y el plan, en `plan.md` del mismo
directorio.

## Lo global y lo del cliente

- **El catálogo de cuentas es uno solo, de BearSoft.** Sólo el `ADMIN` lo
  cambia; el cliente lo lee.
- **Las tasas de ley** (IVA, IT, IUE) son una para todos y guardan la fecha
  desde la que rigen: un mes se calcula con la tasa vigente en ese mes.
- **Lo que carga el cliente** queda bajo su `client` (fase 3).

## Stack

- Python 3.14 + FastAPI + Uvicorn
- AWS Lambda (handler `Mangum`) + API Gateway
- AWS DynamoDB (`boto3`): `finance_accounts`, `finance_law_parameters`
- Autenticación JWT delegada al servicio AUTH; auditoría y uso en EVENTS

## Endpoints

| Método | Ruta | Quién |
|---|---|---|
| GET | `/v1/finance/accounts` | Cualquier usuario autenticado |
| POST | `/v1/finance/accounts` | `ADMIN` |
| PATCH | `/v1/finance/accounts/{account_code}` | `ADMIN` (sólo el nombre) |
| DELETE | `/v1/finance/accounts/{account_code}` | `ADMIN` |
| GET | `/v1/finance/law-parameters` | Cualquier usuario autenticado |
| POST | `/v1/finance/law-parameters` | `ADMIN` |

## Tablas y siembra

Las tablas se crean con `services/ci/api/create_dynamodb_tables.sh`. El
catálogo y las tasas se siembran desde el contrato aprobado:

```bash
python -m tools.seed_finance          # simulación
python -m tools.seed_finance --yes
```

## Local

```bash
cd services/finance
python main.py        # puerto 3160
python -m pytest -q
```
