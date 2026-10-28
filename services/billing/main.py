'''
    Supplies Microservice Main Handler.

    Billing for pharmacies: the catalogue a shop sells, the batches it
    receives, and the two documents that move them — the nota de compra and
    the nota de venta. Wires the billing router and exposes the
    Lambda-friendly ASGI handler via Mangum.
'''
from collections.abc import AsyncIterator
import socket
from datetime import date, datetime, timezone
from typing import Any
from contextlib import asynccontextmanager

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse

from mangum import Mangum
import uvicorn

from routes.billing import router as billing_router
from routes.billing_cash import router as billing_cash_router
from routes.billing_customers import router as billing_customers_router
from routes.billing_siat import router as billing_siat_router

from schemas.health import TableHealth, TablesHealthResponse, TableState
from services import billing_contingency
from services.api_exceptions import setup_exception_handlers
from services.db_connection import dynamodb_resource
from services.security import require_roles
from services.environment import load_and_validate_env_vars
from services.logger_config import custom_logger as logger


ENV_VARS = load_and_validate_env_vars(
    env_vars = {
        'HOST': str,
        'PORT': int,
    },
    optional_env_vars = {
        'APP_ENV': str,
        'ROOT_PATH': str,
        'CORS_ALLOWED_ORIGINS': str,
        'CORS_ALLOWED_ORIGIN_REGEX': str,
    },
)

UVICORN_HOST = ENV_VARS['HOST']
UVICORN_PORT = ENV_VARS['PORT']
APP_ENV = ENV_VARS['APP_ENV']

ROOT_PATH_VALUE = ENV_VARS.get('ROOT_PATH', '').strip('/') if ENV_VARS.get('ROOT_PATH') else ''
ROOT_PATH_NORMALIZED = f'/{ROOT_PATH_VALUE}' if ROOT_PATH_VALUE else ''
# The docs live under the service's own prefix too: api.bearsoft.com.bo only
# routes /v1/<service>/... to this Lambda, so /docs is unreachable through it.
DOCS_BASE = '/v1/billing'
OPENAPI_URL = f'{DOCS_BASE}/openapi.json'


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    '''
        Nothing to provision at startup.

        The DynamoDB tables are created by `services/ci/api/
        create_dynamodb_tables.sh`, which is reviewed and run on purpose. A
        service that provisioned its own storage on every cold start would be
        one deploy away from creating a table nobody agreed to.
    '''
    message = 'Application startup: billing service ready.'
    logger.info(message)
    yield

    message = 'Application shutdown: closing resources.'
    logger.info(message)


APP_CONFIG = {
    'root_path': ROOT_PATH_NORMALIZED,
    'title': 'Supplies Service',
    'description': '''
        Billing for pharmacies, on DynamoDB and multi-tenant: the owner of
        every row is the shop the token names.

        1. **Catálogo y lotes**: each SKU carries its batches, and each batch
           its own cost and shelf price — the laboratory sets both per
           purchase.
        2. **Nota de compra**: what a laboratory or distributor delivered;
           every line becomes a batch.
        3. **Nota de venta**: sells oldest-expiry-first (FEFO), takes the
           units out under a condition so two tills cannot oversell, and can
           be cancelled back into the very batches it emptied.

        Includes the counter dashboard: what was sold today, the margin it
        left, and what is about to expire.''',
    'version': '1.0.0',
    'contact': {
        'name': 'API Support',
        'email': 'raforios@gmail.com',
    },
    'lifespan': lifespan,
    # Swagger's "Try it out" calls the host it was opened on, not a stage prefix.
    'root_path_in_servers': False,
    'docs_url': None,
    'redoc_url': None,
    'openapi_url': None,
}

app = FastAPI(**APP_CONFIG)

setup_exception_handlers(app)


@app.get('/', tags = ['Home'])
@app.get(f'{DOCS_BASE}/health', tags = ['Home'])
def root() -> dict[str, Any]:
    '''
        Healthcheck endpoint. Returns runtime metadata for monitoring.
    '''
    today = datetime.now()
    copyright_symbol = '©'
    output = {
        'Api Healthcheck': 'OK',
        'Host': socket.gethostname(),
        'Environment': APP_ENV,
        'Status': 'available',
        'Server Date Time': today.isoformat(),
        'Last Update': date.today().isoformat(),
        'Application': 'Python - FastAPI',
        'Database': 'MySQL transactional Database',
        'Owner': f'BearSoft {copyright_symbol} {today.year}',
    }
    return output


# The health of the tables lives here, in the service shell, next to the
# public health check: every service answers it the same way.
def describe_table(
    client: Any,
    name: str
) -> TableHealth:
    '''
        One table as DynamoDB describes it. A table that does not exist is
        MISSING; one that cannot be read for any other reason, UNREACHABLE.

        Args:
            client (Any): A boto3 DynamoDB client.
            name (str): Table name.

        Returns:
            TableHealth: The table's state and DynamoDB's approximate counts.
    '''
    try:
        table = client.describe_table(TableName = name)['Table']
    except ClientError as error:
        code = error.response.get('Error', {}).get('Code')
        if code == 'ResourceNotFoundException':
            error_msg = f'Health check: table {name} does not exist.'
            logger.error(error_msg)
            return TableHealth(name = name, status = TableState.MISSING)
        error_msg = f'Health check: table {name} could not be described ({code}).'
        logger.error(error_msg)
        return TableHealth(name = name, status = TableState.UNREACHABLE)
    except BotoCoreError as error:
        error_msg = f'Health check: table {name} could not be described: {error}'
        logger.error(error_msg)
        return TableHealth(name = name, status = TableState.UNREACHABLE)
    return TableHealth(
        name = name,
        status = TableState(table['TableStatus']),
        item_count = table.get('ItemCount'),
        size_bytes = table.get('TableSizeBytes')
    )


def tables_health(
    client: Any,
    service: str,
    names: list[str]
) -> TablesHealthResponse:
    '''
        Every table the service uses, and whether all of them are active.

        Args:
            client (Any): A boto3 DynamoDB client.
            service (str): Service code.
            names (list[str]): The service's table names.

        Returns:
            TablesHealthResponse: One entry per table.
    '''
    tables = [describe_table(client, name) for name in names]
    message = f'Health check of {service}: {len(tables)} tables read.'
    logger.info(message)
    return TablesHealthResponse(
        service = service,
        healthy = all(table.status == TableState.ACTIVE for table in tables),
        checked_at = datetime.now(timezone.utc),
        tables = tables
    )


# The tables this service reads and writes, by the variables that name them.
HEALTH_TABLE_VARS = (
    'DYNAMODB_TABLE_NAME_BILLING_PRODUCTS',
    'DYNAMODB_TABLE_NAME_BILLING_LOTS',
    'DYNAMODB_TABLE_NAME_BILLING_SALES',
    'DYNAMODB_TABLE_NAME_BILLING_PURCHASES',
    'DYNAMODB_TABLE_NAME_BILLING_SETTINGS',
    'DYNAMODB_TABLE_NAME_BILLING_CASH_SESSIONS',
    'DYNAMODB_TABLE_NAME_BILLING_CASH_MOVEMENTS',
    'DYNAMODB_TABLE_NAME_SERVICE_PARAMETERS',
)


@app.get(
    f'{DOCS_BASE}/health/tables',
    response_model = TablesHealthResponse,
    tags = ['Home'],
    dependencies = [Depends(require_roles('ADMIN'))]
)
def tables_health_endpoint() -> TablesHealthResponse:
    '''
        The state of every table this service uses (ADMIN only): the table
        names stay off the public health check (Rafael, 21-oct-2026).
    '''
    names = load_and_validate_env_vars(env_vars = dict.fromkeys(HEALTH_TABLE_VARS, str))
    return tables_health(boto3.client('dynamodb'), 'billing',
                         [names[variable] for variable in HEALTH_TABLE_VARS])


@app.get('/openapi.json', include_in_schema = False)
@app.get(OPENAPI_URL, include_in_schema = False)
def custom_openapi() -> dict[str, Any]:
    '''
        Returns the OpenAPI schema (JSON file) for the service.
    '''
    return app.openapi()


@app.get('/docs', include_in_schema = False)
@app.get(f'{DOCS_BASE}/docs', include_in_schema = False)
async def custom_swagger_ui() -> HTMLResponse:
    '''
        Serves the Swagger UI documentation interface.
    '''
    return get_swagger_ui_html(
        openapi_url = OPENAPI_URL,
        title = app.title + ' - Docs',
    )


# Standard CORS: an optional explicit list from the environment
# (CORS_ALLOWED_ORIGINS, comma-separated) plus a pattern that covers our own
# frontends without naming every URL one by one.
CORS_ALLOWED_ORIGINS_ENV = ENV_VARS.get('CORS_ALLOWED_ORIGINS') or ''
ORIGINS = [
    origin.strip() for origin in CORS_ALLOWED_ORIGINS_ENV.split(',') if origin.strip()
]
DEFAULT_CORS_ORIGIN_REGEX = (
    r'^https://([a-z0-9-]+\.)*bearsoft\.com\.bo$'
    r'|^https://[a-z0-9-]+\.cloudfront\.net$'
    r'|^https://([a-z0-9-]+\.)*mineria\.gob\.bo$'
    r'|^http://(localhost|127\.0\.0\.1)(:\d+)?$'
)
CORS_ALLOWED_ORIGIN_REGEX = ENV_VARS.get('CORS_ALLOWED_ORIGIN_REGEX') or DEFAULT_CORS_ORIGIN_REGEX

app.add_middleware(
    CORSMiddleware,
    allow_origins = ORIGINS,
    allow_origin_regex = CORS_ALLOWED_ORIGIN_REGEX,
    allow_credentials = True,
    allow_methods = ['*'],
    allow_headers = ['*'],
)

app.include_router(billing_router)
app.include_router(billing_cash_router)
app.include_router(billing_customers_router)
app.include_router(billing_siat_router)


def run_local() -> None:
    '''
        Runs the app with Uvicorn for local development. A function so its
        log message does not live at module level, where it shadowed the
        `message` of every other function.
    '''
    message = f'Starting Uvicorn server at {UVICORN_HOST}:{UVICORN_PORT}'
    logger.info(message)
    uvicorn.run('main:app', host = UVICORN_HOST, port = UVICORN_PORT, reload = True)


if __name__ == '__main__':
    run_local()

# The Lambda answers two kinds of caller. API Gateway sends HTTP events, which
# Mangum turns into ASGI; EventBridge sends the contingency run, which has no
# request at all and would make Mangum fail looking for one. The dispatch below
# is the only place that has to know the difference — the same one QUOTES uses.
_asgi_handler = Mangum(app)

# What the scheduled event carries, from `ci/api/create_schedules.sh`.
_CONTINGENCY_TASK = 'siat_contingency'


def handler(
    event: dict[str, Any],
    context: Any
) -> Any:
    '''
        Lambda entry point.

        Args:
            event (dict[str, Any]): Raw Lambda event.
            context (Any): Lambda context, passed through to Mangum.

        Returns:
            Any: The HTTP response, or what the contingency run touched.
    '''
    if isinstance(event, dict) and event.get('task') == _CONTINGENCY_TASK:
        done = billing_contingency.run_scheduled(dynamodb_resource)
        message = f'Scheduled SIAT contingency run touched {len(done)} row(s).'
        logger.info(message)
        return {'touched': done}
    return _asgi_handler(event, context)
