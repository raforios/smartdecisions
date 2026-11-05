'''
    JWT Service Provider
'''
from datetime import datetime, timedelta, timezone
from typing import Any
from jose import jwt, JWTError

from schemas.auth import AuthError
from services.logger_config import custom_logger as logger
from services.exceptions import ServiceUnavailableError
from services.environment import load_and_validate_env_vars

ENV_VARS = load_and_validate_env_vars({
    'SECRET_KEY': str,
    'ALGORITHM': str,
    'ACCESS_TOKEN_EXPIRE_MINUTES': int
})

SECRET_KEY = ENV_VARS['SECRET_KEY']
ALGORITHM = ENV_VARS['ALGORITHM']
ACCESS_TOKEN_EXPIRE_MINUTES = ENV_VARS['ACCESS_TOKEN_EXPIRE_MINUTES']

def create_access_token(data: dict[str, Any]) -> str:
    '''
        Signs a token with the configured lifetime.

        Args:
            data (dict[str, Any]): The claims: email, role and client.

        Returns:
            str: The token.

        Raises:
            ServiceUnavailableError: TOKEN_NOT_ISSUED.
    '''
    expire = datetime.now(timezone.utc) + timedelta(minutes = ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {**data, 'exp': expire.timestamp()}

    try:
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm = ALGORITHM)
        message = f'JWT created for user: {data.get('email')}'
        logger.info(message)
        return encoded_jwt
    except JWTError as e:
        error_msg = f'Error creating JWT token for user {data.get('email')}: {e}'
        logger.critical(error_msg)
        raise ServiceUnavailableError(detail = AuthError.TOKEN_NOT_ISSUED.value) from e

def decode_access_token(token: str) -> dict[str, Any] | None:
    '''
        The claims of a valid token.

        Args:
            token (str): The token as received.

        Returns:
            dict[str, Any] | None: The claims; None for an expired or forged
                token.
    '''
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms = [ALGORITHM])
        message = f'JWT decoded successfully. Payload email: {payload.get('email')}'
        logger.info(message)
        return payload
    except JWTError as e:
        error_msg = f'Invalid JWT token: {e}'
        logger.warning(error_msg)
        return None
