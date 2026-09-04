'''
    Quotes Microservice Main Handler
'''
import asyncio
import socket
from datetime import date, datetime
from typing import Any, AsyncIterator, Dict
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html

from mangum import Mangum
import uvicorn

from routes.quotes import router as quotes_router
from schemas.quotes import SyncResult

from services.api_exceptions import setup_exception_handlers
from services.environment import load_and_validate_env_vars
from services.logger_config import custom_logger as logger
from services.quotes import scheduled_sync_service

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
APP_ENV = ENV_VARS.get('APP_ENV') or 'development'

ROOT_PATH_VALUE = (ENV_VARS.get('ROOT_PATH') or '').strip('/')
ROOT_PATH_NORMALIZED = f'/{ROOT_PATH_VALUE}' if ROOT_PATH_VALUE else ''
OPENAPI_URL = f'{ROOT_PATH_NORMALIZED}/openapi.json' if ROOT_PATH_NORMALIZED else '/openapi.json'

CORS_ALLOWED_ORIGINS_ENV = ENV_VARS.get('CORS_ALLOWED_ORIGINS') or ''
ORIGINS = [
    origin.strip() for origin in CORS_ALLOWED_ORIGINS_ENV.split(',') if origin.strip()
]

# Además de la lista explícita (ORIGINS), un patrón cubre todos nuestros frontends
# —subdominios de bearsoft.com.bo, *.cloudfront.net y localhost— sin listarlos uno
# por uno. Se puede sobreescribir con la env var CORS_ALLOWED_ORIGIN_REGEX.
DEFAULT_CORS_ORIGIN_REGEX = (
    r'^https://([a-z0-9-]+\.)*bearsoft\.com\.bo$'
    r'|^https://[a-z0-9-]+\.cloudfront\.net$'
    r'|^https://([a-z0-9-]+\.)*mineria\.gob\.bo$'
    r'|^http://(localhost|127\.0\.0\.1)(:\d+)?$'
)
CORS_ALLOWED_ORIGIN_REGEX = ENV_VARS.get('CORS_ALLOWED_ORIGIN_REGEX') or DEFAULT_CORS_ORIGIN_REGEX


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    '''
        Handles startup/shutdown. DynamoDB tables are managed outside the app
        lifecycle (via dynamodb.sh / IaC); we only log readiness here.
    '''
    message = 'Quotes startup: DynamoDB-backed service ready.'
    logger.info(message)
    yield
    message = 'Quotes shutdown: closing resources.'
    logger.info(message)


APP_CONFIG = {
    'root_path': ROOT_PATH_NORMALIZED,
    'title': 'Quotes Service',
    'description': (
        'SmartDecisions quotes microservice — the "Afinidad × Drop Size" '
        'engine that turns an ingested sales dataset into prioritized, '
        'monetary-impact-ranked opportunities per point of sale.'
    ),
    'version': '1.0.0',
    'contact': {
        'name': 'API Support',
        'email': 'raforios@gmail.com'
    },
    'lifespan': lifespan,
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


@app.get('/', tags = ['Home'])
def root() -> Dict[str, Any]:
    '''
        Health check endpoint.

        Returns:
            Dict[str, Any]: Service metadata and status.
    '''
    today = datetime.now()
    copyright_symbol = '©'
    return {
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


app.include_router(quotes_router)


if __name__ == '__main__':
    MESSAGE = f'Starting Uvicorn server at {UVICORN_HOST}:{UVICORN_PORT}'
    logger.info(MESSAGE)
    uvicorn.run('main:app', host = UVICORN_HOST, port = UVICORN_PORT, reload = True)


# The Lambda answers two kinds of caller. API Gateway sends HTTP events, which
# Mangum turns into ASGI; EventBridge sends a scheduled event, which has no
# request at all and would make Mangum fail looking for one. The dispatch below
# is the only place that has to know the difference.
_asgi_handler = Mangum(app)

# What a scheduled event looks like, and what a manual test invocation can send
# to reach the same path from the console.
_SCHEDULED_SOURCE = 'aws.events'
_SYNC_TASK = 'sync_rates'


def _is_scheduled_sync(event: Dict[str, Any]) -> bool:
    '''
        Tells a scheduled invocation apart from an HTTP one.

        Args:
            event (Dict[str, Any]): Raw Lambda event.

        Returns:
            bool: True when the event asks for the rate sync.
    '''
    if not isinstance(event, dict):
        return False
    return (event.get('source') == _SCHEDULED_SOURCE
            or event.get('task') == _SYNC_TASK)


def handler(event: Dict[str, Any], context: Any) -> Any:
    '''
        Lambda entry point.

        Args:
            event (Dict[str, Any]): Raw Lambda event.
            context (Any): Lambda context, passed through to Mangum.

        Returns:
            Any: The HTTP response, or the sync result for a scheduled run.

        Raises:
            RuntimeError: If the scheduled sync could not complete. Raised so
                the invocation is marked as failed and the retry policy applies;
                a silent success would leave the series with a hole nobody sees.
    '''
    if _is_scheduled_sync(event):
        try:
            result = asyncio.run(scheduled_sync_service())
        except HTTPException as error:
            error_msg = f'Scheduled rate sync failed: {error.detail}'
            logger.error(error_msg)
            raise RuntimeError(error_msg) from error
        message = (f"Scheduled rate sync stored {result['stored']} day(s), "
                   f"skipped {result['already_present']} already present.")
        logger.info(message)
        # Through the response model: the payload carries `date` objects, and the
        # Lambda runtime can only marshal JSON. On the HTTP path FastAPI does this
        # conversion; a scheduled invocation has no FastAPI in front of it, so
        # returning the raw dict fails after the work is already done — the sync
        # succeeds and the invocation still reports an error.
        return SyncResult(**result).model_dump(mode = 'json')

    return _asgi_handler(event, context)
