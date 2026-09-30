'''
    Fluctuating factor models for DynamoDB.
'''
from typing import Optional, TypedDict


class FactorItem(TypedDict, total = False):
    '''
        One fluctuating factor an account declared.

        Table: quotes_factors
        Partition Key: owner_email (String)
        Sort Key: code (String) — the identifier the client gives it.

        `status` is what lets a factor leave without being deleted: an
        inactive one keeps every reading it has and simply stops counting.
    '''
    owner_email: str
    code: str
    name: str
    unit: str
    source: Optional[str]
    status: str
    latest_date: Optional[str]
    latest_value: Optional[float]
    created_at: str
    updated_at: str


class FactorValueItem(TypedDict, total = False):
    '''
        What a factor was worth on one day.

        Table: quotes_factor_values
        Partition Key: owner_code (String) — "<owner_email>#<code>", so one
                       query returns the whole series of one factor.
        Sort Key: factor_date (String, 'YYYY-MM-DD') — sorts and ranges as a
                  date because ISO text does.
    '''
    owner_code: str
    factor_date: str
    value: float
    recorded_at: str
