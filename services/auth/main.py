'''
    File handler Microservice
'''
import socket
from datetime import datetime, date
from typing import Dict, Any
from fastapi import FastAPI
from fastapi.responses import FileResponse

from mangum import Mangum

import uvicorn

from routes.auth import router as auth_router
from routes.users import router as users_router

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


APP_CONFIG = {
    'title': 'Authentication & User Management Service',
    'description': 'Handles user registration, login, JWT management, and user CRUD operations.',
    'version': '1.0.0',
    'contact': {
        'name': 'API Support',
        'email': 'raforios@gmail.com',
    }
}

app = FastAPI(**APP_CONFIG)

setup_exception_handlers(app)

@app.get('/favicon.ico', include_in_schema = False)
async def favicon():
    '''
        Serves the favicon.ico file to prevent 404 errors from browsers.
    '''
    return FileResponse('./favicon.ico')

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
        'Database': 'DynamoDB NoSQL Database',
        'Owner': f'BearSoft {copyright_symbol} {today.year}'
    }
    return output

# Include routers
app.include_router(auth_router, tags = ['Authentication'])
app.include_router(users_router, tags = ['Users'])

# Entry point to run the app
if __name__ == '__main__':
    MESSAGE = f'Starting Uvicorn server at {UVICORN_HOST}:{UVICORN_PORT}'
    logger.info(MESSAGE)
    uvicorn.run('main:app', host = UVICORN_HOST, port = UVICORN_PORT, reload = True)

handler = Mangum(app)
