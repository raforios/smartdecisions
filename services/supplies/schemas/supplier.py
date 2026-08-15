'''
    Pydantic schemas for suppliers (proveedores).

    Every field except the email address is mandatory: a Nota de Ingreso is an
    accounting document and the warehouse must be able to reach the vendor
    that issued it.
'''
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SupplierBaseSchema(BaseModel):
    '''
        Shared base config so SQLAlchemy objects can be serialized.
    '''
    model_config = ConfigDict(from_attributes = True)


class SupplierCreateSchema(BaseModel):
    '''
        Payload to register a supplier.
    '''
    name: str = Field(..., min_length = 2, max_length = 200)
    nit: str = Field(..., min_length = 4, max_length = 50)
    contact_person: str = Field(..., min_length = 3, max_length = 200)
    address: str = Field(..., min_length = 3, max_length = 300)
    phone: str = Field(..., min_length = 6, max_length = 50)
    email: Optional[str] = Field(None, max_length = 150)
    is_active: bool = True


class SupplierUpdateSchema(BaseModel):
    '''
        Payload to partially update a supplier. The NIT is updatable because
        vendors do correct a mistyped one, but it stays unique.
    '''
    name: Optional[str] = Field(None, min_length = 2, max_length = 200)
    nit: Optional[str] = Field(None, min_length = 4, max_length = 50)
    contact_person: Optional[str] = Field(None, min_length = 3, max_length = 200)
    address: Optional[str] = Field(None, min_length = 3, max_length = 300)
    phone: Optional[str] = Field(None, min_length = 6, max_length = 50)
    email: Optional[str] = Field(None, max_length = 150)
    is_active: Optional[bool] = None


class SupplierFilterSchema(BaseModel):
    '''
        Filters accepted by the supplier listing.
    '''
    skip: int = Field(0, ge = 0)
    limit: int = Field(200, ge = 1, le = 500)
    search: Optional[str] = Field(None, description = 'Free text on name, NIT or contact.')
    only_active: bool = Field(False, description = 'Exclude deactivated suppliers.')


class SupplierResponseSchema(SupplierBaseSchema):
    '''
        Supplier as returned by the API.
    '''
    id: int
    name: str
    nit: str
    contact_person: str
    address: str
    email: Optional[str]
    phone: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
