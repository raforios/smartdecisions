'''
    Audit Schemas (Request/Response)
'''
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

class AuditRecordCreateSchema(BaseModel):
    '''
        Pydantic schema for creating a new audit record.
    '''
    microservice: str = Field(..., max_length = 50)
    entity_name: str = Field(..., max_length = 50)
    entity_id: int | str = Field(...,
                description = 'ID of the entity, stored as a string.')
    action: str = Field(..., max_length = 15)
    user_id: int | str = Field(..., max_length = 50)
    old_values: Any | None = Field(None,
                description = 'The objects state before the change.')
    new_values: Any = Field(...,
                description = 'The objects new state after the change.')
    model_config = ConfigDict(extra = 'ignore')

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
    microservice: str | None = Field(None, max_length = 50)
    entity_name: str | None = Field(None, max_length = 50)
    entity_id: str | None = Field(None,
                description = 'ID of the entity to filter by.')
    action: str | None = Field(None, max_length = 15)
    user_id: str | None = Field(None, max_length = 50)
    start_date: str | None = Field(None,
                description = 'Start date for filtering (ISO 8601 format).')
    end_date: str | None = Field(None,
                description = 'End date for filtering (ISO 8601 format).')
    limit: int = Field(100, ge = 1, le = 100)
    last_evaluated_key: str | None = Field(None,
                description = 'The last evaluated key for pagination.')


# Who may READ the logs. They hold every user's e-mail, IP and the bodies of
# their requests, and they were open to anyone on the internet. Writing stays
# open: every service posts its audit and usage logs without a user token.
READ_ROLES: tuple[str, ...] = ('ADMIN',)
