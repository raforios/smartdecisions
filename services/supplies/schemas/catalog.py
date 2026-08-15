'''
    Pydantic schemas for the catalog (categories, units, items).
'''
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field


class SuppliesBaseSchema(BaseModel):
    '''
        Shared base config so SQLAlchemy objects can be serialized.
    '''
    model_config = ConfigDict(from_attributes = True)


# --------------------------------------------------------------------------- #
# Category                                                                    #
# --------------------------------------------------------------------------- #
class CategoryCreateSchema(BaseModel):
    '''
        Payload to create a category.
    '''
    code: str = Field(..., min_length = 2, max_length = 50)
    name: str = Field(..., min_length = 2, max_length = 150)
    description: Optional[str] = Field(None, max_length = 500)
    is_active: bool = True


class CategoryUpdateSchema(BaseModel):
    '''
        Payload to partially update a category.
    '''
    name: Optional[str] = Field(None, min_length = 2, max_length = 150)
    description: Optional[str] = Field(None, max_length = 500)
    is_active: Optional[bool] = None


class CategoryResponseSchema(SuppliesBaseSchema):
    '''
        Category as returned by the API.
    '''
    id: int
    code: str
    name: str
    description: Optional[str]
    is_active: bool
    created_at: datetime


# --------------------------------------------------------------------------- #
# Unit                                                                        #
# --------------------------------------------------------------------------- #
class UnitCreateSchema(BaseModel):
    '''
        Payload to create a unit of measure.
    '''
    code: str = Field(..., min_length = 1, max_length = 20)
    name: str = Field(..., min_length = 1, max_length = 100)
    abbreviation: str = Field(..., min_length = 1, max_length = 10)
    is_active: bool = True


class UnitUpdateSchema(BaseModel):
    '''
        Payload to partially update a unit of measure.
    '''
    name: Optional[str] = Field(None, min_length = 1, max_length = 100)
    abbreviation: Optional[str] = Field(None, min_length = 1, max_length = 10)
    is_active: Optional[bool] = None


class UnitResponseSchema(SuppliesBaseSchema):
    '''
        Unit of measure as returned by the API.
    '''
    id: int
    code: str
    name: str
    abbreviation: str
    is_active: bool
    created_at: datetime


# --------------------------------------------------------------------------- #
# Item                                                                        #
# --------------------------------------------------------------------------- #
class ItemCreateSchema(BaseModel):
    '''
        Payload to create an item.
    '''
    code: str = Field(..., min_length = 2, max_length = 50)
    name: str = Field(..., min_length = 2, max_length = 500)
    description: Optional[str] = Field(None, max_length = 500)
    category_id: int = Field(..., gt = 0)
    unit_id: int = Field(..., gt = 0)
    min_stock: Decimal = Field(..., ge = 0)
    default_replenishment_qty: Decimal = Field(..., ge = 0)
    is_active: bool = True


class ItemUpdateSchema(BaseModel):
    '''
        Payload to partially update an item. Stock is intentionally excluded;
        balances change through kardex movements only.
    '''
    name: Optional[str] = Field(None, min_length = 2, max_length = 500)
    description: Optional[str] = Field(None, max_length = 500)
    category_id: Optional[int] = Field(None, gt = 0)
    unit_id: Optional[int] = Field(None, gt = 0)
    is_active: Optional[bool] = None


class ItemParametersUpdateSchema(BaseModel):
    '''
        Payload reserved for updating the replenishment parameters of an
        item. Separated from the main update to keep audit clear.
    '''
    min_stock: Optional[Decimal] = Field(None, ge = 0)
    default_replenishment_qty: Optional[Decimal] = Field(None, ge = 0)


class ItemFilterSchema(BaseModel):
    '''
        Filters accepted by the item listing. Grouped into a model because the
        catalog screen combines free text, accounting group, availability and
        paging, and passing them one by one would bloat the call signature.
    '''
    skip: int = Field(0, ge = 0)
    limit: int = Field(100, ge = 1, le = 500)
    search: Optional[str] = Field(None, description = 'Free text on code or name.')
    category_id: Optional[int] = Field(None, ge = 1,
                                       description = 'Restrict to one accounting group.')
    only_available: bool = Field(False, description = 'Exclude items at or below the minimum.')


class ItemResponseSchema(SuppliesBaseSchema):
    '''
        Item as returned by the API.
    '''
    id: int
    code: str
    name: str
    description: Optional[str]
    category_id: int
    unit_id: int
    min_stock: Decimal
    current_stock: Decimal
    reserved_stock: Decimal
    default_replenishment_qty: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def available_stock(self) -> Decimal:
        '''
            Units a new request may still ask for: physical stock minus what
            open requests reserved minus the minimum the warehouse keeps.
            Exposed here so every consumer reads the same number instead of
            recomputing the rule in the UI.
        '''
        free = self.current_stock - self.reserved_stock - self.min_stock
        return free if free > 0 else Decimal('0')
