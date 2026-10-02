'''
    Pydantic V2 DTOs for the seller master.

    A seller arrives in the files the way the owner's ERP writes it —a name or a
    code—, and signs in to the product with an email. The master is where the
    two meet, once, instead of every module guessing that "Ana" is
    ana@empresa.com.
'''
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from schemas.clients import ClientSource


class SellerError(str, Enum):
    '''
        Why a seller request could not be served.
    '''
    SELLER_NOT_FOUND = 'SELLER_NOT_FOUND'


class SellerResponseSchema(BaseModel):
    '''
        One seller of the master.

        `user_email` is empty until a manager links the seller to the account
        they sign in with; until then plans can be made for them but their
        phone cannot see them.
    '''
    id: str = Field(..., description = 'As the owner\'s files write it.')
    name: str
    user_email: Optional[str] = None
    source: ClientSource = Field(..., description = 'The door it first came through.')
    created_at: str
    updated_at: str


class SellerListResponseSchema(BaseModel):
    '''
        The owner's sellers and how many are already linked to a user.
    '''
    sellers: List[SellerResponseSchema]
    total: int = Field(..., ge = 0)
    linked: int = Field(..., ge = 0, description = 'Sellers with a user to sign in with.')


class SellerUpdateSchema(BaseModel):
    '''
        The explicit act a load is not: a manager states who a seller is.

        Fields left out are untouched; `user_email` set to null unlinks.
    '''
    name: Optional[str] = Field(None, min_length = 1, max_length = 128)
    # A plain pattern and not EmailStr: that needs email-validator, which this
    # service does not carry, and AUTH already validated the address it issued.
    user_email: Optional[str] = Field(
        None, max_length = 100, pattern = r'^[^@\s]+@[^@\s]+\.[^@\s]+$'
    )


# Who may link a seller to a user: it decides whose phone sees which route, so
# it is a management act. The consultation role reads, it does not assign.
LINKING_ROLES: tuple[str, ...] = ('ADMIN', 'MANAGER')
