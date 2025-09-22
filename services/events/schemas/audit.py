'''
    Audit Schemas (Request/Response)
'''
from typing import Optional, Any, Union
from pydantic import BaseModel, ConfigDict, Field

class AuditRecordCreateSchema(BaseModel):
    '''
        Pydantic schema for creating a new audit record.
    '''
    microservice: str = Field(..., max_length = 50)
    entity_name: str = Field(..., max_length = 50)
    entity_id: Union[int, str] = Field(...,
                description = 'ID of the entity, stored as a string.')
    action: str = Field(..., max_length = 15)
    user_id: Union[int, str] = Field(..., max_length = 50)
    old_values: Optional[Any] = Field(None,
                description = 'The objects state before the change.')
    new_values: Any = Field(...,
                description = 'The objects new state after the change.')
    model_config = ConfigDict(extra='ignore')

class AuditRecordResponseSchema(AuditRecordCreateSchema):
    '''
        ydantic schema for the audit record response.
    '''
    id: str
    timestamp: str


class AuditRecordQuerySchema(BaseModel):
    '''
        Pydantic schema for filtering audit records.
    '''
    microservice: Optional[str] = Field(None, max_length = 50)
    entity_name: Optional[str] = Field(None, max_length = 50)
    entity_id: Optional[str] = Field(None,
                description = 'ID of the entity to filter by.')
    action: Optional[str] = Field(None, max_length = 15)
    user_id: Optional[str] = Field(None, max_length = 50)
    start_date: Optional[str] = Field(None,
                description = 'Start date for filtering (ISO 8601 format).')
    end_date: Optional[str] = Field(None,
                description = 'End date for filtering (ISO 8601 format).')
    limit: int = Field(100, ge = 1, le = 100)
    last_evaluated_key: Optional[str] = Field(None,
                description = 'The last evaluated key for pagination.')
