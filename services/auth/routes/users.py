'''
    Users: routes handler
'''
from typing import List
from fastapi import APIRouter, Depends, status
from controllers.users import (
    read_users,
    get_current_active_user,
    read_user_by_email,
    update_user,
    delete_user
)
from schemas.auth import SignupResponse
from schemas.users import UserUpdateRequest, UserResponse
from services.logger_config import custom_logger as logger
from services.exceptions import RegisterNotFoundError

router = APIRouter(prefix = '/v1/users', tags = ['Users'])

@router.get(
    '/',
    response_model = List[UserResponse],
    status_code = status.HTTP_200_OK,
    dependencies = [Depends(get_current_active_user)]
)
async def read_all_users():
    '''
        Endpoint to read all users (requires active user authentication).
    '''
    users = await read_users()
    logger.info('Accessed all users list.')
    return users

@router.get(
    '/{email}',
    response_model = UserResponse,
    status_code = status.HTTP_200_OK,
    dependencies = [Depends(get_current_active_user)]
)
async def read_user(
    email: str
):
    '''
        Endpoint to read a user's email (requires active user authentication).
    '''
    user = await read_user_by_email(email)
    if not user:
        message = f'Attempt to read non-existent user: {email}'
        logger.warning(message)
        raise RegisterNotFoundError(
            detail = 'User not found'
        )
    message = f'Accessed user details for: {email}'
    logger.info(message)
    return user


@router.patch(
    '/{email}',
    status_code = status.HTTP_200_OK,
    dependencies = [Depends(get_current_active_user)]
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
    dependencies = [Depends(get_current_active_user)],
    response_model = SignupResponse
)
async def del_user(
    email: str
) -> SignupResponse:
    '''
    Endpoint para eliminar un usuario.
    '''
    deleted = await delete_user(email)
    if not deleted:
        message = f'User "{email}" not found for deletion.'
        logger.warning(message)
        raise RegisterNotFoundError(detail = 'User not found')

    message = f'User: {email} was deleted'
    logger.info(message)
    return SignupResponse(user_email = email, message = 'User was deleted successfully')
