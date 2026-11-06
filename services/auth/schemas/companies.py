'''
    Companies Schema: the customers of the platform (ADMIN only).

    A company is the `client` every user of a customer shares and every
    service keys its data by. Its name is that key, so it never changes:
    renaming it would leave the company's data in FINANCE, QUOTES and the
    rest under a name nobody has.

    The sector and whether it bought the invoicing product live here, once
    for every user of the company (Rafael, 2-nov-2026): the menu offers what
    the sector has, the products bought and the role allow.
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


class Sector(str, Enum):
    '''
        What a company does, from the sectors SmartDecisions serves (the
        approved chat design, 2-nov-2026): a closed catalogue, so one
        business is not three spellings.
    '''
    FOOD_AND_DRINKS = 'FOOD_AND_DRINKS'
    RETAIL = 'RETAIL'
    WHOLESALE = 'WHOLESALE'
    HOME_SERVICES = 'HOME_SERVICES'
    WORKSHOP = 'WORKSHOP'
    HEALTH = 'HEALTH'
    TRANSPORT = 'TRANSPORT'
    COURIER = 'COURIER'
    PERSONAL_FINANCE = 'PERSONAL_FINANCE'


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
    sector: Sector | None = None
    includes_billing: bool = Field(False, description = 'Whether it bought SmartBilling.')


class CompanyUpdateRequest(BaseModel):
    '''
        What may change in a company: its NIT, its sector, whether it bought
        the invoicing product and whether it is active.
    '''
    tax_id: str | None = Field(None, pattern = TAX_ID_PATTERN, description = 'NIT, digits only.')
    sector: Sector | None = None
    includes_billing: bool | None = Field(None, description = 'Whether it bought SmartBilling.')
    active: bool | None = Field(None, description = 'An inactive company is not offered '
                                                    'for new users.')


class CompanyResponse(BaseModel):
    '''
        A company as stored, with how many users it has.
    '''
    name: str
    tax_id: str | None = None
    sector: Sector | None = None
    includes_billing: bool = False
    active: bool
    users: int = Field(0, description = 'Users whose client is this company.')
    created_at: str
    updated_at: str
