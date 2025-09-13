'''
    Forms Microservice Main Handler
'''
import os
import socket
from datetime import datetime, date
from typing import Dict, Any, AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from mangum import Mangum

import uvicorn

from dotenv import dotenv_values

from routes.forms import router as form_router
from routes.responses import router as response_router
from routes.responses import persons_router as person_router

from services.api_exceptions import setup_exception_handlers
from services.db_connection import ENGINE, Base
from services.logger_config import custom_logger as logger

PARAMETERS = dotenv_values('.env')

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
        # Ensure your models (e.g., models/forms.py) are imported somewhere
        # so Base.metadata knows about them. If models.forms is imported by controllers,
        # it's usually fine. Otherwise, you might need to import models.forms here.
        Base.metadata.create_all(bind = ENGINE)
        message = 'Database tables created/verified successfully.'
        logger.info(message)
    except Exception as e:
        error_msg = f'Database initialization failed on startup: {e}'
        logger.critical(error_msg, exc_info = True)
        # Raise to prevent the app from starting if DB init fails critically.
        raise RuntimeError("Database initialization failed during application startup.") from e

    yield # The application will run after the 'yield' statement

    # Code after yield runs on shutdown (e.g., closing connections)
    message = 'Application shutdown: Closing resources.'
    logger.info(message)

app = FastAPI(
    title = 'Forms Service',
    description = '''This service manages the creation, storage, and retrieval of forms,
    including their headers, questions, multiple choice options, and flow logic.''',
    version = '1.0.0',
    lifespan = lifespan
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
        'Database': 'MySQL transactional Database and DynamoDB NoSQL Database for Cache',
        'Owner': f'BearSoft {copyright_symbol} {today.year}'
    }
    return output

app.include_router(form_router, tags = ['Forms'])
app.include_router(response_router, tags = ['Form Responses'])
app.include_router(person_router, tags = ['Persons'])

# Entry point to run the app
if __name__ == '__main__':
    UVICORN_HOST = os.environ.get('HOST', PARAMETERS.get('HOST'))
    UVICORN_PORT = int(os.environ.get('PORT', PARAMETERS.get('PORT')))

    MESSAGE = f'Starting Uvicorn server at {UVICORN_HOST}:{UVICORN_PORT}'
    logger.info(MESSAGE)
    uvicorn.run('main:app', host = UVICORN_HOST, port = UVICORN_PORT, reload = True)

handler = Mangum(app)
