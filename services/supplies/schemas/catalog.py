'''
    Pydantic schemas for the catalog (categories, units, items, parameters).
'''
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


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
    name: str = Field(..., min_length = 2, max_length = 200)
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
    name: Optional[str] = Field(None, min_length = 2, max_length = 200)
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
    default_replenishment_qty: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------- #
# System parameter                                                            #
# --------------------------------------------------------------------------- #
class SystemParameterUpsertSchema(BaseModel):
    '''
        Payload to create or update a system parameter.
    '''
    key: str = Field(..., min_length = 2, max_length = 100)
    value: str = Field(..., min_length = 1, max_length = 500)
    description: Optional[str] = Field(None, max_length = 500)


class SystemParameterResponseSchema(SuppliesBaseSchema):
    '''
        System parameter as returned by the API.
    '''
    id: int
    key: str
    value: str
    description: Optional[str]
    updated_by: Optional[str]
    updated_at: datetime
