'''
    Trade Microservice Main Handler
'''
import socket
from datetime import datetime, date
from typing import Dict, Any, AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from fastapi.openapi.docs import get_swagger_ui_html

from mangum import Mangum

import uvicorn

from routes.trade import router as trade_router

from services.api_exceptions import setup_exception_handlers
from services.db_connection import ENGINE, Base
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
OPENAPI_URL = f'{ROOT_PATH_NORMALIZED}/openapi.json' if ROOT_PATH_NORMALIZED else '/openapi.json'


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    '''
        Handles the startup and shutdown events of the FastAPI application.
        This is the recommended way to manage application lifecycle, including DB initialization.
    '''
    message = 'Application startup: Attempting to initialize database tables.'
    logger.info(message)
    try:
        # Base.metadata.create_all requires all models to be imported before calling.
        Base.metadata.create_all(bind = ENGINE)
        message = 'Database tables created/verified successfully.'
        logger.info(message)
    except Exception as e:
        error_msg = f'Database initialization failed on startup: {e}'
        logger.critical(error_msg, exc_info = True)
        # Raise to prevent the app from starting if DB init fails critically.
        raise RuntimeError('Database initialization failed during application startup.') from e

    yield

    # Code after yield runs on shutdown (e.g., closing connections)
    message = 'Application shutdown: Closing resources.'
    logger.info(message)

APP_CONFIG = {
    'root_path': ROOT_PATH_NORMALIZED,
    'title': 'Trade Service',
    'description': '''
    This microservice manages the **Trade Marketing** domain, covering:
    1. **Product Catalog:** Atomic generation of unique SKUs based on classification.
    2. **Point of Sale (POS) Management:** Creation of POS records and their initial inventory.
    3. **Inventory Control:** Tracking of stock, including batch number, expiration date, 
    and short date indicators.
    4. **Future extensions:** Support for impulsing, sales, and corresponding reports 
    (as per functional specifications).''',
    'version': '1.0.0',
    'contact': {
        'name': 'API Support',
        'email': 'raforios@gmail.com'
    },
    'lifespan': lifespan,

    # Disable automatic documentation routes to use manual routing below
    'docs_url': None,
    'redoc_url': None,
    'openapi_url': None

}

app = FastAPI(**APP_CONFIG)

setup_exception_handlers(app)

# Root path (Healtcheck function)
@app.get('/', tags = ['Home'])
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
        'Database': 'MySQL transactional Database',
        'Owner': f'BearSoft {copyright_symbol} {today.year}'
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

app.include_router(trade_router, tags = ['Trade'])

# Entry point to run the app
if __name__ == '__main__':
    MESSAGE = f'Starting Uvicorn server at {UVICORN_HOST}:{UVICORN_PORT}'
    logger.info(MESSAGE)
    uvicorn.run('main:app', host = UVICORN_HOST, port = UVICORN_PORT, reload = True)

handler = Mangum(app)
