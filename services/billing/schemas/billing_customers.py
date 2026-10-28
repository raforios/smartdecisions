'''
    The shop's customers: who it invoiced, by NIT or CI.

    A customer is written by the invoices themselves. One that does not exist
    is created; one that exists only gets the fields it had empty, so an
    invoice can never undo a correction. Overwriting is a separate, explicit
    act.
'''
from pydantic import BaseModel, Field


class CustomerOut(BaseModel):
    '''
        One customer of the shop.
    '''
    document: str = Field(..., description = 'NIT or CI, as the buyer gives it.')
    document_type: int | None = None
    name: str | None = None
    email: str | None = None
    created_at: str
    created_by: str
    last_invoiced_at: str | None = None
    updated_at: str | None = None
    updated_by: str | None = None


class CustomersResponse(BaseModel):
    '''
        The customers of one shop.
    '''
    items: list[CustomerOut]
    total: int


class CustomerPatch(BaseModel):
    '''
        A correction. What it carries replaces what was stored; what it leaves
        out stays as it was.
    '''
    name: str | None = Field(None, max_length = 200)
    document_type: int | None = Field(None, ge = 1, le = 5)
    email: str | None = Field(None, max_length = 254,
                              pattern = r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


class CustomerEdit(CustomerPatch):
    '''
        Which customer is corrected, and how.
    '''
    document: str = Field(..., min_length = 1, max_length = 40)
