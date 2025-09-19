'''
    User and Auth Controller
'''
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from services.dynamodb import (
    create_user_item,
    get_user_by_email,
    update_user_item,
    delete_user_item,
    scan_all_users
)
from services.security import hash_password, verify_password
from services.jwt_token import decode_access_token
from services.logger_config import custom_logger as logger
from services.exceptions import (
    UnauthorizedError,
    InvalidInputError,
    RegisterAlreadyExistsError
)
from schemas.users import (
    UserRequest,
    UserUpdateRequest,
    UserResponse,
    InternalUser
)
from schemas.role import Role

async def get_user_payload(
    token: HTTPAuthorizationCredentials = Depends(HTTPBearer())
) -> Dict[str, Any]:
    '''
        Function to extract and decode the JWT token payload.
    '''
    if not token:
        logger.warning('No token provided for protected route.')
        raise UnauthorizedError(detail = 'Authentication token missing.')

    payload = decode_access_token(token.credentials)
    if not payload:
        logger.warning('Invalid or expired token detected.')
        raise UnauthorizedError(
            detail = 'Invalid or expired token.'
        )

    return payload

async def get_current_user(
    payload: Dict[str, Any] = Depends(get_user_payload)
) -> UserResponse:
    '''
        Function to get the full User object from the JWT token.
    '''
    email: str = payload.get('email')
    if not email:
        logger.error('JWT payload missing "email" subject.')
        raise UnauthorizedError(
            detail = 'Could not validate credentials: Token sub (email) missing.'
        )

    user_item = get_user_by_email(email)
    if user_item is None:
        error_msg = f'Authenticated user {email} not found in DB.'
        logger.error(error_msg)
        raise UnauthorizedError(
            detail = error_msg
        )

    return UserResponse(**user_item)

async def get_current_active_user(
    current_user: UserResponse = Depends(get_current_user)
) -> UserResponse:
    '''
        Function to check if the authenticated user is active.
    '''
    if not current_user.status:
        message = f'Inactive user {current_user.email} attempted access.'
        logger.warning(message)
        raise InvalidInputError(
            detail = 'Inactive user'
        )

    return current_user

async def authenticate_user(
    email: str, password: str
) -> Optional[InternalUser]:
    '''
        Function to authenticate a user by verifying their credentials against DynamoDB.
    '''
    user_item = get_user_by_email(email)
    if not user_item or not verify_password(password, user_item['hashed_password']):
        message = f'Authentication failed for user {email}.'
        logger.warning(message)
        return None

    return InternalUser(**user_item)

async def create_user(
    user_data: UserRequest
) -> Dict[str, Any]:
    '''
        Create User
    '''
    existing_user = get_user_by_email(user_data.email)
    if existing_user:
        message = f'Registration failed: User with email {user_data.email} already exists.'
        logger.warning(message)
        raise RegisterAlreadyExistsError(detail = 'Email already registered')

    hashed_pw = hash_password(user_data.password)
    current_time = datetime.now(timezone.utc)
    new_user_item = {
        'email': user_data.email,
        'first_name': user_data.first_name,
        'last_name': user_data.last_name,
        'hashed_password': hashed_pw,
        'role': Role.USER.value,
        'status': True,
        'date_register': current_time.isoformat(),
        'date_update': current_time.isoformat()
    }
    created_item = create_user_item(new_user_item)
    message = f'User {created_item['email']} registered successfully in DynamoDB.'
    logger.info(message)
    return {'user_email': created_item['email'], 'message': 'User created successfully'}

async def read_users() -> List[UserResponse]:
    '''
        Read all users from database.
    '''
    user_items = scan_all_users()
    return [UserResponse(**item) for item in user_items]

async def read_user_by_email(
    email: str
) -> Optional[UserResponse]:
    '''
        Read user by email.
    '''
    user_item = get_user_by_email(email)
    if user_item:
        return UserResponse(**user_item)
    return None

def build_user_update_params(
    user_update_data: UserUpdateRequest
) -> tuple[str, dict, dict]:
    '''
        Helper function that builds DynamoDB update expressions and attribute values
        from a UserUpdateRequest object.
    '''
    update_expression_parts = []
    expression_attribute_values = {}
    expression_attribute_names = {}

    update_fields_map = {
        'first_name': 'first_name',
        'last_name': 'last_name',
        'client': 'client'
    }

    data_to_update = user_update_data.model_dump(exclude_unset = True)

    for field, value in data_to_update.items():
        if field == 'password':
            hashed_pw = hash_password(value)
            update_expression_parts.append('hashed_password = :hashed_password')
            expression_attribute_values[':hashed_password'] = hashed_pw
        elif field == 'status':
            update_expression_parts.append('#status_alias = :status')
            expression_attribute_values[':status'] = value
            expression_attribute_names['#status_alias'] = 'status'
        elif field in update_fields_map:
            db_field = update_fields_map[field]
            update_expression_parts.append(f'{db_field} = :{field}')
            expression_attribute_values[f':{field}'] = value

    if not update_expression_parts:
        return None, None, None

    update_expression_parts.append('date_update = :date_update')
    expression_attribute_values[':date_update'] = datetime.now(timezone.utc).isoformat()

    final_update_expression = 'SET ' + ', '.join(update_expression_parts)
    return final_update_expression, expression_attribute_values, \
           (expression_attribute_names if expression_attribute_names else None)

async def update_user(
    email: str,
    user_update_data: UserUpdateRequest
) -> Optional[UserResponse]:
    '''
        Update user.
    '''
    current_user_item = get_user_by_email(email)
    if not current_user_item:
        message = f'Update failed: User {email} not found.'
        logger.warning(message)
        return None

    final_update_expression, expression_attribute_values, expression_attribute_names = \
        build_user_update_params(user_update_data)

    if not final_update_expression:
        message = f'No update data provided for user {email}.'
        logger.info(message)
        return UserResponse(**current_user_item)

    updated_item = update_user_item(
        email,
        final_update_expression,
        expression_attribute_values,
        expression_attribute_names
    )

    if updated_item:
        return UserResponse(**updated_item)
    return None

async def delete_user(
    email: str
) -> bool:
    '''
        Delete user
    '''
    return delete_user_item(email)
