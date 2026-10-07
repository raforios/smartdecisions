'''
    Events Microservice Main Handler
'''
from collections.abc import AsyncGenerator
import socket
from datetime import datetime, date
from typing import Any
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.openapi.docs import get_swagger_ui_html

from mangum import Mangum
import uvicorn

from routes.audit import router as audit_router
from routes.usage_log import router as usage_log_router

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
        'ROOT_PATH': str
    }
)

UVICORN_HOST = ENV_VARS['HOST']
UVICORN_PORT = ENV_VARS['PORT']
APP_ENV = ENV_VARS['APP_ENV']

ROOT_PATH_VALUE = ENV_VARS.get('ROOT_PATH', '').strip('/')
ROOT_PATH_NORMALIZED = f'/{ROOT_PATH_VALUE}' if ROOT_PATH_VALUE else ''
# The docs live under the service's own prefix too: api.bearsoft.com.bo only
# routes /v1/<service>/... to this Lambda, so /docs is unreachable through it.
DOCS_BASE = '/v1/events'
OPENAPI_URL = f'{DOCS_BASE}/openapi.json'

@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    '''
        Handles the startup and shutdown events of the FastAPI application.
        DynamoDB tables are managed outside the application lifecycle.
    '''
    message = 'Application startup: Validating DynamoDB table existence.'
    logger.info(message)

    yield

    # Code after yield runs on shutdown (e.g., closing connections)
    message = 'Application shutdown: Closing resources.'
    logger.info(message)

APP_CONFIG = {
    'root_path': ROOT_PATH_NORMALIZED,
    'title': 'Events Service',
    'description': '''
        The Events Microservice is a centralized platform designed for robust event tracking and system observability. 
        It acts as a single source of truth for critical system events, enabling comprehensive monitoring and 
        streamlined debugging. The service has two primary functions: it records audit events to provide detailed 
        traceability of data modifications across all microservices, and it logs API usage events to capture key 
        performance metrics, user activity, and request/response data for in-depth analysis and security.
    ''',
    'version': '1.0.0',
    'contact': {
        'name': 'API Support',
        'email': 'raforios@gmail.com'
    },
    'lifespan': lifespan,

    # Disable automatic documentation routes to use manual routing below
    # Swagger's "Try it out" calls the host it was opened on, not a stage prefix.
    'root_path_in_servers': False,
    'docs_url': None,
    'redoc_url': None,
    'openapi_url': None

}

app = FastAPI(**APP_CONFIG)

setup_exception_handlers(app)

@app.get('/favicon.ico', include_in_schema = False)
async def favicon() -> FileResponse:
    '''
        Serves the favicon.ico file to prevent 404 errors from browsers.
    '''
    return FileResponse('favicon.ico')

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
        'Database': 'AWS DynamoDB',
        'Owner': f'BearSoft {copyright_symbol} {today.year}'
    }
    return output

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

app.include_router(audit_router, tags = ['Events'])
app.include_router(usage_log_router, tags = ['Events'])

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
