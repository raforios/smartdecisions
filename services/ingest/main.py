'''
    Ingest Microservice Main Handler
'''
import socket
from datetime import date, datetime
from typing import Any, AsyncIterator, Dict
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html

from mangum import Mangum
import uvicorn

from routes.ingest import router as ingest_router

from services.api_exceptions import setup_exception_handlers
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
        'CORS_ALLOWED_ORIGINS': str
    }
)

UVICORN_HOST = ENV_VARS['HOST']
UVICORN_PORT = ENV_VARS['PORT']
APP_ENV = ENV_VARS.get('APP_ENV') or 'development'

ROOT_PATH_VALUE = (ENV_VARS.get('ROOT_PATH') or '').strip('/')
ROOT_PATH_NORMALIZED = f'/{ROOT_PATH_VALUE}' if ROOT_PATH_VALUE else ''
OPENAPI_URL = f'{ROOT_PATH_NORMALIZED}/openapi.json' if ROOT_PATH_NORMALIZED else '/openapi.json'

CORS_ALLOWED_ORIGINS_ENV = ENV_VARS.get('CORS_ALLOWED_ORIGINS') or ''
DEFAULT_CORS_ORIGINS = [
    'http://127.0.0.1:5500',
    'http://localhost:5500',
    'http://127.0.0.1:5501',
    'http://localhost:5501',
    'http://127.0.0.1:8000',
    'http://localhost:8000',
]
ORIGINS = [
    origin.strip() for origin in CORS_ALLOWED_ORIGINS_ENV.split(',') if origin.strip()
] or DEFAULT_CORS_ORIGINS


def _ensure_template_present() -> None:
    '''
        Generates `assets/template_ventas_v1.xlsx` if it is not already on
        disk. The Dockerfile bakes it at build time, but `python main.py`
        in local dev does not — without this step `GET /template/file`
        would 400 with "plantilla aún no disponible".
    '''
    from pathlib import Path
    target = (
        Path(__file__).resolve().parent / 'assets' / 'template_ventas_v1.xlsx'
    )
    if target.exists():
        return
    try:
        from scripts.generate_template import generate
        generate(target)
        message = f'Generated v1 template at {target}.'
        logger.info(message)
    except Exception as e: # pylint: disable=broad-exception-caught
        error_msg = f'Could not pre-generate v1 template: {e}'
        logger.warning(error_msg)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    '''
        Handles startup/shutdown. DynamoDB tables are managed outside the app
        lifecycle (via dynamodb.sh / IaC). Pre-generates the canonical v1
        template if it is missing so `GET /template/file` always works.
    '''
    _ensure_template_present()
    message = 'Ingest startup: DynamoDB-backed service ready.'
    logger.info(message)
    yield
    message = 'Ingest shutdown: closing resources.'
    logger.info(message)


APP_CONFIG = {
    'root_path': ROOT_PATH_NORMALIZED,
    'title': 'Ingest Service',
    'description': (
        'SmartDecisions ingestion microservice: receives sales Excel/CSV files, '
        'validates them against the v1 contract, stores the raw file in S3 via '
        'FILES and persists dataset metadata in DynamoDB. Powers the upload step '
        'of the SmartDecisions self-service POC.'
    ),
    'version': '1.0.0',
    'contact': {
        'name': 'API Support',
        'email': 'raforios@gmail.com'
    },
    'lifespan': lifespan,
    'docs_url': None,
    'redoc_url': None,
    'openapi_url': None
}

app = FastAPI(**APP_CONFIG)

setup_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins = ORIGINS,
    allow_credentials = True,
    allow_methods = ['*'],
    allow_headers = ['*'],
)


@app.get('/', tags = ['Home'])
def root() -> Dict[str, Any]:
    '''
        Health check endpoint.

        Returns:
            Dict[str, Any]: Service metadata and status.
    '''
    today = datetime.now()
    copyright_symbol = '©'
    return {
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


@app.get('/openapi.json', include_in_schema = False)
def custom_openapi():
    '''
        Returns the OpenAPI schema (JSON file) for the service.
    '''
    return app.openapi()


@app.get('/docs', include_in_schema = False)
async def custom_swagger_ui():
    '''
        Serves the Swagger UI documentation interface.
    '''
    return get_swagger_ui_html(
        openapi_url = OPENAPI_URL,
        title = app.title + ' - Docs'
    )


app.include_router(ingest_router)


if __name__ == '__main__':
    MESSAGE = f'Starting Uvicorn server at {UVICORN_HOST}:{UVICORN_PORT}'
    logger.info(MESSAGE)
    uvicorn.run('main:app', host = UVICORN_HOST, port = UVICORN_PORT, reload = True)


handler = Mangum(app)
