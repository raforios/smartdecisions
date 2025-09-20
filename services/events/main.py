'''
    Events Microservice Main Handler
'''
import socket
from datetime import datetime, date
from typing import Dict, Any, AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
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
        'APP_ENV': str
    }
)

UVICORN_HOST = ENV_VARS['HOST']
UVICORN_PORT = ENV_VARS['PORT']
APP_ENV = ENV_VARS['APP_ENV']

@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    '''
        Handles the startup and shutdown events of the FastAPI application.
        DynamoDB tables are managed outside the application lifecycle.
    '''
    message = 'Application startup: Validating DynamoDB table existence.'
    logger.info(message)

    yield # The application will run after the 'yield' statement

    # Code after yield runs on shutdown (e.g., closing connections)
    message = 'Application shutdown: Closing resources.'
    logger.info(message)

app = FastAPI(
    title = 'Events Service',
    description = '''
        The Events Microservice is a centralized platform designed for robust event tracking and system observability. 
        It acts as a single source of truth for critical system events, enabling comprehensive monitoring and 
        streamlined debugging. The service has two primary functions: it records audit events to provide detailed 
        traceability of data modifications across all microservices, and it logs API usage events to capture key 
        performance metrics, user activity, and request/response data for in-depth analysis and security.
    ''',
    version = '1.0.0',
    lifespan = lifespan
)

setup_exception_handlers(app)

@app.get('/favicon.ico', include_in_schema = False)
async def favicon():
    '''
        Serves the favicon.ico file to prevent 404 errors from browsers.
    '''
    return FileResponse('favicon.ico')

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
        'Database': 'AWS DynamoDB',
        'Owner': f'BearSoft {copyright_symbol} {today.year}'
    }
    return output

app.include_router(audit_router, tags = ['Events'])
app.include_router(usage_log_router, tags = ['Events'])

# Entry point to run the app
if __name__ == '__main__':
    MESSAGE = f'Starting Uvicorn server at {UVICORN_HOST}:{UVICORN_PORT}'
    logger.info(MESSAGE)
    uvicorn.run('main:app', host = UVICORN_HOST, port = UVICORN_PORT, reload = True)

handler = Mangum(app)
