'''
    Auth: routes handler
'''
from fastapi import APIRouter, status
from schemas.auth import LoginRequest, SignupResponse, Token
from schemas.users import UserRequest
from controllers.users import authenticate_user, create_user
from services.logger_config import custom_logger as logger
from services.jwt_token import create_access_token
from services.exceptions import (
    UnauthorizedError,
)

router = APIRouter(prefix = '/v1/auth', tags = ['Authentication'])

@router.post(
    '/login',
    response_model = Token,
    status_code = status.HTTP_200_OK
)
async def login(
    request: LoginRequest
):
    '''
        Login route for obtaining an access token after verifying credentials.
    '''
    user = await authenticate_user(request.email, request.password)
    if not user:
        error_msg = f'Invalid credentials for: {request.email}'
        logger.error(error_msg)
        raise UnauthorizedError(
            detail = 'Incorrect email or password.'
        )

    access_token = create_access_token({'email': user.email})
    message = f'User {user.email} logged in successfully.'
    logger.info(message)
    return Token(access_token = access_token, token_type = 'bearer')

@router.post(
    '/signup',
    response_model = SignupResponse,
    status_code = status.HTTP_201_CREATED
)
async def signup(
    user_data: UserRequest
):
    '''
        Sign-up route for creating a new user and storing their credentials securely.
    '''
    response = await create_user(user_data)
    message = f'User {user_data.email} created successfully'
    logger.info(message)
    return SignupResponse(user_email = response['user_email'], message = response['message'])
