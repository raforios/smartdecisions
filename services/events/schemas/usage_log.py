'''
    Usage Log Schemas (Request/Response)
'''
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field

class UsageLogCreateSchema(BaseModel):# pylint: disable=too-few-public-methods
    '''
        Pydantic schema for creating a new usage log record.
    '''
    user_id: str = Field(..., max_length = 50)
    microservice: str = Field(..., max_length = 50)
    endpoint: str
    method: str = Field(..., max_length = 10)
    status_code: int = Field(..., ge = 100, lt = 600)
    ip_address: str = Field(..., max_length = 50)
    request_body: Optional[Any] = None
    response_body: Optional[Any] = None
    response_time_ms: Optional[int] = Field(None, ge = 0)

    class Config:# pylint: disable=too-few-public-methods
        '''
            UsageLogCreateSchema - Config Class - To get form attributes
        '''
        from_attributes = True

class UsageLogResponseSchema(UsageLogCreateSchema):# pylint: disable=too-few-public-methods
    '''
        Pydantic schema for the usage log response.
    '''
    id: int
    timestamp: datetime

    class Config:# pylint: disable=too-few-public-methods
        '''
            UsageLogResponseSchema - Config Class - To get form attributes
        '''
        from_attributes = True
