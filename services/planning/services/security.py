'''
    Security service
'''
import os
from typing import Optional
from fastapi import Header
from jose import jwt, JWTError

from dotenv import dotenv_values

from services.logger_config import custom_logger as logger
from services.exceptions import UnauthorizedError, ServiceUnavailableError

_LOCAL_ENV_PARAMS = dotenv_values('.env') if os.path.exists('.env') else {}

SECRET_KEY = os.environ.get('SECRET_KEY') or \
                      _LOCAL_ENV_PARAMS.get('SECRET_KEY')

if not SECRET_KEY:
    ERROR_MSG = 'SECRET_KEY is not configured in environment or .env.'
    logger.critical(ERROR_MSG)
    raise ServiceUnavailableError(
        detail = ERROR_MSG
    )

ALGORITHM = os.environ.get('ALGORITHM') or \
                      _LOCAL_ENV_PARAMS.get('ALGORITHM')

if not ALGORITHM:
    ERROR_MSG = 'ALGORITHM for JWT is not configured in environment or .env.'
    logger.critical(ERROR_MSG)
    raise ServiceUnavailableError(
        detail = ERROR_MSG
    )

async def get_current_user(authorization: Optional[str] = Header(None)) -> str:
    '''
        Validates the JWT authentication token from the 'Authorization' header.

        Extracts and decodes the token, verifying its validity and the presence
        of a user email. This function is designed to be used as a dependency
        in FastAPI path operations to secure endpoints.

        Args:
            authorization (Optional[str]): The 'Authorization' header containing
                                        the Bearer token (e.g., "Bearer YOUR_TOKEN").

        Returns:
            str: The email address of the authenticated user if the token is valid.

        Raises:
            UnauthorizedError: If the token is invalid, expired, or missing.
    '''
    if not authorization:
        raise UnauthorizedError(
            detail = 'Authentication token not provided',
            headers = {'WWW-Authenticate': 'Bearer'},
        )

    try:
        token_prefix, token = authorization.split(' ', 1)
        if token_prefix.lower() != 'bearer':
            raise UnauthorizedError(
                detail = 'Invalid token format, expected "Bearer"',
                headers = {'WWW-Authenticate': 'Bearer'},
            )
    except ValueError as e:
        raise UnauthorizedError(
            detail = 'Invalid token format, expected "Bearer"',
            headers = {'WWW-Authenticate': 'Bearer'},
        ) from e

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms = [ALGORITHM])
        email: str = payload.get('email')

        message = f'User authenticated with email: {email} ------'
        logger.info(message)

        if email is None:
            raise UnauthorizedError(
                detail = 'No user email was found in the token',
                headers = {'WWW-Authenticate': 'Bearer'},
            )
        return email
    except JWTError as e:
        raise UnauthorizedError(
            detail = 'Invalid credentials',
            headers = {'WWW-Authenticate': 'Bearer'},
        ) from e
    except Exception as e:
        raise UnauthorizedError(
            detail = 'An unexpected authentication error occurred',
            headers = {'WWW-Authenticate': 'Bearer'},
        ) from e
