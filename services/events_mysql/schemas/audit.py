'''
    Audit Schemas (Request/Response)
'''
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field

class AuditRecordCreateSchema(BaseModel):# pylint: disable=R0903
    '''
        Pydantic schema for creating a new audit record.
    '''
    microservice: str = Field(..., max_length = 50)
    entity_name: str = Field(..., max_length = 50)
    entity_id: int = Field(..., ge = 0)
    action: str = Field(..., max_length = 15)
    user_id: str = Field(..., max_length = 50)
    old_values: Optional[Any] = Field(None, description = 'The objects state before the change.')
    new_values: Any = Field(..., description = 'The objects new state after the change.')

    class Config:# pylint: disable=R0903
        '''
            AuditRecordCreateSchema - Config Class - To get form attributes
        '''
        from_attributes = True

class AuditRecordResponseSchema(AuditRecordCreateSchema):# pylint: disable=R0903
    '''
        Pydantic schema for the audit record response.
    '''
    id: int
    timestamp: datetime

    class Config:# pylint: disable=R0903
        '''
            AuditRecordResponseSchema - Config Class - To get form attributes
        '''
        from_attributes = True
