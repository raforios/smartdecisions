'''
    Auth: routes handler
'''
from fastapi import APIRouter, Depends, status
from schemas.auth import LoginRequest, SignupResponse, Token
from schemas.users import UserRequest
from controllers.users import (
    authenticate_user,
    create_user,
    get_current_admin_user,
    record_login
)
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
async def login(request: LoginRequest) -> Token:
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

    # `client` groups every user of one customer: downstream services key
    # their data by it, so a manager and their sellers see the same routes,
    # plans and stock. Users without a client keep their email as the key.
    access_token = create_access_token(
        {'email': user.email, 'role': user.role, 'client': user.client}
    )
    record_login(user)
    message = f'User {user.email} logged in successfully.'
    logger.info(message)
    return Token(access_token = access_token, token_type = 'bearer')

@router.post(
    '/signup',
    response_model = SignupResponse,
    status_code = status.HTTP_201_CREATED,
    # Only an ADMIN signs users up (Rafael, 19-oct-2026): an open sign-up let
    # anyone create an account. The new user starts as REQUESTER without a
    # client; the ADMIN then sets role and client with PATCH /v1/users/{email}.
    dependencies = [Depends(get_current_admin_user)]
)
async def signup(user_data: UserRequest) -> SignupResponse:
    '''
        Sign-up route for creating a new user and storing their credentials securely.
    '''
    response = await create_user(user_data)
    message = f'User {user_data.email} created successfully'
    logger.info(message)
    return SignupResponse(user_email = response['user_email'], message = response['message'])
