'''
    Supplies Microservice Main Handler.

    Inventory management for materials and supplies. Wires the router for
    catalog, replenishments, requests, kardex and dashboard endpoints, and
    exposes the Lambda-friendly ASGI handler via Mangum.
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

from routes.catalog import router as catalog_router
from routes.dashboard import router as dashboard_router
from routes.kardex import router as kardex_router
from routes.replenishment import router as replenishment_router
from routes.request import router as request_router

from services.api_exceptions import setup_exception_handlers
from services.db_connection import ENGINE, Base
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
OPENAPI_URL = f'{ROOT_PATH_NORMALIZED}/openapi.json' if ROOT_PATH_NORMALIZED else '/openapi.json'


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    '''
        Initializes database tables at startup. Failing here aborts the
        process so the service does not stay up serving against a half-
        provisioned schema.
    '''
    message = 'Application startup: initializing database tables.'
    logger.info(message)
    try:
        Base.metadata.create_all(bind = ENGINE)
        message = 'Database tables created/verified successfully.'
        logger.info(message)
    except Exception as e:
        error_msg = f'Database initialization failed on startup: {e}'
        logger.critical(error_msg, exc_info = True)
        raise RuntimeError('Database initialization failed during application startup.') from e

    yield

    message = 'Application shutdown: closing resources.'
    logger.info(message)


APP_CONFIG = {
    'root_path': ROOT_PATH_NORMALIZED,
    'title': 'Supplies Service',
    'description': '''
        Inventory microservice for the Ministry. Covers two main processes:

        1. **Replenishments**: detect items below the configured minimum,
           generate orders aimed at an external purchasing system, register
           physical receptions and update the kardex.
        2. **Requests**: end-user supply requests with a full state machine,
           stock validation against the minimum, role-based transitions and
           automatic kardex OUT movements on delivery.

        Includes reports (low-stock, replenishments, requests) and a
        dashboard summary.''',
    'version': '1.0.0',
    'contact': {
        'name': 'API Support',
        'email': 'raforios@gmail.com',
    },
    'lifespan': lifespan,
    'docs_url': None,
    'redoc_url': None,
    'openapi_url': None,
}

app = FastAPI(**APP_CONFIG)

setup_exception_handlers(app)


@app.get('/', tags = ['Home'])
def root() -> Dict[str, Any]:
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
        title = app.title + ' - Docs',
    )


# CORS estándar: lista explícita opcional por env (CORS_ALLOWED_ORIGINS, CSV) +
# un patrón que cubre nuestros frontends sin listar URLs una por una.
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

app.include_router(catalog_router)
app.include_router(replenishment_router)
app.include_router(request_router)
app.include_router(kardex_router)
app.include_router(dashboard_router)


if __name__ == '__main__':
    MESSAGE = f'Starting Uvicorn server at {UVICORN_HOST}:{UVICORN_PORT}'
    logger.info(MESSAGE)
    uvicorn.run('main:app', host = UVICORN_HOST, port = UVICORN_PORT, reload = True)

handler = Mangum(app)
