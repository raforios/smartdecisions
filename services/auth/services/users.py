'''
    Users: sign-in, sign-up, profile changes and who belongs to an account.

    The rules live here and the controller only hands requests in (CLAUDE.md
    §3). Every refusal is a code of `AuthError`; the wording is the portal's.
'''
from dataclasses import dataclass
from typing import Any

from schemas.auth import AuthError, AuthResult, SignupResponse
from schemas.role import Role
from schemas.users import (
    InternalUser,
    PasswordChangeRequest,
    UserRequest,
    UserResponse,
    UserUpdateRequest
)
from services.companies import check_company_for_user
from services.dynamodb import (
    create_user_item,
    delete_user_item,
    get_user_by_email,
    scan_all_users,
    update_user_item
)
from services.exceptions import InvalidInputError, ServiceUnavailableError
from services.logger_config import custom_logger as logger
from services.security import hash_password, verify_password
from services.sessions import company_members, login_update
from services.utils import get_current_time_gmt

# The fields a profile change writes as they come; the password is hashed and
# the role and status are reserved words of DynamoDB, so they travel aliased.
_PLAIN_FIELDS = ('first_name', 'last_name', 'client')


@dataclass(frozen = True)
class UserUpdate:
    '''
        One profile change as DynamoDB takes it.
    '''
    expression: str
    values: dict[str, Any]
    names: dict[str, str] | None


def authenticate_user(
    email: str,
    password: str
) -> InternalUser | None:
    '''
        The user whose credentials these are, or None.

        Args:
            email (str): The e-mail given.
            password (str): The password given.

        Returns:
            InternalUser | None: The user, when e-mail and password match.
    '''
    stored = get_user_by_email(email)
    if not stored or not verify_password(password, stored['hashed_password']):
        error_msg = f'Authentication failed for {email}.'
        logger.warning(error_msg)
        return None
    return InternalUser(**stored)


def create_user(user_data: UserRequest) -> SignupResponse:
    '''
        Registers a user as REQUESTER, active and without a client: the ADMIN
        gives role and client afterwards.

        Args:
            user_data (UserRequest): The new user.

        Returns:
            SignupResponse: The e-mail and USER_CREATED.

        Raises:
            RegisterAlreadyExistsError: EMAIL_TAKEN.
    '''
    now = get_current_time_gmt().isoformat()
    created = create_user_item({
        'email': user_data.email,
        'first_name': user_data.first_name,
        'last_name': user_data.last_name,
        'hashed_password': hash_password(user_data.password),
        'role': Role.REQUESTER.value,
        'status': True,
        'date_register': now,
        'date_update': now
    })
    message = f'User {created["email"]} registered.'
    logger.info(message)
    return SignupResponse(user_email = created['email'], message = AuthResult.USER_CREATED)


def read_users() -> list[UserResponse]:
    '''
        Every user of the platform.

        Returns:
            list[UserResponse]: The users.
    '''
    return [UserResponse(**item) for item in scan_all_users()]


def read_user_by_email(email: str) -> UserResponse | None:
    '''
        One user, or None.

        Args:
            email (str): The user.

        Returns:
            UserResponse | None: The user.
    '''
    stored = get_user_by_email(email)
    return UserResponse(**stored) if stored else None


def user_update(change: UserUpdateRequest) -> UserUpdate | None:
    '''
        The DynamoDB update a profile change asks for.

        Args:
            change (UserUpdateRequest): What changes.

        Returns:
            UserUpdate | None: The update; None when nothing changes.
    '''
    parts: list[str] = []
    values: dict[str, Any] = {}
    names: dict[str, str] = {}
    for field, value in change.model_dump(exclude_unset = True).items():
        if field == 'password':
            parts.append('hashed_password = :hashed_password')
            values[':hashed_password'] = hash_password(value)
        elif field in ('status', 'role'):
            parts.append(f'#{field} = :{field}')
            values[f':{field}'] = value.value if isinstance(value, Role) else value
            names[f'#{field}'] = field
        elif field in _PLAIN_FIELDS:
            parts.append(f'{field} = :{field}')
            values[f':{field}'] = value
    if not parts:
        return None
    parts.append('date_update = :date_update')
    values[':date_update'] = get_current_time_gmt().isoformat()
    return UserUpdate(expression = 'SET ' + ', '.join(parts), values = values,
                      names = names or None)


def update_user(
    email: str,
    change: UserUpdateRequest
) -> UserResponse | None:
    '''
        Changes a user's profile.

        Args:
            email (str): The user.
            change (UserUpdateRequest): What changes.

        Returns:
            UserResponse | None: The user as it is now; None when there is no
                such user.

        Raises:
            InvalidInputError: COMPANY_NOT_FOUND or COMPANY_INACTIVE.
    '''
    stored = get_user_by_email(email)
    if not stored:
        error_msg = f'Update refused: user {email} not found.'
        logger.warning(error_msg)
        return None
    # The company is chosen from the companies table, never typed freely
    # (Rafael, 21-oct-2026): it must exist and be active.
    if change.client is not None:
        check_company_for_user(change.client)
    update = user_update(change)
    if update is None:
        return UserResponse(**stored)
    updated = update_user_item(email, update.expression, update.values, update.names)
    return UserResponse(**updated) if updated else None


def delete_user(email: str) -> bool:
    '''
        Deletes a user.

        Args:
            email (str): The user.

        Returns:
            bool: Whether there was such a user.
    '''
    return delete_user_item(email)


def record_login(user: InternalUser) -> None:
    '''
        Records a sign-in on the user: last and previous sign-in and the count.
        A failure is logged and does not stop the sign-in: the record serves
        the welcome page, the access does not depend on it.

        Args:
            user (InternalUser): Who signed in.
    '''
    stored = {'last_login': user.last_login.isoformat() if user.last_login else None}
    expression, values = login_update(stored, get_current_time_gmt())
    try:
        update_user_item(user.email, expression, values)
    except ServiceUnavailableError as error:
        error_msg = f'Could not record the sign-in of {user.email}: {error.detail}'
        logger.error(error_msg)


def read_company_users(viewer: UserResponse) -> list[UserResponse]:
    '''
        The users of the viewer's account; every user for an administrator.

        Args:
            viewer (UserResponse): Who asks.

        Returns:
            list[UserResponse]: The users they may see.
    '''
    visible = company_members(scan_all_users(), viewer.email, viewer.client,
                              viewer.role == Role.ADMIN)
    message = f'{viewer.email} listed {len(visible)} account user(s).'
    logger.info(message)
    return [UserResponse(**item) for item in visible]


def change_password(
    user: UserResponse,
    request: PasswordChangeRequest
) -> None:
    '''
        Changes a user's own password once the current one is proven.

        Args:
            user (UserResponse): Who changes it.
            request (PasswordChangeRequest): The current and the new password.

        Raises:
            InvalidInputError: WRONG_PASSWORD or SAME_PASSWORD.
    '''
    stored = get_user_by_email(user.email)
    if not stored or not verify_password(request.current_password, stored['hashed_password']):
        error_msg = f'Password change refused for {user.email}: wrong current password.'
        logger.warning(error_msg)
        # 400, not 401: the session is valid, only the proof failed.
        raise InvalidInputError(detail = AuthError.WRONG_PASSWORD.value)
    if request.new_password == request.current_password:
        error_msg = f'Password change refused for {user.email}: same password.'
        logger.warning(error_msg)
        raise InvalidInputError(detail = AuthError.SAME_PASSWORD.value)
    update_user(user.email, UserUpdateRequest(password = request.new_password))
    message = f'User {user.email} changed their password.'
    logger.info(message)
