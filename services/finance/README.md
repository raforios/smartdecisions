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
- **Lo que carga el cliente** queda bajo su `client`, con el usuario que lo cargó.
- **El informe se calcula al pedirlo** y no se guarda: cada línea dice si fue
  cargada o calculada.

## Stack

- Python 3.14 + FastAPI + Uvicorn
- AWS Lambda (handler `Mangum`) + API Gateway
- AWS DynamoDB (`boto3`): `finance_accounts`, `finance_law_parameters`,
  `finance_loads`, `finance_entries`, `finance_suggested_parameters`,
  `finance_client_parameters`
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
| POST | `/v1/finance/loads` · `/v1/finance/loads/file` | `MANAGER` (carga por API o por archivo) |
| GET | `/v1/finance/loads` | `MANAGER` (historial) |
| GET · PATCH · DELETE | `/v1/finance/entries` | `MANAGER` (ver, corregir o borrar un monto) |
| DELETE | `/v1/finance/periods` | `MANAGER` (vaciar un período) |
| GET | `/v1/finance/report` | `MANAGER`: Estado de Resultados, impuestos, Balance e indicadores por mes y año |
| GET · PUT | `/v1/finance/parameters` | `MANAGER` (sus parámetros, junto a la sugerencia) |
| GET · PUT | `/v1/finance/suggested-parameters` | Cualquiera lee; `ADMIN` cambia |

## Valores de negocio

Las cuentas que cumplen cada papel en el informe, los códigos de las tasas,
la historia mínima, la tolerancia del balance y los decimales se leen de
**PARAMETERS** (alcances `finance` y `global`), no del `.env`: el `ADMIN` los
cambia sin redesplegar. Están definidos en `docs/parametros.md`.

## Tablas y siembra

Las tablas se crean con `services/ci/api/create_dynamodb_tables.sh`. El
catálogo y las tasas se siembran desde el contrato aprobado:

```bash
python -m tools.seeds.seed_finance          # simulación
python -m tools.seeds.seed_finance --yes
```

## Local

```bash
cd services/finance
python main.py        # puerto 3160
python -m pytest -q
```
