'''
    Users: routes handler
'''
from fastapi import APIRouter, Depends, status
from controllers.users import (
    read_users,
    get_current_admin_user,
    get_current_active_user,
    get_current_manager_user,
    read_company_users,
    change_password,
    read_user_by_email,
    update_user,
    delete_user
)
from schemas.auth import SignupResponse
from schemas.users import UserUpdateRequest, UserResponse, PasswordChangeRequest
from services.logger_config import custom_logger as logger
from services.exceptions import RegisterNotFoundError

router = APIRouter(prefix = '/v1/users', tags = ['Users'])

@router.get(
    '/',
    response_model = list[UserResponse],
    status_code = status.HTTP_200_OK,
    dependencies = [Depends(get_current_admin_user)]
)
async def read_all_users() -> list[UserResponse]:
    '''
        Endpoint to read all users. Restricted to ADMIN.
    '''
    users = await read_users()
    logger.info('Accessed all users list.')
    return users

@router.get(
    '/me',
    response_model = UserResponse,
    status_code = status.HTTP_200_OK
)
async def read_me(
    current_user: UserResponse = Depends(get_current_active_user)
) -> UserResponse:
    '''
        The signed-in user, with their last and previous sign-in.
    '''
    message = f'{current_user.email} read their own profile.'
    logger.info(message)
    return current_user


@router.get(
    '/company',
    response_model = list[UserResponse],
    status_code = status.HTTP_200_OK
)
async def read_company(
    current_user: UserResponse = Depends(get_current_manager_user)
) -> list[UserResponse]:
    '''
        The users of the caller's account. Restricted to MANAGER and ADMIN.
    '''
    return await read_company_users(current_user)


@router.post(
    '/me/password',
    status_code = status.HTTP_204_NO_CONTENT
)
async def post_my_password(
    request: PasswordChangeRequest,
    current_user: UserResponse = Depends(get_current_active_user)
) -> None:
    '''
        Changes the caller's own password; the current one is required.
    '''
    await change_password(current_user, request)


@router.get(
    '/{email}',
    response_model = UserResponse,
    status_code = status.HTTP_200_OK,
    dependencies = [Depends(get_current_admin_user)]
)
async def read_user(email: str) -> list[UserResponse]:
    '''
        Endpoint to read a single user by email. Restricted to ADMIN.
    '''
    user = await read_user_by_email(email)
    if not user:
        error_msg = f'Attempt to read non-existent user: {email}'
        logger.warning(error_msg)
        raise RegisterNotFoundError(
            detail = 'User not found'
        )
    message = f'Accessed user details for: {email}'
    logger.info(message)
    return user


@router.patch(
    '/{email}',
    status_code = status.HTTP_200_OK,
    dependencies = [Depends(get_current_admin_user)]
)
async def patch_user(
    email: str,
    user_update_data: UserUpdateRequest
) -> UserResponse:
    '''
        Endpoint to update a user.
    '''
    updated_user = await update_user(email, user_update_data)
    if not updated_user:
        error_msg = f'Failed to update user {email} for unknown reasons.'
        logger.error(error_msg)
        raise RegisterNotFoundError(
            detail = 'User not found'
        )

    message = f'User: {email} was updated'
    logger.info(message)
    return updated_user

@router.delete(
    '/{email}',
    status_code = status.HTTP_200_OK,
    dependencies = [Depends(get_current_admin_user)],
    response_model = SignupResponse
)
async def del_user(email: str) -> SignupResponse:
    '''
    Endpoint para eliminar un usuario.
    '''
    deleted = await delete_user(email)
    if not deleted:
        error_msg = f'User "{email}" not found for deletion.'
        logger.warning(error_msg)
        raise RegisterNotFoundError(detail = 'User not found')

    message = f'User: {email} was deleted'
    logger.info(message)
    return SignupResponse(user_email = email, message = 'User was deleted successfully')
