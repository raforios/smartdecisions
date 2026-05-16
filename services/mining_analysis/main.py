'''
    Mining Analysis Microservice Main Handler
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

# Importación del router del microservicio actual
from routes.mining_analysis import router as mining_router
from routes.public_reports import router as public_reports_router

from services.api_exceptions import setup_exception_handlers
from services.db_connection import ENGINE, Base
from services.logger_config import custom_logger as logger
from services.environment import load_and_validate_env_vars

# Configuración de variables de entorno
ENV_VARS = load_and_validate_env_vars(
    env_vars = {
        'HOST': str,
        'PORT': int,
    },
    optional_env_vars = {
        'APP_ENV': str,
        'ROOT_PATH': str,
        'CORS_ORIGINS': str,
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
        Handles the startup and shutdown events. 
        Ensures t_minerals and t_mining_prices exist.
    '''
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
        Este microservicio es el núcleo de inteligencia para el sector minero. 
        Permite la ingesta masiva de datos de cotización mediante procesos ETL, 
        la normalización de precios históricos y la exposición de métricas para 
        sistemas externos y dashboards de Business Intelligence.''',
    'version': '1.0.0',
    'contact': {
        'name': 'Mining Tech Support',
        'email': 'support.mining@smartbear.com'
    },
    'lifespan': lifespan,
    'docs_url': None,
    'redoc_url': None,
    'openapi_url': None
}

app = FastAPI(**APP_CONFIG)
setup_exception_handlers(app)

@app.get('/', tags = ['Healthcheck'])
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
        'Database': 'MySQL - Normalized  transactional Database',
        'Owner': f'Ministerio de Minería y Metalurgia {copyright_symbol} {today.year}',
        'Architecture': 'Spec-Driven Development'
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

# CORS: pulled from `CORS_ORIGINS` (comma-separated). Defaults cover the
# local dev origins for the Streamlit dashboard and the institutional
# website served via Live Server on port 5500.
_DEFAULT_ORIGINS = (
    'http://127.0.0.1:5500',
    'http://localhost:5500',
    'http://127.0.0.1:8080',
    'http://localhost:8080',
    'http://localhost:8501',
)
_cors_env = ENV_VARS.get('CORS_ORIGINS', '') or ''
origins = [o.strip() for o in _cors_env.split(',') if o.strip()] or list(_DEFAULT_ORIGINS)
app.add_middleware(
    CORSMiddleware,
    allow_origins = origins,
    allow_credentials = True,
    allow_methods = ['*'],
    allow_headers = ['*'],
)

# Inclusión de routers — el público va antes para que aparezca primero en /docs.
app.include_router(public_reports_router)
app.include_router(mining_router)

if __name__ == '__main__':
    MESSAGE = f'Starting Mining Analysis Service at {UVICORN_HOST}:{UVICORN_PORT}'
    logger.info(MESSAGE)
    uvicorn.run('main:app', host = UVICORN_HOST, port = UVICORN_PORT, reload = True)

handler = Mangum(app)
