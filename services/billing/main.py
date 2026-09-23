'''
    Supplies Microservice Main Handler.

    Billing for pharmacies: the catalogue a shop sells, the batches it
    receives, and the two documents that move them — the nota de compra and
    the nota de venta. Wires the billing router and exposes the
    Lambda-friendly ASGI handler via Mangum.
'''
import socket
from datetime import date, datetime
from typing import Any, AsyncIterator, Dict
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse

from mangum import Mangum
import uvicorn

from routes.billing import router as billing_router

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
def custom_openapi() -> Dict[str, Any]:
    '''
        Returns the OpenAPI schema (JSON file) for the service.
    '''
    return app.openapi()


@app.get('/docs', include_in_schema = False)
async def custom_swagger_ui() -> HTMLResponse:
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

app.include_router(billing_router)


if __name__ == '__main__':
    message = f'Starting Uvicorn server at {UVICORN_HOST}:{UVICORN_PORT}' # pylint: disable=invalid-name
    logger.info(message)
    uvicorn.run('main:app', host = UVICORN_HOST, port = UVICORN_PORT, reload = True)

handler = Mangum(app)
