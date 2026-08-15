'''
    Pydantic schemas for warehouse entries (Nota de Ingreso).

    Each entry has a document header plus one or more detail lines; every
    detail line becomes a PEPS/FIFO cost layer once the entry is registered.
'''
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from schemas.enums import EntryTypeEnum


class _Base(BaseModel):
    '''
        Shared base config so SQLAlchemy objects can be serialized.
    '''
    model_config = ConfigDict(from_attributes = True)


# --------------------------------------------------------------------------- #
# Create                                                                      #
# --------------------------------------------------------------------------- #
class EntryDetailCreateSchema(BaseModel):
    '''
        Single line of a new Nota de Ingreso (a cost layer to be created).
    '''
    item_id: int = Field(..., gt = 0)
    quantity: Decimal = Field(..., gt = 0)
    unit_cost: Decimal = Field(..., ge = 0)


class EntryCreateSchema(BaseModel):
    '''
        Payload to register a warehouse entry (Nota de Ingreso).
    '''
    entry_type: EntryTypeEnum = EntryTypeEnum.COMPRA
    # Preferred way to name the vendor: the registered supplier. The free-text
    # field stays for reingreso notes, which have no vendor behind them.
    supplier_id: Optional[int] = Field(None, gt = 0)
    supplier: Optional[str] = Field(None, max_length = 200)
    requirement_no: Optional[str] = Field(None, max_length = 100)
    requirement_date: Optional[date] = None
    delivery_note: Optional[str] = Field(None, max_length = 100)
    delivery_note_date: Optional[date] = None
    invoice_no: Optional[str] = Field(None, max_length = 100)
    authorization: Optional[str] = Field(None, max_length = 100)
    invoice_date: Optional[date] = None
    observations: Optional[str] = Field(None, max_length = 1000)
    discount: Decimal = Field(Decimal('0'), ge = 0)
    details: List[EntryDetailCreateSchema] = Field(..., min_length = 1)


# --------------------------------------------------------------------------- #
# Response shapes                                                             #
# --------------------------------------------------------------------------- #
class EntryFilterSchema(BaseModel):
    '''
        Filters and paging accepted by the Nota de Ingreso listing, grouped so
        the controller keeps a readable signature.
    '''
    entry_type: Optional[EntryTypeEnum] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    skip: int = Field(0, ge = 0)
    limit: int = Field(100, ge = 1, le = 500)


class EntryDetailResponseSchema(_Base):
    '''
        Entry line enriched with item metadata for display and print.
    '''
    id: int
    item_id: int
    item_code: str
    item_name: str
    unit: str
    qty_initial: Decimal
    qty_remaining: Decimal
    unit_cost: Decimal
    total_cost: Decimal


class EntryResponseSchema(_Base):
    '''
        Entry header (without details) for list views.
    '''
    id: int
    code: str
    entry_type: EntryTypeEnum
    supplier_id: Optional[int]
    supplier: Optional[str]
    requirement_no: Optional[str]
    requirement_date: Optional[date]
    delivery_note: Optional[str]
    delivery_note_date: Optional[date]
    invoice_no: Optional[str]
    authorization: Optional[str]
    invoice_date: Optional[date]
    observations: Optional[str]
    discount: Decimal
    subtotal: Decimal
    total: Decimal
    created_by: str
    created_at: datetime


class EntryDetailedResponseSchema(EntryResponseSchema):
    '''
        Entry with its detail lines, for the /entries/{id} and print views.
    '''
    details: List[EntryDetailResponseSchema]
