'''
    Health of the service's tables (ADMIN only).
'''
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class TableState(str, Enum):
    '''
        The state of one table: DynamoDB's own, or why it could not be read.
    '''
    ACTIVE = 'ACTIVE'
    CREATING = 'CREATING'
    UPDATING = 'UPDATING'
    DELETING = 'DELETING'
    ARCHIVING = 'ARCHIVING'
    ARCHIVED = 'ARCHIVED'
    INACCESSIBLE_ENCRYPTION_CREDENTIALS = 'INACCESSIBLE_ENCRYPTION_CREDENTIALS'
    MISSING = 'MISSING'
    UNREACHABLE = 'UNREACHABLE'


class TableHealth(BaseModel):
    '''
        One table the service uses, as DynamoDB describes it. The counts are
        DynamoDB's own, refreshed about every six hours.
    '''
    name: str = Field(..., description = 'Table name.')
    status: TableState = Field(..., description = 'Table state.')
    item_count: int | None = Field(None, description = 'Approximate number of items.')
    size_bytes: int | None = Field(None, description = 'Approximate size in bytes.')


class TablesHealthResponse(BaseModel):
    '''
        Every table the service uses and whether all of them are active.
    '''
    service: str = Field(..., description = 'Service code.')
    healthy: bool = Field(..., description = 'True when every table is ACTIVE.')
    checked_at: datetime = Field(..., description = 'When the tables were read.')
    tables: list[TableHealth] = Field(..., description = 'One entry per table.')
