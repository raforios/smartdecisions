'''
    Usage Log Schemas (Request/Response)
'''
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field

class UsageLogCreateSchema(BaseModel):
    '''
        Pydantic schema for creating a new usage log record.
    '''
    user_app: str = Field(..., max_length = 50)
    user_id: Optional[str] = Field(None, max_length = 50,
                description = 'End user inside the client application.')
    microservice: str = Field(..., max_length = 50)
    endpoint: str
    method: str = Field(..., max_length = 10)
    status_code: int = Field(..., ge = 100, lt = 600)
    ip_address: str = Field(..., max_length = 50)
    request_body: Optional[Any] = None
    response_body: Optional[Any] = None
    response_time_ms: Optional[int] = Field(None, ge = 0)
    model_config = ConfigDict(extra='ignore')

class UsageLogResponseSchema(UsageLogCreateSchema):
    '''
        Pydantic schema for the usage log response.
    '''
    id: str
    timestamp: str


class UsageLogQuerySchema(BaseModel):
    '''
        Pydantic schema for filtering usage logs.
    '''
    user_app: Optional[str] = Field(None, max_length = 50)
    microservice: Optional[str] = Field(None, max_length = 50)
    endpoint: Optional[str] = None
    method: Optional[str] = Field(None, max_length = 10)
    status_code: Optional[int] = Field(None, ge = 100, lt = 600)
    start_date: Optional[str] = Field(None,
                description = 'Start date for filtering (ISO 8601 format).')
    end_date: Optional[str] = Field(None,
                description = 'End date for filtering (ISO 8601 format).')
    limit: int = Field(100, ge=1, le=100)
    last_evaluated_key: Optional[str] = Field(None,
                description = 'The last evaluated key for pagination.')
