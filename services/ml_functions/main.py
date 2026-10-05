'''
    Machine Learning handler Microservice
'''
import socket
from datetime import datetime, date
from typing import Dict, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.openapi.docs import get_swagger_ui_html

from mangum import Mangum

import uvicorn

from routes.classification import router as classification_router
from routes.prediction import router as prediction_router
from routes.common import router as common_router

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
DOCS_BASE = '/v1/common'
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
    'title': 'Machine Learning Service',
    'description': '''It is a Machine Learning service that uses Regression algorithms
    (linear, logarithmic, gradient) and Sigmoid, with and without data normalization.''',
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
def root() -> Dict[str, Any]:
    '''
        Function root: health check function

        Returns:
            Dict[str, Any]: A dictionary with system info.
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
        'Database': 'No Database',
        'Owner': f'BearSoft {copyright_symbol} {today.year}'
    }
    return output

@app.get('/openapi.json', include_in_schema = False)
@app.get(OPENAPI_URL, include_in_schema = False)
def custom_openapi() -> Dict[str, Any]:
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
app.include_router(classification_router, tags = ['ML Classification'])
app.include_router(prediction_router, tags = ['ML Prediction'])
app.include_router(common_router, tags = ['ML Common Functions'])

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
