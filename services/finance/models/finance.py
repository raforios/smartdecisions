'''
    DynamoDB item definitions for the financial analysis.

    The catalog and the law parameters are global: one copy for every client,
    and only an ADMIN of BearSoft changes them. What a client loads —its loads
    and their amounts— lives under its own key.
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
    invoiced: bool | None
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


class LoadItem(TypedDict, total = False):
    '''
        One load a client made, by API or by file.

        Table: finance_loads
        Partition Key: client (String) — the owner, never a filter after the fact.
        Sort Key: load_id (String) — starts with the moment of the load, so
                  the history reads newest first with no index.
    '''
    client: str
    load_id: str
    user: str
    flow: str
    channel: str
    file_key: str | None
    accepted: int
    rejected: int
    created_at: str


class EntryItem(TypedDict, total = False):
    '''
        One amount of one account in one period.

        Table: finance_entries
        Partition Key: client (String).
        Sort Key: entry_key (String) — "<periodicity>#<date>#<account_code>":
                  a period is a prefix, so a month, its days or a year are
                  read with begins_with, and a reload of the same account and
                  period overwrites instead of duplicating.
        Index: account_code-index (account_code, keys only) — whether any
               client filed figures under an account, before it is removed.
    '''
    client: str
    entry_key: str
    periodicity: str
    date: str
    account_code: str
    amount: float
    note: str | None
    taxes_included: bool | None
    flow: str
    load_id: str
    user: str
    updated_at: str
