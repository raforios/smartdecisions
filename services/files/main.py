'''
    File handler Microservice
'''
import socket
from datetime import datetime, date
from typing import Dict, Any
from fastapi import FastAPI

from mangum import Mangum

import uvicorn

from routes.files import router as file_router

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
    'title': 'AWS S3 Bucket File Management Service',
    'description': 'Managing data files stored in AWS S3 buckets',
    'version': '1.0.0',
    'contact': {
        'name': 'API Support',
        'email': 'raforios@gmail.com',
    }
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
        'Database': 'No Database',
        'Owner': f'BearSoft {copyright_symbol} {today.year}'
    }
    return output


# Include routers
app.include_router(file_router, tags = ['Management S3 File System'])

# Entry point to run the app
if __name__ == '__main__':
    MESSAGE = f'Starting Uvicorn server at {UVICORN_HOST}:{UVICORN_PORT}'
    logger.info(MESSAGE)
    uvicorn.run('main:app', host = UVICORN_HOST, port = UVICORN_PORT, reload = True)

handler = Mangum(app)
