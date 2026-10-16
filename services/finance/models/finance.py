'''
    DynamoDB item definitions for the financial analysis.

    The catalog and the law parameters are global: one copy for every client,
    and only an ADMIN of BearSoft changes them. What a client loads lives under
    its own key (the loads and their amounts, next phase).
'''
from typing import TypedDict


class AccountItem(TypedDict, total = False):
    '''
        One account of the chart, or one group of accounts.

        Table: finance_accounts
        Partition Key: account_code (String), e.g. 6.1.07 or 6.1.

        A group has no `group_code`. `account_type` is the digit of the type
        (1 to 6) as the plan writes it.
    '''
    account_code: str
    name: str
    account_type: str
    group_code: str | None
    subtracts: bool
    created_at: str
    updated_at: str


class LawParameterItem(TypedDict, total = False):
    '''
        One value of a rate set by law, from the day it applies.

        Table: finance_law_parameters
        Partition Key: parameter_code (String), e.g. IVA.
        Sort Key: valid_from (String, 'YYYY-MM-DD') — sorts as a date because
                  ISO text does, so the rate in force on a day is the last one
                  that starts on or before it.
    '''
    parameter_code: str
    valid_from: str
    name: str
    rate: float
    created_at: str
    updated_at: str
