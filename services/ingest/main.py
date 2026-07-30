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
from services.template_builder import ensure_template

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
APP_ENV = ENV_VARS.get('APP_ENV') or 'development'

ROOT_PATH_VALUE = (ENV_VARS.get('ROOT_PATH') or '').strip('/')
ROOT_PATH_NORMALIZED = f'/{ROOT_PATH_VALUE}' if ROOT_PATH_VALUE else ''
OPENAPI_URL = f'{ROOT_PATH_NORMALIZED}/openapi.json' if ROOT_PATH_NORMALIZED else '/openapi.json'

CORS_ALLOWED_ORIGINS_ENV = ENV_VARS.get('CORS_ALLOWED_ORIGINS') or ''
ORIGINS = [
    origin.strip() for origin in CORS_ALLOWED_ORIGINS_ENV.split(',') if origin.strip()
]

# Además de la lista explícita (ORIGINS), un patrón cubre todos nuestros frontends
# —subdominios de bearsoft.com.bo, *.cloudfront.net y localhost— sin listarlos uno
# por uno. Se puede sobreescribir con la env var CORS_ALLOWED_ORIGIN_REGEX.
DEFAULT_CORS_ORIGIN_REGEX = (
    r'^https://([a-z0-9-]+\.)*bearsoft\.com\.bo$'
    r'|^https://[a-z0-9-]+\.cloudfront\.net$'
    r'|^https://([a-z0-9-]+\.)*mineria\.gob\.bo$'
    r'|^http://(localhost|127\.0\.0\.1)(:\d+)?$'
)
CORS_ALLOWED_ORIGIN_REGEX = ENV_VARS.get('CORS_ALLOWED_ORIGIN_REGEX') or DEFAULT_CORS_ORIGIN_REGEX


def _ensure_template_present() -> None:
    '''
        Warms up the downloadable template in the writable temp dir at startup.
        The Lambda package (/var/task) is read-only, so the template must live
        in /tmp; `ensure_template()` also regenerates it on demand per request,
        making this a best-effort warm-up rather than a hard requirement.
    '''
    try:
        path = ensure_template()
        message = f'Template ready at {path}.'
        logger.info(message)
    except Exception as e: # pylint: disable=broad-exception-caught
        error_msg = f'Could not pre-generate template: {e}'
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
    allow_origin_regex = CORS_ALLOWED_ORIGIN_REGEX,
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


_asgi_handler = Mangum(app)


def handler(event, context):
    '''
        Lambda entry point. Async self-invocations (background ingest jobs)
        carry an 'ingest_async' key and run the heavy validate/normalize work
        directly; every other event is a normal API Gateway request handled by
        Mangum.
    '''
    if isinstance(event, dict) and 'ingest_async' in event:
        # Imported here so the ASGI cold-start path stays lean.
        from services.async_processor import process_dataset # pylint: disable=import-outside-toplevel
        process_dataset(event['ingest_async'])
        return {'ok': True}
    return _asgi_handler(event, context)
