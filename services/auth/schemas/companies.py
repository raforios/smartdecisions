'''
    Companies Schema: the customers of the platform (ADMIN only).

    A company is the `client` every user of a customer shares and every
    service keys its data by. Its name is that key, so it never changes:
    renaming it would leave the company's data in FINANCE, QUOTES and the
    rest under a name nobody has.
'''
from enum import Enum

from pydantic import BaseModel, Field


class CompanyError(str, Enum):
    '''
        Why a request on a company was refused: a code, the wording belongs
        to the portal.
    '''
    COMPANY_NOT_FOUND = 'COMPANY_NOT_FOUND'
    DUPLICATE_COMPANY = 'DUPLICATE_COMPANY'
    COMPANY_HAS_USERS = 'COMPANY_HAS_USERS'
    COMPANY_INACTIVE = 'COMPANY_INACTIVE'


# Bolivian tax ids (NIT) are numbers; the length bounds leave room for both
# people and companies.
TAX_ID_PATTERN = r'^\d{5,20}$'


class CompanyRequest(BaseModel):
    '''
        A new company.
    '''
    name: str = Field(..., min_length = 3, max_length = 50,
                      description = 'Legal name; it is the users\' client and never changes.')
    tax_id: str | None = Field(None, pattern = TAX_ID_PATTERN,
                               description = 'NIT, digits only.')


class CompanyUpdateRequest(BaseModel):
    '''
        What may change in a company: its NIT and whether it is active.
    '''
    tax_id: str | None = Field(None, pattern = TAX_ID_PATTERN, description = 'NIT, digits only.')
    active: bool | None = Field(None, description = 'An inactive company is not offered '
                                                    'for new users.')


class CompanyResponse(BaseModel):
    '''
        A company as stored, with how many users it has.
    '''
    name: str
    tax_id: str | None = None
    active: bool
    users: int = Field(0, description = 'Users whose client is this company.')
    created_at: str
    updated_at: str
