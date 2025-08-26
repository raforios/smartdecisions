'''
    File handler Microservice
'''
import os
import socket
from datetime import datetime, date
from typing import Dict, Any
from fastapi import FastAPI

from mangum import Mangum

import uvicorn

from dotenv import dotenv_values

from routes.auth import router as auth_router
from routes.users import router as users_router

from services.api_exceptions import setup_exception_handlers
from services.logger_config import custom_logger as logger

PARAMETERS = dotenv_values('.env')

app = FastAPI(
    title = 'Authentication & User Management Service',
    description = 'Handles user registration, login, JWT management, and user CRUD operations.',
    version = '1.0.0',
    contact = {
        'name': 'API Support',
        'email': 'raforios@gmail.com',
    },
)

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
        'Environment': os.environ.get('APP_ENV', PARAMETERS.get('APP_ENV')),
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
    UVICORN_HOST = os.environ.get('HOST', PARAMETERS.get('HOST'))
    UVICORN_PORT = int(os.environ.get('PORT', PARAMETERS.get('PORT')))

    MESSAGE = f'Starting Uvicorn server at {UVICORN_HOST}:{UVICORN_PORT}'
    logger.info(MESSAGE)
    uvicorn.run('main:app', host = UVICORN_HOST, port = UVICORN_PORT, reload = True)

handler = Mangum(app)
