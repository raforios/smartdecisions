'''
    Pydantic V2 DTOs for the financial analysis.

    There is one chart of accounts and it belongs to BearSoft: every client
    files its figures against the same codes, and only an ADMIN adds, edits or
    removes an account. The same goes for the law: a tax rate is one for every
    client, and it carries the day it starts to apply, so a month is always
    computed with the rate that was in force during that month.
'''
from datetime import date
from enum import Enum
from pydantic import BaseModel, Field, model_validator


class FinanceError(str, Enum):
    '''
        Why a request on the catalog or the law parameters was refused.

        The codes of the loads live in `schemas/entries.py`; those of the
        calculation join when their phase does. The contract lists them all.
    '''
    ACCOUNT_NOT_FOUND = 'ACCOUNT_NOT_FOUND'
    DUPLICATE_ACCOUNT_CODE = 'DUPLICATE_ACCOUNT_CODE'
    ACCOUNT_IN_USE = 'ACCOUNT_IN_USE'
    GROUP_NOT_FOUND = 'GROUP_NOT_FOUND'
    GROUP_TYPE_MISMATCH = 'GROUP_TYPE_MISMATCH'
    GROUP_HAS_ACCOUNTS = 'GROUP_HAS_ACCOUNTS'


class AccountType(str, Enum):
    '''
        The six types of the Bolivian chart of accounts. The value is the
        digit the type carries in the plan.

        1 to 3 are balances, a picture at a date that is never added up over
        time; 4 to 6 are what moved during a period.
    '''
    ASSET = '1'
    LIABILITY = '2'
    EQUITY = '3'
    INCOME = '4'
    COST = '5'
    EXPENSE = '6'


class AccountSchema(BaseModel):
    '''
        An account of the catalog, or a group of accounts.

        A group has no `group_code`; an account points to the group it sits
        in, and only accounts receive amounts.
    '''
    account_code: str = Field(..., min_length = 1, max_length = 20,
                              description = 'Code of the account, e.g. 6.1.07.')
    name: str = Field(..., min_length = 1, max_length = 150)
    account_type: AccountType
    group_code: str | None = Field(
        None, max_length = 20,
        description = 'Code of the group the account sits in. Empty for a group.'
    )
    subtracts: bool = Field(
        False,
        description = 'True for the "(Menos)" accounts, which subtract within their group.'
    )
    invoiced: bool | None = Field(
        None,
        description = 'Income accounts only: true for a sale with invoice, false without. '
                      'The account says it, so a row never has to.'
    )

    @model_validator(mode = 'after')
    def invoiced_only_on_income(self) -> 'AccountSchema':
        '''
            Only a sale is with or without invoice: the mark means nothing
            on a cost, an expense or a balance.

            Returns:
                AccountSchema: The account, unchanged.

            Raises:
                ValueError: The mark on an account that is not income.
        '''
        if self.invoiced is not None and self.account_type is not AccountType.INCOME:
            raise ValueError('INVOICE_ONLY_ON_INCOME')
        return self


class AccountUpdateSchema(BaseModel):
    '''
        What may change in an account: the text, never what it does.
    '''
    name: str = Field(..., min_length = 1, max_length = 150)


class AccountResponseSchema(AccountSchema):
    '''
        An account as it is stored.
    '''
    updated_at: str


class AccountListResponseSchema(BaseModel):
    '''
        The whole catalog, ordered by code.
    '''
    accounts: list[AccountResponseSchema]
    total: int


class LawParameterSchema(BaseModel):
    '''
        A rate set by law, valid from a day on.

        A new value never overwrites the old one: it is stored with its own
        `valid_from`, and the months before it keep being computed with the
        rate they had.
    '''
    parameter_code: str = Field(..., min_length = 1, max_length = 20,
                                description = 'Stable identifier, e.g. IVA.')
    name: str = Field(..., min_length = 1, max_length = 150)
    rate: float = Field(..., ge = 0, le = 100, description = 'Percentage, e.g. 13 for 13 %.')
    valid_from: date


class LawParameterResponseSchema(LawParameterSchema):
    '''
        A law parameter as it is stored.
    '''
    updated_at: str


class LawParameterListResponseSchema(BaseModel):
    '''
        Every value of every law parameter, ordered by code and date.
    '''
    parameters: list[LawParameterResponseSchema]
    total: int
