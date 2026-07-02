'''
    CMS Microservice Main Handler
'''
import socket
from datetime import datetime, date
from typing import Dict, Any, AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from mangum import Mangum
import uvicorn

from routes.public_cms import router as public_cms_router
from routes.admin_cms import router as admin_cms_router

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
        'CORS_ALLOWED_ORIGIN_REGEX': str,
    }
)

UVICORN_HOST = ENV_VARS['HOST']
UVICORN_PORT = ENV_VARS['PORT']
APP_ENV = ENV_VARS.get('APP_ENV', 'development')

ROOT_PATH_VALUE = ENV_VARS.get('ROOT_PATH', '').strip('/')
ROOT_PATH_NORMALIZED = f'/{ROOT_PATH_VALUE}' if ROOT_PATH_VALUE else ''
OPENAPI_URL = f'{ROOT_PATH_NORMALIZED}/openapi.json' if ROOT_PATH_NORMALIZED else '/openapi.json'

@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    '''
        Handles startup and shutdown events.

        DynamoDB tables are provisioned out-of-band (dynamodb.sh / IaC),
        so this hook only logs lifecycle events.
    '''
    message = 'CMS startup: DynamoDB-backed service ready.'
    logger.info(message)
    yield
    message = 'CMS shutdown: releasing resources.'
    logger.info(message)


APP_CONFIG = {
    'root_path': ROOT_PATH_NORMALIZED,
    'title': 'CMS Service',
    'description': '''
        Microservicio de contenidos del portal público.
        Expone endpoints públicos de lectura (consumidos por el sitio) y
        endpoints administrativos protegidos por JWT para gestionar
        noticias, documentos, slider y entidades adscritas.
        Persistencia en DynamoDB; los archivos binarios se delegan al
        microservicio FILES (S3) y aquí solo se guardan las referencias
        (bucket + key).
    ''',
    'version': '1.0.0',
    'contact': {
        'name': 'CMS Tech Support',
        'email': 'support.cms@smartbear.com',
    },
    'lifespan': lifespan,
    'docs_url': None,
    'redoc_url': None,
    'openapi_url': None,
}

app = FastAPI(**APP_CONFIG)
setup_exception_handlers(app)


@app.get('/', tags = ['Healthcheck'])
def root() -> Dict[str, Any]:
    '''
        Health check endpoint.

        Returns:
            Dict[str, Any]: Service runtime metadata.
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
        'Database': 'AWS DynamoDB',
        'Owner': f'Ministerio de Minería y Metalurgia {copyright_symbol} {today.year}',
        'Architecture': 'Spec-Driven Development',
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
        title = app.title + ' - Docs'
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

# Public routers come first so they appear first in /docs. Admin routes
# (JWT-protected) cover the editorial CRUD consumed by the operator panel.
app.include_router(public_cms_router)
app.include_router(admin_cms_router)

if __name__ == '__main__':
    MESSAGE = f'Starting CMS Service at {UVICORN_HOST}:{UVICORN_PORT}'
    logger.info(MESSAGE)
    uvicorn.run('main:app', host = UVICORN_HOST, port = UVICORN_PORT, reload = True)

handler = Mangum(app)
