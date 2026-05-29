'''
    Security service.

    Exposes:
        - get_current_user: dependency returning the authenticated user's email.
        - get_current_payload: dependency returning the full JWT payload (email + role).
        - require_roles: factory that builds a dependency enforcing role-based access.
'''
import os
from typing import Any, Dict, Iterable, Optional
from fastapi import Depends, Header
from jose import jwt, JWTError

from dotenv import dotenv_values

from services.logger_config import custom_logger as logger
from services.exceptions import (
    ForbiddenError,
    ServiceUnavailableError,
    UnauthorizedError
)

_LOCAL_ENV_PARAMS = dotenv_values('.env') if os.path.exists('.env') else {}

SECRET_KEY = os.environ.get('SECRET_KEY') or \
                      _LOCAL_ENV_PARAMS.get('SECRET_KEY')

if not SECRET_KEY:
    error_msg = 'SECRET_KEY is not configured in environment or .env.'
    logger.critical(error_msg)
    raise ServiceUnavailableError(
        detail = error_msg
    )

ALGORITHM = os.environ.get('ALGORITHM') or \
                      _LOCAL_ENV_PARAMS.get('ALGORITHM')

if not ALGORITHM:
    error_msg = 'ALGORITHM for JWT is not configured in environment or .env.'
    logger.critical(error_msg)
    raise ServiceUnavailableError(
        detail = error_msg
    )


def _decode_token(authorization: Optional[str]) -> Dict[str, Any]:
    '''
        Decodes the Bearer JWT from the Authorization header and returns its payload.

        Raises:
            UnauthorizedError: If the token is missing, malformed, or invalid.
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
        return jwt.decode(token, SECRET_KEY, algorithms = [ALGORITHM])
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


async def get_current_user(authorization: Optional[str] = Header(None)) -> str:
    '''
        Validates the JWT and returns the authenticated user's email.

        Kept compatible with the rest of the boilerplate: services that only
        need the user identity continue to use this dependency.

        Returns:
            str: The email address embedded in the token.
    '''
    payload = _decode_token(authorization)
    email: Optional[str] = payload.get('email')

    message = f'User authenticated with email: {email}'
    logger.info(message)

    if email is None:
        raise UnauthorizedError(
            detail = 'No user email was found in the token',
            headers = {'WWW-Authenticate': 'Bearer'},
        )
    return email


async def get_current_payload(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    '''
        Validates the JWT and returns the full payload (email, role, exp, ...).

        Use this dependency when the endpoint needs role information.
    '''
    payload = _decode_token(authorization)
    if not payload.get('email'):
        raise UnauthorizedError(
            detail = 'No user email was found in the token',
            headers = {'WWW-Authenticate': 'Bearer'},
        )
    return payload


def require_roles(*allowed_roles: str):
    '''
        Dependency factory that enforces role-based access control.

        The JWT issued by AUTH carries the user's role under the 'role' claim.
        This factory returns a FastAPI dependency that resolves to the user's
        email (matching the get_current_user contract) when the role is allowed,
        and raises ForbiddenError otherwise.

        Example:
            @router.post('/items', dependencies=[Depends(require_roles('ADMIN'))])

        Or, when the email is needed:
            async def endpoint(current_user: str = Depends(require_roles('ADMIN'))):
                ...

        Args:
            *allowed_roles (str): One or more role values accepted by the endpoint.

        Returns:
            Callable: A FastAPI dependency.
    '''
    allowed: Iterable[str] = tuple(allowed_roles)

    async def _checker(payload: Dict[str, Any] = Depends(get_current_payload)) -> str:
        user_role: Optional[str] = payload.get('role')
        email: str = payload.get('email')
        if user_role not in allowed:
            message = (f'Forbidden: user {email} with role {user_role} attempted '
                       f'to access an endpoint restricted to {list(allowed)}.')
            logger.warning(message)
            raise ForbiddenError(
                detail = f'Role "{user_role}" is not authorized for this operation.'
            )
        return email

    return _checker
