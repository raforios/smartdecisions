'''
    Pydantic schemas for replenishments and receptions.
'''
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from schemas.enums import ReplenishmentStatusEnum


class _Base(BaseModel):
    '''
        Shared base config so SQLAlchemy objects can be serialized.
    '''
    model_config = ConfigDict(from_attributes = True)


# --------------------------------------------------------------------------- #
# Pending suggestion                                                          #
# --------------------------------------------------------------------------- #
class ReplenishmentSuggestionSchema(_Base):
    '''
        One suggested item to be replenished, derived from current stock
        against the configured minimum.
    '''
    item_id: int
    item_code: str
    item_name: str
    current_stock: Decimal
    min_stock: Decimal
    suggested_qty: Decimal


# --------------------------------------------------------------------------- #
# Create / Read                                                               #
# --------------------------------------------------------------------------- #
class ReplenishmentCreateSchema(BaseModel):
    '''
        Payload to create a replenishment order. If requested_qty is omitted
        the service will fall back to the item's default_replenishment_qty.
    '''
    item_id: int = Field(..., gt = 0)
    requested_qty: Optional[Decimal] = Field(None, gt = 0)
    supplier_hint: Optional[str] = Field(None, max_length = 200)
    notes: Optional[str] = Field(None, max_length = 1000)


class ReplenishmentBulkCreateSchema(BaseModel):
    '''
        Convenience payload to create several replenishments at once,
        typically right after consuming /replenishments/pending.
    '''
    items: List[ReplenishmentCreateSchema]


class ReplenishmentResponseSchema(_Base):
    '''
        Replenishment header as returned by the API.
    '''
    id: int
    code: str
    item_id: int
    requested_qty: Decimal
    received_qty: Decimal
    status: ReplenishmentStatusEnum
    supplier_hint: Optional[str]
    notes: Optional[str]
    created_by: str
    created_at: datetime
    completed_at: Optional[datetime]


# --------------------------------------------------------------------------- #
# Reception                                                                   #
# --------------------------------------------------------------------------- #
class ReceptionCreateSchema(BaseModel):
    '''
        Payload to register a physical reception of a replenishment.
    '''
    received_qty: Decimal = Field(..., gt = 0)
    supplier_name: str = Field(..., min_length = 2, max_length = 200)
    batch_code: Optional[str] = Field(None, max_length = 100)
    expiration_date: Optional[date] = None
    invoice_number: Optional[str] = Field(None, max_length = 100)
    file_key: Optional[str] = Field(None, max_length = 500,
                                    description = 'S3 key for the supporting document, '
                                                  'returned by the FILES service.')
    notes: Optional[str] = Field(None, max_length = 1000)


class ReceptionResponseSchema(_Base):
    '''
        Reception as returned by the API.
    '''
    id: int
    replenishment_id: int
    received_qty: Decimal
    supplier_name: str
    batch_code: Optional[str]
    expiration_date: Optional[date]
    invoice_number: Optional[str]
    file_key: Optional[str]
    notes: Optional[str]
    received_by: str
    received_at: datetime
