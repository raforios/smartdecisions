'''
    Security service
'''
import os
from typing import Any, Dict, Iterable, Optional
from fastapi import Depends, Header
from jose import jwt, JWTError

from dotenv import dotenv_values

from services.logger_config import custom_logger as logger
from services.exceptions import ForbiddenError, UnauthorizedError, ServiceUnavailableError

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
# Supplies-specific additions                                                 #
#                                                                             #
# Everything above is the shared boilerplate, byte-identical to the reference #
# (localization). Supplies also enforces role-based access — the warehouse    #
# flows differ for REQUESTER, WAREHOUSE_MANAGER and ADMIN — which needs the   #
# full JWT payload, not just the email. These three helpers provide that and  #
# are appended here so a diff against the reference stays readable.           #
#                                                                             #
# If another service ends up needing role guards, promote this block into the #
# shared boilerplate instead of copying it.                                   #
# --------------------------------------------------------------------------- #
def _decode_token(authorization: Optional[str]) -> Dict[str, Any]:
    '''
        Decodes the Bearer JWT from the Authorization header and returns its
        payload, applying the same validation as get_current_user.

        Args:
            authorization (Optional[str]): The 'Authorization' header.

        Returns:
            Dict[str, Any]: The decoded JWT payload.

        Raises:
            UnauthorizedError: If the token is missing, malformed or invalid.
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


async def get_current_payload(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    '''
        Validates the JWT and returns the full payload (email, role, exp, ...).

        Used by endpoints that need the role, where get_current_user's email
        alone is not enough.

        Args:
            authorization (Optional[str]): The 'Authorization' header.

        Returns:
            Dict[str, Any]: The decoded JWT payload.

        Raises:
            UnauthorizedError: If the token is invalid or carries no email.
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
        The returned dependency resolves to the user's email — matching the
        get_current_user contract, so endpoints can use it as a drop-in — and
        raises ForbiddenError when the role is not allowed.

        Example:
            @router.post('/items', dependencies = [Depends(require_roles('ADMIN'))])

        Args:
            *allowed_roles (str): One or more role values accepted by the endpoint.

        Returns:
            Callable: A FastAPI dependency resolving to the caller's email.
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
