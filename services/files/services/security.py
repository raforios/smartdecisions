'''
    Security service
'''
from typing import Optional
from fastapi import Header
from jose import jwt, JWTError

from services.logger_config import custom_logger as logger
from services.exceptions import UnauthorizedError
from services.environment import load_and_validate_env_vars

ENV_VARS = load_and_validate_env_vars(
    env_vars = {
        'SECRET_KEY': str,
        'ALGORITHM': str,
    }
)
SECRET_KEY = ENV_VARS['SECRET_KEY']
ALGORITHM = ENV_VARS['ALGORITHM']

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

    # Raised outside the try on purpose: UnauthorizedError derives from
    # Exception, so raising it inside would be swallowed by the catch-all above
    # and reported as an unexpected error, hiding the real cause.
    email: str = payload.get('email')

    message = f'User authenticated with email: {email}'
    logger.info(message)

    if email is None:
        raise UnauthorizedError(
            detail = 'No user email was found in the token',
            headers = {'WWW-Authenticate': 'Bearer'},
        )
    return email
