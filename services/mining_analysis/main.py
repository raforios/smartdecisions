'''
    Mining Analysis Microservice Main Handler
'''
from collections.abc import AsyncGenerator
import socket
from datetime import date, datetime, timezone
from typing import Any
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from mangum import Mangum
import uvicorn

# Router of this microservice
from routes.mining_analysis import router as mining_router
from routes.market import router as market_router
from routes.public_reports import router as public_reports_router

from schemas.health import TableHealth, TablesHealthResponse, TableState
from services.api_exceptions import setup_exception_handlers
from services.security import require_roles
from services.db_connection_sql import ENGINE, Base
from services.logger_config import custom_logger as logger
from services.environment import load_and_validate_env_vars

from services.market_sources import scheduled_sync
from services.prices_store import uses_dynamodb

# Environment variable configuration
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
    }
)

UVICORN_HOST = ENV_VARS['HOST']
UVICORN_PORT = ENV_VARS['PORT']
APP_ENV = ENV_VARS.get('APP_ENV', 'development')

ROOT_PATH_VALUE = ENV_VARS.get('ROOT_PATH', '').strip('/')
ROOT_PATH_NORMALIZED = f'/{ROOT_PATH_VALUE}' if ROOT_PATH_VALUE else ''
# The docs live under the service's own prefix too: api.bearsoft.com.bo only
# routes /v1/<service>/... to this Lambda, so /docs is unreachable through it.
DOCS_BASE = '/v1/mining-analysis'
OPENAPI_URL = f'{DOCS_BASE}/openapi.json'

@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    '''
        Handles the startup and shutdown events.

        Ensures the relational schema exists, but only when the service is
        actually configured to run on it. On DynamoDB there is no schema to
        create and no relational database to reach: doing this unconditionally
        would kill startup in an environment where no RDS is even deployed.
    '''
    if uses_dynamodb():
        message = 'Application startup: quotations run on DynamoDB, no schema to verify.'
        logger.info(message)
        yield
        return

    message = 'Application startup: Verifying Mining Analysis database schema.'
    logger.info(message)
    try:
        Base.metadata.create_all(bind = ENGINE)
        logger.info('Mining database schema verified successfully.')
    except Exception as e:
        error_msg = f'Database initialization failed: {e}'
        logger.critical(error_msg, exc_info = True)
        raise RuntimeError('Critical failure: Database not reachable.') from e

    yield
    logger.info('Application shutdown: Releasing Mining Service resources.')

APP_CONFIG = {
    'root_path': ROOT_PATH_NORMALIZED,
    'title': 'Mining Analysis Service',
    'description': '''
        This microservice is the intelligence core for the mining sector. It
        handles bulk ingest of quotation data through ETL processes, normalizes
        historical prices and exposes metrics for external systems and Business
        Intelligence dashboards.''',
    'version': '1.0.0',
    'contact': {
        'name': 'Mining Tech Support',
        'email': 'support.mining@smartbear.com'
    },
    'lifespan': lifespan,
    # Swagger's "Try it out" calls the host it was opened on, not a stage prefix.
    'root_path_in_servers': False,
    'docs_url': None,
    'redoc_url': None,
    'openapi_url': None
}

app = FastAPI(**APP_CONFIG)
setup_exception_handlers(app)

@app.get('/', tags = ['Healthcheck'])
@app.get(f'{DOCS_BASE}/health', tags = ['Home'])
def root() -> dict[str, Any]:
    '''
        Function root: health check function

        Returns:
            dict[str, Any]: A dictionary with system info.
    '''
    today = datetime.now()
    copyright_symbol = '\u00A9'
    output = {
        'Api Healthcheck': 'OK',
        'Host': socket.gethostname(),
        'Environment': APP_ENV,
        'Status': 'available',
        'Server Date Time': today.isoformat(),
        'Last Update': date.today().isoformat(),
        'Application': 'Python - FastAPI',
        'Database': 'MySQL - Normalized  transactional Database',
        'Owner': f'Ministerio de Minería y Metalurgia {copyright_symbol} {today.year}',
        'Architecture': 'Spec-Driven Development'
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
    'DYNAMODB_TABLE_NAME_MINERALS',
    'DYNAMODB_TABLE_NAME_MINING_PRICES',
    'DYNAMODB_TABLE_NAME_MINING_MARKET_PRICES',
    'DYNAMODB_TABLE_NAME_MINING_ROYALTY_RULES',
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
    return tables_health(boto3.client('dynamodb'), 'mining_analysis',
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
        title = app.title + ' - Docs'
    )

# Standard CORS: an optional explicit list from the environment
# (CORS_ALLOWED_ORIGINS, comma-separated) plus
# one pattern covering our frontends without listing URLs one by one.
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

# Router registration. The public one goes first so it shows up first in /docs.
app.include_router(public_reports_router)
app.include_router(mining_router)
app.include_router(market_router)

def run_local() -> None:
    '''
        Runs the app with Uvicorn for local development. A function so its
        log message does not live at module level, where it shadowed the
        `message` of every other function.
    '''
    message = f'Starting Mining Analysis Service at {UVICORN_HOST}:{UVICORN_PORT}'
    logger.info(message)
    uvicorn.run('main:app', host = UVICORN_HOST, port = UVICORN_PORT, reload = True)


if __name__ == '__main__':
    run_local()

# The Lambda answers two kinds of caller. API Gateway sends HTTP events, which
# Mangum turns into ASGI; EventBridge sends a scheduled event, which has no
# request at all and would make Mangum fail looking for one. Same dispatch as
# QUOTES: the only place that has to know the difference.
_asgi_handler = Mangum(app)
_SCHEDULED_SOURCE = 'aws.events'
_SYNC_TASK = 'sync_market'


def _is_scheduled_sync(event: dict[str, Any]) -> bool:
    '''
        Tells a scheduled invocation apart from an HTTP one.

        Args:
            event (dict[str, Any]): Raw Lambda event.

        Returns:
            bool: True when the event asks for the market sync.
    '''
    if not isinstance(event, dict):
        return False
    return event.get('source') == _SCHEDULED_SOURCE or event.get('task') == _SYNC_TASK


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
            Any: The HTTP response, or the sync result for a scheduled run.

        Raises:
            RuntimeError: If the scheduled sync could not complete, so the
                invocation is marked failed and the retry policy applies.
    '''
    if _is_scheduled_sync(event):
        try:
            result = scheduled_sync(boto3.resource('dynamodb'))
        except HTTPException as error:
            error_msg = f'Scheduled market sync failed: {error.detail}'
            logger.error(error_msg)
            raise RuntimeError(error_msg) from error
        message = (f'Scheduled market sync stored {result.stored} day(s), '
                   f'skipped {result.already_present}, failed sources {result.failed_sources}.')
        logger.info(message)
        return result.model_dump(mode = 'json')
    return _asgi_handler(event, context)
