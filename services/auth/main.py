'''
    Auth handler Microservice
'''
import socket
from datetime import date, datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse

from mangum import Mangum

import uvicorn

from routes.auth import router as auth_router
from routes.users import router as users_router

from controllers.users import get_current_admin_user
from schemas.health import TableHealth, TablesHealthResponse, TableState
from services.api_exceptions import setup_exception_handlers
from services.logger_config import custom_logger as logger
from services.environment import load_and_validate_env_vars

ENV_VARS = load_and_validate_env_vars(
    env_vars = {
        'HOST': str,
        'PORT': int,
    },
    optional_env_vars = {
        'APP_ENV': str,
        'ROOT_PATH': str,
        'CORS_ALLOWED_ORIGINS': str,
        'CORS_ALLOWED_ORIGIN_REGEX': str
    }
)

UVICORN_HOST = ENV_VARS['HOST']
UVICORN_PORT = ENV_VARS['PORT']
APP_ENV = ENV_VARS['APP_ENV']

ROOT_PATH_VALUE = ENV_VARS.get('ROOT_PATH', '').strip('/')
ROOT_PATH_NORMALIZED = f'/{ROOT_PATH_VALUE}' if ROOT_PATH_VALUE else ''
# The docs live under the service's own prefix too: api.bearsoft.com.bo only
# routes /v1/<service>/... to this Lambda, so /docs is unreachable through it.
DOCS_BASE = '/v1/auth'
OPENAPI_URL = f'{DOCS_BASE}/openapi.json'

CORS_ALLOWED_ORIGINS_ENV = ENV_VARS.get('CORS_ALLOWED_ORIGINS') or ''
ORIGINS = [
    origin.strip() for origin in CORS_ALLOWED_ORIGINS_ENV.split(',') if origin.strip()
]

# On top of the explicit list (ORIGINS), one pattern covers every frontend we
# have —bearsoft.com.bo subdomains, *.cloudfront.net and localhost— without
# listing them one by one. Overridable with the CORS_ALLOWED_ORIGIN_REGEX env var.
DEFAULT_CORS_ORIGIN_REGEX = (
    r'^https://([a-z0-9-]+\.)*bearsoft\.com\.bo$'
    r'|^https://[a-z0-9-]+\.cloudfront\.net$'
    r'|^https://([a-z0-9-]+\.)*mineria\.gob\.bo$'
    r'|^http://(localhost|127\.0\.0\.1)(:\d+)?$'
)
CORS_ALLOWED_ORIGIN_REGEX = ENV_VARS.get('CORS_ALLOWED_ORIGIN_REGEX') or DEFAULT_CORS_ORIGIN_REGEX


APP_CONFIG = {
    'root_path': ROOT_PATH_NORMALIZED,
    'title': 'Authentication & User Management Service',
    'description': 'Handles user registration, login, JWT management, and user CRUD operations.',
    'version': '1.0.0',
    'contact': {
        'name': 'API Support',
        'email': 'raforios@gmail.com',
    },

    # Disable automatic documentation routes to use manual routing below
    # Swagger's "Try it out" calls the host it was opened on, not a stage prefix.
    'root_path_in_servers': False,
    'docs_url': None,
    'redoc_url': None,
    'openapi_url': None

}

app = FastAPI(**APP_CONFIG)

setup_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins = ORIGINS,
    allow_origin_regex = CORS_ALLOWED_ORIGIN_REGEX,
    allow_credentials = True,
    allow_methods = ['*'],
    allow_headers = ['*'],
)

@app.get('/favicon.ico', include_in_schema = False)
async def favicon() -> FileResponse:
    '''
        Serves the favicon.ico file to prevent 404 errors from browsers.
    '''
    return FileResponse('./favicon.ico')

# Root path (Healtcheck function)
@app.get('/', tags = ['Home'])
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
        'Database': 'DynamoDB NoSQL Database',
        'Owner': f'BearSoft {copyright_symbol} {today.year}'
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
    'TABLE_NAME',
)


@app.get(
    f'{DOCS_BASE}/health/tables',
    response_model = TablesHealthResponse,
    tags = ['Home'],
    dependencies = [Depends(get_current_admin_user)]
)
def tables_health_endpoint() -> TablesHealthResponse:
    '''
        The state of every table this service uses (ADMIN only): the table
        names stay off the public health check (Rafael, 21-oct-2026).
    '''
    names = load_and_validate_env_vars(env_vars = dict.fromkeys(HEALTH_TABLE_VARS, str))
    return tables_health(boto3.client('dynamodb'), 'auth',
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

# Include routers
app.include_router(auth_router, tags = ['Authentication'])
app.include_router(users_router, tags = ['Users'])

# Entry point to run the app
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

handler = Mangum(app)
