'''
    Pydantic V2 DTOs for what a client loads: amounts per account and period.

    The file and the API share one contract and one validator. A row that
    breaks a rule is set aside with its code and the rest goes in, so the
    fields a row arrives with are loose here and the rules live in the
    validator, where each failure gets its own code instead of rejecting the
    whole request.

    The client fills a template in Spanish; the API speaks English. The
    mapper between them is derived from `ENTRY_COLUMNS`, never written twice.
'''
from dataclasses import dataclass
from enum import Enum
from pydantic import BaseModel, Field


class LoadError(str, Enum):
    '''
        Why a row, or a whole load, was refused.
    '''
    EMPTY_LOAD = 'EMPTY_LOAD'
    UNKNOWN_ACCOUNT = 'UNKNOWN_ACCOUNT'
    ACCOUNT_IS_GROUP = 'ACCOUNT_IS_GROUP'
    MISSING_DATE = 'MISSING_DATE'
    INVALID_PERIODICITY = 'INVALID_PERIODICITY'
    DATE_PERIODICITY_MISMATCH = 'DATE_PERIODICITY_MISMATCH'
    PERIODICITY_CONFLICT = 'PERIODICITY_CONFLICT'
    INVALID_AMOUNT = 'INVALID_AMOUNT'
    NEGATIVE_AMOUNT = 'NEGATIVE_AMOUNT'
    FUTURE_PERIOD = 'FUTURE_PERIOD'
    DUPLICATE_ROW = 'DUPLICATE_ROW'
    MISSING_TAXES_INCLUDED = 'MISSING_TAXES_INCLUDED'
    ENTRY_NOT_FOUND = 'ENTRY_NOT_FOUND'


class Periodicity(str, Enum):
    '''
        How often a figure was taken. Days add up to the month and months to
        the year; a year loaded as such is never split into invented months.
    '''
    DAILY = 'DAILY'
    MONTHLY = 'MONTHLY'
    ANNUAL = 'ANNUAL'


class LoadFlow(str, Enum):
    '''
        Chosen on each load. PROCESSED brings every amount, taxes included;
        BASE brings the base figures and the taxes are computed from the law
        parameters.
    '''
    PROCESSED = 'PROCESSED'
    BASE = 'BASE'


class LoadChannel(str, Enum):
    '''
        How a load arrived.
    '''
    API = 'API'
    FILE = 'FILE'


@dataclass(frozen = True)
class EntryColumn:
    '''
        One column of the data template: the API field and the header the
        client reads.
    '''
    field: str
    header: str


# Order is the template order.
ENTRY_COLUMNS: tuple[EntryColumn, ...] = (
    EntryColumn('date', 'Fecha'),
    EntryColumn('periodicity', 'Periodicidad'),
    EntryColumn('account_code', 'Código de cuenta'),
    EntryColumn('amount', 'Monto'),
    EntryColumn('note', 'Nota'),
    EntryColumn('taxes_included', 'Impuestos incluidos'),
)
HEADER_TO_FIELD: dict[str, str] = {column.header: column.field for column in ENTRY_COLUMNS}

# The words the client writes in the template, and what they mean.
PERIODICITY_LABELS: dict[str, Periodicity] = {
    'DIARIA': Periodicity.DAILY,
    'MENSUAL': Periodicity.MONTHLY,
    'ANUAL': Periodicity.ANNUAL,
}
YES_NO_LABELS: dict[str, bool] = {'SÍ': True, 'SI': True, 'NO': False}


class EntryRowSchema(BaseModel):
    '''
        One row as it arrives, by API or read from the file. Loose on
        purpose: the validator, not the parser, decides what is wrong with it.
    '''
    date: str | int | None = Field(None, description = 'YYYY-MM-DD, YYYY-MM or YYYY.')
    periodicity: str | None = Field(None, description = 'DAILY, MONTHLY or ANNUAL.')
    account_code: str | None = Field(None, description = 'An account of the catalog.')
    amount: float | str | None = Field(None, description = 'In bolivianos, never negative.')
    note: str | None = Field(None, max_length = 500)
    taxes_included: bool | str | None = Field(
        None, description = 'Mandatory on the accounts of sales with invoice.'
    )


class EntryLoadSchema(BaseModel):
    '''
        A load pushed by API.
    '''
    flow: LoadFlow
    rows: list[EntryRowSchema] = Field(..., min_length = 1)


class EntryFileLoadSchema(BaseModel):
    '''
        A load from a file the client already uploaded through FILES.
    '''
    flow: LoadFlow
    file_key: str = Field(..., min_length = 1, max_length = 500,
                          description = 'Object key FILES answered with.')


class RejectedRowSchema(BaseModel):
    '''
        One row set aside, with why.
    '''
    row: int = Field(..., description = 'Position in the load; in a file, the Excel row.')
    code: LoadError
    value: str | None = Field(None, description = 'The value that broke the rule.')


class LoadResultSchema(BaseModel):
    '''
        What a load did.
    '''
    load_id: str
    flow: LoadFlow
    channel: LoadChannel
    accepted: int
    rejected: list[RejectedRowSchema]


class LoadSchema(BaseModel):
    '''
        A past load, as the client's history shows it.
    '''
    load_id: str
    user: str
    flow: LoadFlow
    channel: LoadChannel
    accepted: int
    rejected: int
    created_at: str


class LoadListResponseSchema(BaseModel):
    '''
        The loads of the client, newest first.
    '''
    loads: list[LoadSchema]
    total: int


class EntrySchema(BaseModel):
    '''
        One stored amount.
    '''
    periodicity: Periodicity
    date: str
    account_code: str
    amount: float
    note: str | None = None
    taxes_included: bool | None = None
    flow: LoadFlow
    load_id: str
    user: str
    updated_at: str


class EntryListResponseSchema(BaseModel):
    '''
        Stored amounts, ordered by periodicity, date and account.
    '''
    entries: list[EntrySchema]
    total: int


class EntryUpdateSchema(BaseModel):
    '''
        A correction of one stored amount: what the client got wrong. The
        account is not here — a figure filed under the wrong account is
        deleted and loaded again.
    '''
    date: str | None = Field(None, description = 'The right date, same periodicity.')
    amount: float | None = Field(None, ge = 0)
    note: str | None = Field(None, max_length = 500)
    taxes_included: bool | None = None


class PeriodDeleteResultSchema(BaseModel):
    '''
        What deleting a period removed.
    '''
    periodicity: Periodicity
    date: str
    deleted: int
