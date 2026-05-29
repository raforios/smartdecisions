'''
    Module for global exception handlers.
'''
from fastapi import Request
from fastapi.responses import JSONResponse
from services.logger_config import custom_logger as logger
from services.exceptions import (
    RegisterNotFoundError,
    RegisterAlreadyExistsError,
    InvalidInputError,
    UnauthorizedError,
    ForbiddenError,
    ServiceUnavailableError,
    ResourceNotFoundError
)

def setup_exception_handlers(app):
    '''
        Sets up global exception handlers for the FastAPI application.

        Args:
            app (FastAPI): The FastAPI application instance.
    '''
    @app.exception_handler(RegisterNotFoundError)
    async def register_not_found_exception_handler(
        request: Request, exc: RegisterNotFoundError
    ) -> JSONResponse:
        '''
            Handles RegisterNotFoundError, returning a 404 Not Found response.
        '''
        message = f'Register not found: {exc.detail} for path: {request.url.path}'
        logger.warning(message)
        return JSONResponse(
            status_code = exc.status_code,
            content = {'detail': exc.detail}
        )

    @app.exception_handler(ResourceNotFoundError)
    async def resource_not_found_exception_handler(
        request: Request, exc: ResourceNotFoundError
    ) -> JSONResponse:
        '''
            Handles ResourceNotFoundError, returning a 404 Not Found response.
        '''
        message = f'Resource not found: {exc.detail} for path: {request.url.path}'
        logger.warning(message)
        return JSONResponse(
            status_code = exc.status_code,
            content = {'detail': exc.detail}
        )

    @app.exception_handler(RegisterAlreadyExistsError)
    async def register_already_exists_exception_handler(
        request: Request, exc: RegisterAlreadyExistsError
    ) -> JSONResponse:
        '''
            Handles RegisterAlreadyExistsError, returning a 409 Conflict response.
        '''
        message = f'Register already exists: {exc.detail} for path: {request.url.path}'
        logger.warning(message)
        return JSONResponse(
            status_code = exc.status_code,
            content = {'detail': exc.detail}
        )

    @app.exception_handler(InvalidInputError)
    async def invalid_input_exception_handler(
        request: Request, exc: InvalidInputError
    ) -> JSONResponse:
        '''
            Handles InvalidInputError, returning a 400 Bad Request response.
        '''
        message = f'Invalid input: {exc.detail} for path: {request.url.path}'
        logger.warning(message)
        return JSONResponse(
            status_code = exc.status_code,
            content = {'detail': exc.detail}
        )

    @app.exception_handler(UnauthorizedError)
    async def unauthorized_exception_handler(
        request: Request, exc: UnauthorizedError
    ) -> JSONResponse:
        '''
            Handles UnauthorizedError, returning a 401 Unauthorized response.
        '''
        message = f'Unauthorized access: {exc.detail} for path: {request.url.path}'
        logger.warning(message)
        return JSONResponse(
            status_code = exc.status_code,
            content = {'detail': exc.detail}
        )

    @app.exception_handler(ForbiddenError)
    async def forbidden_exception_handler(
        request: Request, exc: ForbiddenError
    ) -> JSONResponse:
        '''
            Handles ForbiddenError, returning a 403 Forbidden response.
        '''
        message = f'Forbidden access: {exc.detail} for path: {request.url.path}'
        logger.warning(message)
        return JSONResponse(
            status_code = exc.status_code,
            content = {'detail': exc.detail}
        )

    @app.exception_handler(ServiceUnavailableError)
    async def service_unavailable_exception_handler(
        request: Request, exc: ServiceUnavailableError
    ) -> JSONResponse:
        '''
            Handles ServiceUnavailableError, returning a 503 Service Unavailable response.
        '''
        error_msg = f'Service unavailable: {exc.detail} for path: {request.url.path}'
        logger.error(error_msg, exc_info = True)
        return JSONResponse(
            status_code = exc.status_code,
            content = {'detail': exc.detail}
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        '''
            Handles any unhandled exceptions, returning a generic 500 Internal Server Error.
        '''
        error_msg = f'Unhandled exception: {exc} for path: {request.url.path}'
        logger.critical(error_msg)
        return JSONResponse(
            status_code = 500,
            content = {'detail': 'An unexpected internal server error occurred.'}
        )
