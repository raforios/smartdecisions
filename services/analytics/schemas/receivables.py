'''
    Pydantic V2 DTOs of the receivables view.

    They live beside `analytics.py` and not inside it because that file already
    declares the five blocks of the commercial summary and the thousand-line
    limit is there for a reason. The dependency goes one way: this module reads
    `PeriodInfo` from the main schema and nothing imports back.

    Same rule as everywhere else in the product: what travels is data and
    codes — `AgingBucket.DAYS_31_60`, `CreditRisk.DELINQUENT` — never the
    sentence a manager reads.
'''
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from schemas.analytics import PeriodInfo


class AgingBucket(str, Enum):
    '''
        Where an open balance sits on the aging scale. A code: the label and the
        wording belong to whoever renders it.
    '''
    CURRENT = 'CURRENT'
    DAYS_1_15 = 'DAYS_1_15'
    DAYS_16_30 = 'DAYS_16_30'
    DAYS_31_60 = 'DAYS_31_60'
    DAYS_61_90 = 'DAYS_61_90'
    DAYS_91_120 = 'DAYS_91_120'
    DAYS_OVER_120 = 'DAYS_OVER_120'


class CreditRisk(str, Enum):
    '''
        How a debtor reads today, from its own overdue balance and history.
    '''
    HEALTHY = 'HEALTHY'
    WATCH = 'WATCH'
    DELINQUENT = 'DELINQUENT'
    CRITICAL = 'CRITICAL'


class ReceivablesUnavailable(str, Enum):
    '''
        Why the receivables view cannot be built. A code, so the frontend can
        say what to do about it instead of showing an empty dashboard.
    '''
    NO_CREDIT_COLUMNS = 'NO_CREDIT_COLUMNS'
    NO_CREDIT_SALES = 'NO_CREDIT_SALES'


class AgingRow(BaseModel):
    '''
        One aging bucket with what it holds and what it is expected to lose.

        `expected_loss_rate` travels with the row because it is a policy
        parameter, not a fact: showing the provision without the rate that
        produced it would hide the only number the client can argue with.
    '''
    bucket_code: AgingBucket
    invoices: int = 0
    clients: int = 0
    amount: float = 0.0
    share: float = 0.0
    expected_loss_rate: float = 0.0
    provision: float = 0.0


class ReceivablesKpis(BaseModel):
    '''
        The position of the credit book, its speed and what it is worth.

        Every figure is derived at invoice level against a reference date: the
        last day with activity in the dataset, not the day the request runs, or
        a file from last quarter would report its whole book as overdue.
    '''
    as_of: Optional[str] = Field(None, description = 'Reference date, ISO.')
    credit_amount: float = 0.0
    cash_amount: float = 0.0
    credit_share: float = 0.0
    receivable_total: float = 0.0
    current_amount: float = 0.0
    overdue_amount: float = 0.0
    overdue_rate: float = 0.0
    clients_with_debt: int = 0
    open_invoices: int = 0
    recoverable_amount: float = 0.0
    uncollectible_amount: float = 0.0
    recoverable_rate: float = 0.0
    uncollectible_rate: float = 0.0
    days_sales_outstanding: Optional[float] = None
    average_days_delinquent: float = 0.0
    weighted_days_late: float = 0.0
    collection_effectiveness: Optional[float] = Field(
        None, description = 'CEI over the configured window, 0-100.'
    )
    on_time_rate: Optional[float] = None
    average_term_granted: Optional[float] = None
    average_term_real: Optional[float] = None


class CreditMargin(BaseModel):
    '''
        What the credit actually earns, once financed and provisioned.

        The gross margin of a credit sale is not what it leaves: the money is
        out for a number of days and part of it never comes back. `net_margin`
        is the figure that changes a decision, and it can be negative on a
        client whose gross margin looks fine.
    '''
    available: bool = False
    reason_code: Optional[str] = None
    credit_revenue: float = 0.0
    credit_gross_margin: float = 0.0
    credit_gross_margin_rate: Optional[float] = None
    financing_cost: float = 0.0
    delinquency_cost: float = 0.0
    expected_loss: float = 0.0
    net_margin: float = 0.0
    net_margin_rate: Optional[float] = None
    cash_gross_margin_rate: Optional[float] = None


class DebtorRow(BaseModel):
    '''
        One client with debt, read the way a collector reads it.

        `limit_utilization` is None when the client has no credit limit in the
        file: an unknown limit is not an unused one.
    '''
    label: str
    open_amount: float = 0.0
    overdue_amount: float = 0.0
    oldest_days: int = 0
    weighted_days_late: float = 0.0
    invoices: int = 0
    credit_limit: Optional[float] = None
    limit_utilization: Optional[float] = None
    risk_code: CreditRisk = CreditRisk.HEALTHY
    collector: Optional[str] = None


class CollectorRow(BaseModel):
    '''
        One person responsible for collecting, with what they are carrying and
        how well it is going.

        `on_time_rate` measures the collector; the overdue amount measures the
        book they were handed. Both travel because judging one by the other is
        how a good collector on a bad zone gets blamed.
    '''
    label: str
    open_amount: float = 0.0
    overdue_amount: float = 0.0
    clients: int = 0
    invoices: int = 0
    weighted_days_late: float = 0.0
    on_time_rate: Optional[float] = None


class DueWindow(BaseModel):
    '''
        What falls due inside one window, for the cash projection.
    '''
    window_code: str = Field(
        ..., description = 'OVERDUE | DAYS_7 | DAYS_15 | DAYS_30 | BEYOND.'
    )
    amount: float = 0.0
    invoices: int = 0


class DueDateRow(BaseModel):
    '''One calendar date with what it is due to collect.'''
    due_date: str
    amount: float = 0.0
    invoices: int = 0
    clients: int = 0


class CollectionCurvePoint(BaseModel):
    '''
        One invoice cohort and how much of it had been collected by 30, 60 and
        90 days. It answers whether collection is getting faster or slower,
        which a single DSO figure cannot.
    '''
    cohort_month: str
    credit_amount: float = 0.0
    collected_30: Optional[float] = None
    collected_60: Optional[float] = None
    collected_90: Optional[float] = None


class PriorityRow(BaseModel):
    '''
        Who to call today. The score is amount × age × recovery probability, so
        a large balance that is still recoverable outranks an old one that is
        not — which is the opposite of sorting by days overdue.
    '''
    label: str
    collector: Optional[str] = None
    overdue_amount: float = 0.0
    oldest_days: int = 0
    recovery_probability: float = 0.0
    expected_recovery: float = 0.0
    risk_code: CreditRisk = CreditRisk.HEALTHY


class CreditPolicy(BaseModel):
    '''
        The policy the figures were computed with, and where it came from.

        It travels with the answer because two clients with the same book get
        different provisions, and the reader has to be able to see which
        parameters produced the number.
    '''
    source_code: str = Field(
        ..., description = 'CLIENT when the client has a stored policy, DEFAULT '
                           'when the service defaults were used.'
    )
    aging_buckets: list[int] = []
    loss_rates: list[float] = []
    financial_rate_daily: float = 0.0
    delinquent_days: int = 0
    default_term_days: int = 0


class ReceivablesBlock(BaseModel):
    '''
        Receivables view: the credit book, its aging, who owes, who collects,
        what falls due and what it is worth.

        `available` is False —with a code— when the dataset carries no credit
        columns. Rendering zeros instead would state that nothing is owed,
        which is a different and false statement.
    '''
    available: bool = False
    reason_code: Optional[str] = None
    policy: Optional[CreditPolicy] = None
    kpis: ReceivablesKpis = ReceivablesKpis()
    margin: CreditMargin = CreditMargin()
    aging: list[AgingRow] = []
    debtors: list[DebtorRow] = []
    collectors: list[CollectorRow] = []
    due_windows: list[DueWindow] = []
    due_dates: list[DueDateRow] = []
    collection_curve: list[CollectionCurvePoint] = []
    priority: list[PriorityRow] = []


class ReceivablesResponse(BaseModel):
    '''
        Full receivables view for GET /v1/analytics/receivables/{dataset_id}.
    '''
    dataset_id: str
    period: PeriodInfo = PeriodInfo()
    available: bool = False
    reason_code: Optional[str] = None
    policy: Optional[CreditPolicy] = None
    kpis: ReceivablesKpis = ReceivablesKpis()
    margin: CreditMargin = CreditMargin()
    aging: list[AgingRow] = []
    debtors: list[DebtorRow] = []
    collectors: list[CollectorRow] = []
    due_windows: list[DueWindow] = []
    due_dates: list[DueDateRow] = []
    collection_curve: list[CollectionCurvePoint] = []
    priority: list[PriorityRow] = []


class CreditPolicyRequest(BaseModel):
    '''
        The parameters a client of SmartDecisions can set for its own book.

        Every field is optional and what is not sent falls back to the service
        default, field by field: somebody who only wants to change the interest
        rate should not have to restate the whole policy.
    '''
    aging_buckets: Optional[list[int]] = Field(
        None, min_length = 1, max_length = 10,
        description = 'Upper bound of each overdue bucket, in days, ascending.'
    )
    loss_rates: Optional[list[float]] = Field(
        None, min_length = 2, max_length = 11,
        description = 'Expected loss per bucket, 0 to 1: one for CURRENT plus '
                      'one per overdue bucket.'
    )
    financial_rate_daily: Optional[float] = Field(None, ge = 0, le = 1)
    delinquent_days: Optional[int] = Field(None, ge = 0, le = 365)
    default_term_days: Optional[int] = Field(None, ge = 0, le = 365)


class CreditPolicyResponse(CreditPolicy):
    '''The stored policy of the caller, as it will be applied.'''
    owner_email: str
