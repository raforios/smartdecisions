'''
    Shared Pydantic base schemas for the Mining Summit service.
'''
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class OptionalContactSchema(BaseModel):
    '''
        Optional contact fields shared by participant and attendance creation
        payloads. Centralized to keep a single source of truth for contact
        validation constraints.
    '''
    email: Optional[EmailStr] = Field(None, max_length = 120)
    phone: Optional[str] = Field(None, max_length = 30)
    department: Optional[str] = Field(None, max_length = 60)
    company: Optional[str] = Field(None, max_length = 120)

    model_config = ConfigDict(extra = 'ignore')
