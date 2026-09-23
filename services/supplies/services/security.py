'''
    Security service
'''
from typing import Any, Awaitable, Callable, Dict, Iterable, Optional
from fastapi import Depends, Header
from jose import jwt, JWTError

from services.logger_config import custom_logger as logger
from services.exceptions import ForbiddenError, UnauthorizedError
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


# --------------------------------------------------------------------------- #
# Roles and the client an account belongs to                                  #
# --------------------------------------------------------------------------- #
# AUTH issues the token with three claims: `email` (the user), `role` (what
# they may do) and `client` (the customer that groups them). Data is keyed by
# the client, so a manager and their sellers share routes, plans and stock;
# accounts created before the grouping have no client and keep their email as
# the key, which is exactly how their data was stored.
async def get_current_payload(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    '''
        Validates the token exactly like `get_current_user` and returns its
        whole payload (email, role, client, exp).

        Args:
            authorization (Optional[str]): The 'Authorization' header.

        Returns:
            Dict[str, Any]: The decoded claims.
    '''
    await get_current_user(authorization)
    token = authorization.split(' ', 1)[1]
    return jwt.decode(token, SECRET_KEY, algorithms = [ALGORITHM])


def resolve_owner(payload: Dict[str, Any]) -> str:
    '''
        The key the caller's data lives under: their client, or their email
        when they belong to none.

        Args:
            payload (Dict[str, Any]): Decoded token claims.

        Returns:
            str: Owner key.
    '''
    return payload.get('client') or payload['email']


async def get_current_owner(payload: Dict[str, Any] = Depends(get_current_payload)) -> str:
    '''
        FastAPI dependency: the owner key of the caller's data.

        Args:
            payload (Dict[str, Any]): Decoded token claims.

        Returns:
            str: Owner key.
    '''
    return resolve_owner(payload)


def require_roles(*allowed_roles: str) -> Callable[..., Awaitable[str]]:
    '''
        Dependency factory: the caller's owner key when their role is one of
        `allowed_roles`, ForbiddenError otherwise. Same contract as
        `get_current_owner`, so an endpoint swaps one for the other.

        Args:
            *allowed_roles (str): Role values accepted by the endpoint.

        Returns:
            Callable[..., Awaitable[str]]: A FastAPI dependency resolving to the owner key.
    '''
    allowed: Iterable[str] = tuple(allowed_roles)

    async def _checker(payload: Dict[str, Any] = Depends(get_current_payload)) -> str:
        role: Optional[str] = payload.get('role')
        if role not in allowed:
            error_msg = (
                f'Forbidden: {payload["email"]} with role {role} called an endpoint '
                f'restricted to {list(allowed)}.'
            )
            logger.warning(error_msg)
            raise ForbiddenError(detail = 'ROLE_NOT_ALLOWED')
        return resolve_owner(payload)

    return _checker
