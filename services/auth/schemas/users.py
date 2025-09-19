'''
    User Schema (Request/Response)
'''
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from schemas.role import Role

class UserRequest(BaseModel):
    '''
        User Request Class for creation
    '''
    email: EmailStr = Field(min_length = 5, max_length = 100,
                    description = 'User email address.')
    first_name: str = Field(min_length = 3, max_length = 30,
                    description = 'User\'s first name.')
    last_name: str = Field(min_length = 3, max_length = 30,
                    description = 'User\'s last name.')
    password: str = Field(min_length = 8, max_length = 100,
                    description = 'User\'s password.')

class UserUpdateRequest(BaseModel):
    '''
        User Update Request Class
    '''
    first_name: Optional[str] = Field(None, min_length = 3, max_length = 30,
                            description = 'User\'s updated first name.')
    last_name: Optional[str] = Field(None, min_length = 3, max_length = 30,
                            description = 'User\'s updated last name.')
    password: Optional[str] = Field(None, min_length = 8, max_length = 100,
                            description = 'User\'s updated password.')
    client: Optional[str] = Field(None, min_length = 3, max_length = 50,
                            description = 'Client associated with the user.')
    status: Optional[bool] = Field(None,
                            description = 'User\'s active status (True/False).')

class UserResponse(BaseModel):
    '''
        User Response Class - Reflects the structure of the DynamoDB item
    '''
    email: EmailStr = Field(..., description = 'User email address.')
    first_name: str = Field(..., description = 'User\'s first name.')
    last_name: str = Field(..., description = 'User\'s last name.')
    client: Optional[str] = Field(None, description = 'Client associated with the user.')
    role: Role = Field(..., description = 'User\'s assigned role.')
    status: bool = Field(..., description = 'User\'s active status.')
    date_register: datetime = Field(...,
                            description = 'Date and time of user registration.')
    date_update: datetime = Field(...,
                            description = 'Date and time of last user update.')

    class Config: # pylint: disable=too-few-public-methods
        '''
            User Response - Config Class - To get form attributes
        '''
        from_attributes = True

class InternalUser(UserResponse): # pylint: disable=too-few-public-methods
    '''
        Internal User Schema with hashed password
    '''
    hashed_password: str
