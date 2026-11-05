'''
    Users controller: who is calling, what they may do, and the hand-off to
    `services/users.py`, where the rules live.
'''
from typing import Any

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from schemas.auth import AuthError, SignupResponse
from schemas.role import Role
from schemas.users import (
    InternalUser,
    PasswordChangeRequest,
    UserRequest,
    UserResponse,
    UserUpdateRequest
)
from services import users
from services.dynamodb import get_user_by_email
from services.exceptions import ForbiddenError, UnauthorizedError
from services.jwt_token import decode_access_token
from services.logger_config import custom_logger as logger


async def get_user_payload(
    token: HTTPAuthorizationCredentials = Depends(HTTPBearer())
) -> dict[str, Any]:
    '''
        The claims of the caller's token.

        Args:
            token (HTTPAuthorizationCredentials): The bearer token.

        Returns:
            dict[str, Any]: The claims.

        Raises:
            UnauthorizedError: TOKEN_MISSING or TOKEN_INVALID.
    '''
    if not token:
        logger.warning('No token provided for a protected route.')
        raise UnauthorizedError(detail = AuthError.TOKEN_MISSING.value)
    payload = decode_access_token(token.credentials)
    if not payload:
        logger.warning('Invalid or expired token.')
        raise UnauthorizedError(detail = AuthError.TOKEN_INVALID.value)
    return payload


async def get_current_user(
    payload: dict[str, Any] = Depends(get_user_payload)
) -> UserResponse:
    '''
        The caller, read from the users table.

        Args:
            payload (dict[str, Any]): The claims of the caller's token.

        Returns:
            UserResponse: The caller.

        Raises:
            UnauthorizedError: TOKEN_INVALID, also for a user that no longer
                exists: the caller learns only that the token is no good.
    '''
    email = payload.get('email')
    stored = get_user_by_email(email) if email else None
    if stored is None:
        error_msg = f'Token without a known user: {email}.'
        logger.error(error_msg)
        raise UnauthorizedError(detail = AuthError.TOKEN_INVALID.value)
    return UserResponse(**stored)


async def get_current_active_user(
    current_user: UserResponse = Depends(get_current_user)
) -> UserResponse:
    '''
        The caller, when their account is active.

        Args:
            current_user (UserResponse): The caller.

        Returns:
            UserResponse: The caller.

        Raises:
            ForbiddenError: USER_INACTIVE.
    '''
    if not current_user.status:
        error_msg = f'Inactive user {current_user.email} attempted access.'
        logger.warning(error_msg)
        raise ForbiddenError(detail = AuthError.USER_INACTIVE.value)
    return current_user


async def get_current_admin_user(
    current_user: UserResponse = Depends(get_current_active_user)
) -> UserResponse:
    '''
        The caller, when they are an ADMIN. Guards the user management, so a
        non-admin cannot promote itself.

        Args:
            current_user (UserResponse): The active caller.

        Returns:
            UserResponse: The caller.

        Raises:
            ForbiddenError: ADMIN_REQUIRED.
    '''
    if current_user.role != Role.ADMIN:
        error_msg = (f'Forbidden: {current_user.email} ({current_user.role}) attempted a '
                     'user-management operation.')
        logger.warning(error_msg)
        raise ForbiddenError(detail = AuthError.ADMIN_REQUIRED.value)
    return current_user


async def get_current_manager_user(
    current_user: UserResponse = Depends(get_current_active_user)
) -> UserResponse:
    '''
        The caller, when they run an account (MANAGER) or the platform
        (ADMIN): the people who may see who else uses it.

        Args:
            current_user (UserResponse): The active caller.

        Returns:
            UserResponse: The caller.

        Raises:
            ForbiddenError: MANAGER_REQUIRED.
    '''
    if current_user.role not in (Role.MANAGER, Role.ADMIN):
        error_msg = (f'Forbidden: {current_user.email} ({current_user.role}) '
                     'asked for the account users.')
        logger.warning(error_msg)
        raise ForbiddenError(detail = AuthError.MANAGER_REQUIRED.value)
    return current_user


async def authenticate_user(
    email: str,
    password: str
) -> InternalUser | None:
    '''
        The user whose credentials these are, or None.

        Args:
            email (str): The e-mail given.
            password (str): The password given.

        Returns:
            InternalUser | None: The user.
    '''
    return users.authenticate_user(email, password)


async def create_user(user_data: UserRequest) -> SignupResponse:
    '''
        Registers a user.

        Args:
            user_data (UserRequest): The new user.

        Returns:
            SignupResponse: The e-mail and USER_CREATED.
    '''
    return users.create_user(user_data)


async def read_users() -> list[UserResponse]:
    '''
        Every user of the platform.

        Returns:
            list[UserResponse]: The users.
    '''
    return users.read_users()


async def read_user_by_email(email: str) -> UserResponse | None:
    '''
        One user, or None.

        Args:
            email (str): The user.

        Returns:
            UserResponse | None: The user.
    '''
    return users.read_user_by_email(email)


async def update_user(
    email: str,
    user_update_data: UserUpdateRequest
) -> UserResponse | None:
    '''
        Changes a user's profile.

        Args:
            email (str): The user.
            user_update_data (UserUpdateRequest): What changes.

        Returns:
            UserResponse | None: The user as it is now, or None.
    '''
    return users.update_user(email, user_update_data)


async def delete_user(email: str) -> bool:
    '''
        Deletes a user.

        Args:
            email (str): The user.

        Returns:
            bool: Whether there was such a user.
    '''
    return users.delete_user(email)


def record_login(user: InternalUser) -> None:
    '''
        Records a sign-in on the user.

        Args:
            user (InternalUser): Who signed in.
    '''
    users.record_login(user)


async def read_company_users(viewer: UserResponse) -> list[UserResponse]:
    '''
        The users of the viewer's account.

        Args:
            viewer (UserResponse): Who asks.

        Returns:
            list[UserResponse]: The users they may see.
    '''
    return users.read_company_users(viewer)


async def change_password(
    user: UserResponse,
    request: PasswordChangeRequest
) -> None:
    '''
        Changes a user's own password.

        Args:
            user (UserResponse): Who changes it.
            request (PasswordChangeRequest): The current and the new password.
    '''
    users.change_password(user, request)
