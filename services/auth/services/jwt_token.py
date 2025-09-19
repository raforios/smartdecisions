'''
    JWT Service Provider
'''
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
from jose import jwt, JWTError

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

def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    '''
        Creates a JWT access token.
        data: Dictionary of data to include in the token (e.g., email, user_id).
        expires_delta: Optional, the token's lifetime. If not specified,
        use ACCESS_TOKEN_EXPIRE_MINUTES.
    '''
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes = int(ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({'exp': expire.timestamp()})

    try:
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm = ALGORITHM)
        message = f'JWT created for user: {data.get('email')}'
        logger.info(message)
        return encoded_jwt
    except Exception as e:
        error_msg = f'Error creating JWT token for user {data.get('email')}: {e}'
        logger.critical(error_msg)
        raise ServiceUnavailableError(
            detail = 'Failed to create authentication token.'
        ) from e

def decode_access_token(
    token: str
) -> Optional[Dict[str, Any]]:
    '''
        Decodes and validates a JWT access token.
        Returns the token data if valid, None if not.
    '''
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms = [ALGORITHM])
        message = f'JWT decoded successfully. Payload email: {payload.get('email')}'
        logger.info(message)
        return payload
    except JWTError as e:
        message = f'Invalid JWT token: {e}'
        logger.warning(message)
        return None
