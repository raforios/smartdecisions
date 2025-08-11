'''
    Planning Microservice Main Handler
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

from routes.planning import router as planning_router

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
        raise RuntimeError('Database initialization failed during application startup.') from e

    yield # The application will run after the 'yield' statement

    # Code after yield runs on shutdown (e.g., closing connections)
    message = 'Application shutdown: Closing resources.'
    logger.info(message)

app = FastAPI(
    title = 'Planning Service',
    description = '''
        This microservice manages the planning process, including the creation and management
        of planning records, the assignment of teams and routes (from the Localization service),
        and the tracking of material assignments. It provides endpoints for creating, retrieving,
        and updating planning records, with filtering capabilities by week and date.
    ''',
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
        'Database': 'MySQL transactional Database',
        'Owner': f'BearSoft {copyright_symbol} {today.year}'
    }
    return output

app.include_router(planning_router, tags = ['Planning'])

# Entry point to run the app
if __name__ == '__main__':
    UVICORN_HOST = os.environ.get('HOST', PARAMETERS.get('HOST'))
    UVICORN_PORT = int(os.environ.get('PORT', PARAMETERS.get('PORT')))

    MESSAGE = f'Starting Uvicorn server at {UVICORN_HOST}:{UVICORN_PORT}'
    logger.info(MESSAGE)
    uvicorn.run('main:app', host = UVICORN_HOST, port = UVICORN_PORT, reload = True)

handler = Mangum(app)
