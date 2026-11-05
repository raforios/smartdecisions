'''
    Auth Schema
'''
from enum import Enum

from pydantic import BaseModel, Field, EmailStr


class AuthError(str, Enum):
    '''
        Why an account request was refused: a code, the wording belongs to the
        portal.
    '''
    WRONG_PASSWORD = 'WRONG_PASSWORD'
    SAME_PASSWORD = 'SAME_PASSWORD'
    MANAGER_REQUIRED = 'MANAGER_REQUIRED'
    ADMIN_REQUIRED = 'ADMIN_REQUIRED'
    TOKEN_MISSING = 'TOKEN_MISSING'
    # Expired, forged, or naming a user that no longer exists: the caller
    # learns only that the token does not open the door.
    TOKEN_INVALID = 'TOKEN_INVALID'
    TOKEN_NOT_ISSUED = 'TOKEN_NOT_ISSUED'
    INVALID_CREDENTIALS = 'INVALID_CREDENTIALS'
    USER_INACTIVE = 'USER_INACTIVE'
    EMAIL_TAKEN = 'EMAIL_TAKEN'
    USER_NOT_FOUND = 'USER_NOT_FOUND'
    STORAGE_UNAVAILABLE = 'STORAGE_UNAVAILABLE'


class AuthResult(str, Enum):
    '''
        What an account request did, as a code for the portal to word.
    '''
    USER_CREATED = 'USER_CREATED'
    USER_DELETED = 'USER_DELETED'

class LoginRequest(BaseModel):
    '''
        LoginRequest Class
    '''
    email: EmailStr = Field(min_length = 5, max_length = 50,
                    description = 'User email for login.')
    password: str = Field(min_length = 8, max_length = 100,
                    description = 'User password for login.')

class SignupResponse(BaseModel):
    '''
        SignupResponse Class
    '''
    user_email: EmailStr = Field(...,
                    description = 'Email of the newly registered user.')
    message: AuthResult = Field(..., description = 'What was done, as a code.')

class Token(BaseModel):
    '''
        Token Class
    '''
    access_token: str = Field(...,
                    description = 'JWT access token for authentication.')
    token_type: str = Field(...,
                    description = 'Type of the token, typically "bearer".')
