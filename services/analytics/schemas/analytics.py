'''
    Pydantic V2 DTOs for the Analytics service.

    The public contract is the list of `Opportunity` items: each one represents
    a (point of sale, recommended product) pair, ranked by expected monetary
    impact (Afinidad × Drop Size, per SMARTDECISIONS.md §2). The pairing of
    affinity rules with drop-size weighting is the differentiator of the SaaS.
'''
from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class AnalyticsError(str, Enum):
    '''
        Why a request could not be served. Travels as the error `detail` so the
        client renders its own wording, same contract as the rest of the API.
    '''
    INVALID_DATE = 'INVALID_DATE'
    NO_DATE_COLUMN = 'NO_DATE_COLUMN'
    EMPTY_PERIOD = 'EMPTY_PERIOD'
    DATASET_UNREADABLE = 'DATASET_UNREADABLE'
    RUN_NOT_FOUND = 'RUN_NOT_FOUND'


class Opportunity(BaseModel):
    '''
        A single actionable recommendation for a point of sale.
    '''
    pdv_id: str
    pdv_name: Optional[str] = None
    recommended_product_id: str
    recommended_product_name: Optional[str] = None
    based_on_products: list[str] = Field(
        ..., description = 'Antecedent SKUs the PdV already purchases.'
    )
    based_on_product_names: list[str] = Field(
        default_factory = list,
        description = 'Readable names of the antecedent SKUs, for display.'
    )
    support: float = Field(..., ge = 0, le = 1)
    confidence: float = Field(..., ge = 0, le = 1)
    lift: float = Field(..., ge = 0)
    expected_drop_size_units: float = Field(..., ge = 0)
    expected_drop_size_amount: Optional[float] = Field(
        default = None, ge = 0,
        description = 'Only present when unit_price is available in the source.'
    )
    opportunity_score: float = Field(
        ..., ge = 0,
        description = '''Ranking metric = lift * confidence * expected_drop_size_amount
        (or _units when amount missing).'''
    )


class AnalyticsSummary(BaseModel):
    '''
        High-level numbers describing an analytics run.
    '''
    total_pos_with_opportunities: int = Field(..., ge = 0)
    total_opportunities: int = Field(..., ge = 0)
    total_expected_value: Optional[float] = Field(
        default = None,
        description = '''Sum of expected_drop_size_amount across all opportunities
        (when prices are available).'''
    )
    affinity_rules_evaluated: int = Field(..., ge = 0)
    parameters: dict


class AnalyticsRunResponse(BaseModel):
    '''
        Response payload for POST /v1/analytics/run/{dataset_id}.
    '''
    dataset_id: str
    run_id: str
    status: str = Field(..., description = "'completed' or 'failed'.")
    summary: AnalyticsSummary
    opportunities: list[Opportunity]
    created_at: datetime


class RunSummary(BaseModel):
    '''
        One row of "my analyses".

        Lighter than the full results on purpose: a history list says when a
        dataset was analysed and how much it found, not every opportunity.
    '''
    run_id: str
    dataset_id: str
    status: str
    total_opportunities: int = 0
    total_pos_with_opportunities: int = 0
    total_expected_value: Optional[float] = None
    created_at: str


class RunListResponse(BaseModel):
    '''
        The caller's own analyses, most recent first.

        Only the caller's: the owner is part of the query, so the panel that
        shows "your last analysis" cannot surface another client's.
    '''
    owner_email: str
    count: int = Field(..., ge = 0)
    runs: List[RunSummary] = Field(default_factory = list)


class AnalyticsResultsResponse(BaseModel):
    '''
        Compact result for GET /v1/analytics/results/{dataset_id}.
    '''
    dataset_id: str
    run_id: str
    status: str
    summary: AnalyticsSummary
    opportunities: list[Opportunity]
    created_at: datetime


class AnalyticsPdvResponse(BaseModel):
    '''
        Top N opportunities for a single point of sale.
    '''
    dataset_id: str
    pdv_id: str
    opportunities: list[Opportunity]


# --- Commercial summary (general sales dashboard) ---

class MetricCode(str, Enum):
    '''
        Identifier of a headline KPI.

        The backend reports which metric it computed and its value; the label and
        the explanation belong to whoever shows them (the frontend today, the
        interpretation layer tomorrow).
    '''
    UNITS_PER_ORDER = 'UNITS_PER_ORDER'
    PRODUCTS_PER_ORDER = 'PRODUCTS_PER_ORDER'
    AMOUNT_PER_ORDER = 'AMOUNT_PER_ORDER'
    ORDER_COUNT = 'ORDER_COUNT'
    MOM_CHANGE = 'MOM_CHANGE'
    YOY_CHANGE = 'YOY_CHANGE'
    GROSS_MARGIN = 'GROSS_MARGIN'
    GROSS_MARGIN_PERCENT = 'GROSS_MARGIN_PERCENT'
    COST_OF_GOODS = 'COST_OF_GOODS'
    MARGIN_PER_ORDER = 'MARGIN_PER_ORDER'
    PORTFOLIO_CLIENTS = 'PORTFOLIO_CLIENTS'
    ACTIVE_LAST_MONTH = 'ACTIVE_LAST_MONTH'
    COVERAGE = 'COVERAGE'
    CHURN_LAST_MONTH = 'CHURN_LAST_MONTH'
    CLIENTS_AT_RISK = 'CLIENTS_AT_RISK'
    CLIENTS_LOST = 'CLIENTS_LOST'
    PURCHASE_FREQUENCY = 'PURCHASE_FREQUENCY'
    TOTAL_SALES = 'TOTAL_SALES'
    SALES_COUNT = 'SALES_COUNT'
    AVERAGE_TICKET = 'AVERAGE_TICKET'
    UNITS_SOLD = 'UNITS_SOLD'
    CLIENT_COUNT = 'CLIENT_COUNT'
    PRODUCT_COUNT = 'PRODUCT_COUNT'
    LAST_MONTH_SALES = 'LAST_MONTH_SALES'
    MONTHLY_AVERAGE = 'MONTHLY_AVERAGE'


class KpiCard(BaseModel):
    '''
        A single headline KPI. `format` tells the UI how to render `value`
        ('money' -> Bs with 2 decimals, 'int' -> thousands-grouped integer,
        'percent' -> share, 'decimal' -> plain number).

        `value` is optional because a percentage variation without a base
        period is undefined, not zero: growing from no sales at all has no
        percentage. The UI renders those as '—' instead of a misleading 0%.
    '''
    metric_code: MetricCode
    value: Optional[float] = None
    format: str
    reference: Optional[str] = Field(None,
                description = "Period or entity the value refers to, e.g. '2026-05'.")


class RankRow(BaseModel):
    '''One row of a best/worst ranking: a readable label and its amount (Bs).'''
    label: str
    amount: float


class DistRow(BaseModel):
    '''
        One slice of a categorical distribution: label, amount (Bs) and its
        share of the total.
    '''
    label: str
    amount: float
    percentage: float


class TrendPoint(BaseModel):
    '''One point of the monthly sales trend.'''
    month: str
    amount: float


# --- Demand forecast ---

class ForecastPoint(BaseModel):
    '''One month of a forecast series (historical or projected).'''
    month: str
    amount: float


class ForecastSeries(BaseModel):
    '''
        A named forecast series: its historical months and the projected ones,
        plus the projected total for the horizon.
    '''
    name: str
    history: list[ForecastPoint]
    forecast: list[ForecastPoint]
    total_forecast: float


class ForecastBlock(BaseModel):
    '''What the forecast engine produces, independent of the HTTP envelope.'''
    method: str
    months_ahead: int
    series: list[ForecastSeries] = []


class ForecastResponse(ForecastBlock):
    '''
        Demand forecast for GET /v1/analytics/forecast/{dataset_id}.
    '''
    dataset_id: str

# --- Customer segmentation ---

class SegmentTier(BaseModel):
    '''A value tier (Alto/Medio/Bajo) with its client count and sales share.'''
    tier: str
    clients: int
    amount: float
    percentage: float


class SegmentClient(BaseModel):
    '''One client row: label, tier, total amount and number of purchases.'''
    client: str
    tier: str
    amount: float
    purchases: int


class SegmentationBlock(BaseModel):
    '''What the segmentation engine produces, without the HTTP envelope.'''
    total_clients: int = 0
    tiers: list[SegmentTier] = []
    clients: list[SegmentClient] = []


class SegmentationResponse(SegmentationBlock):
    '''
        Customer value segmentation for GET /v1/analytics/segmentation/{dataset_id}.
    '''
    dataset_id: str

# --- Period scoping (shared by every analysis endpoint) ---

class PeriodInfo(BaseModel):
    '''
        Describes the window an analysis actually ran on, so the UI can state
        'Enero a Marzo de 2024' instead of leaving the user guessing whether a
        filter was applied.
    '''
    available_from: Optional[str] = None
    available_to: Optional[str] = None
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    filtered: bool = False
    rows: int = 0


# --- Growth (month-over-month, year-over-year, seasonality) ---

class MonthlyChange(BaseModel):
    '''One month of the sales series with its variation against the previous one.'''
    month: str
    amount: float
    change: Optional[float] = None


class SeasonIndex(BaseModel):
    '''
        Seasonality index of one calendar month: 100 is an average month, 130
        means that month historically sells 30% above average.
    '''
    month: int = Field(..., ge = 1, le = 12,
                description = 'Calendar month number; the UI names it.')
    index_value: float
    average_amount: float


class CategoryMix(BaseModel):
    '''
        How a category's share of total sales moved between the last month and
        the one before it. `share_change` is in percentage points.
    '''
    label: str
    current_amount: float
    previous_amount: float
    change: Optional[float] = None
    current_share: float
    previous_share: float
    share_change: float


class GrowthBlock(BaseModel):
    '''Growth section of the commercial summary.'''
    kpis: list[KpiCard] = []
    monthly_change: list[MonthlyChange] = []
    seasonality: list[SeasonIndex] = []
    category_mix: list[CategoryMix] = []


# --- Concentration (dependency risk) ---

class ConcentrationLevel(str, Enum):
    '''
        How concentrated the revenue is, read off the HHI. A code: the sentence
        that explains it to a manager belongs to the frontend.
    '''
    HIGH = 'HIGH'
    MODERATE = 'MODERATE'
    LOW = 'LOW'


class ClientConcentration(BaseModel):
    '''
        How dependent the business is on a few clients: what the top 10 weigh,
        how many clients make up 80% of sales (Pareto) and the HHI index with a
        plain-language reading of it.
    '''
    total_clients: int = 0
    top10_amount: float = 0.0
    top10_percentage: float = 0.0
    pareto_clients: int = 0
    pareto_client_percentage: float = 0.0
    hhi: float = 0.0
    hhi_level: Optional[str] = None
    top_clients: list[DistRow] = []


class AbcClass(BaseModel):
    '''One ABC class with its product count, amount and share of sales.'''
    abc_class: str
    products: int
    amount: float
    percentage: float


class AbcProduct(BaseModel):
    '''One product's ABC classification and its cumulative share of sales.'''
    label: str
    amount: float
    abc_class: str
    cumulative: float


class AbcBlock(BaseModel):
    '''ABC classification of the product catalog.'''
    summary: list[AbcClass] = []
    products: list[AbcProduct] = []


class ConcentrationBlock(BaseModel):
    '''Concentration section of the commercial summary.'''
    clients: ClientConcentration = ClientConcentration()
    abc: AbcBlock = AbcBlock()


# --- Efficiency (drop size, sales force, realized price) ---

class SellerProductivity(BaseModel):
    '''Productivity of one salesperson.'''
    seller: str
    amount: float
    orders: int
    clients: int
    average_ticket: float
    lines_per_order: float
    amount_per_client: float


class PriceDrift(BaseModel):
    '''
        Realized price of a product in the recent half of the period versus the
        earlier half. Catches discounting that never shows up in a price list.
    '''
    product: str
    current_price: float
    previous_price: float
    change: Optional[float] = None


class EfficiencyBlock(BaseModel):
    '''Efficiency section of the commercial summary.'''
    kpis: list[KpiCard] = []
    sellers: list[SellerProductivity] = []
    prices: list[PriceDrift] = []


# --- Gross margin (requires the optional unit-cost column) ---

class MarginRow(BaseModel):
    '''Revenue, cost and gross margin of one category / product / client / seller.'''
    label: str
    amount: float
    cost: float
    margin: float
    margin_percentage: float


class MarginAlertReason(str, Enum):
    '''Why a product was flagged: sold below cost, or at a negligible margin.'''
    BELOW_COST = 'BELOW_COST'
    THIN_MARGIN = 'THIN_MARGIN'


class MarginAlert(BaseModel):
    '''A product sold below cost or at a negligible margin, with the reason.'''
    label: str
    amount: float
    margin: float
    margin_percentage: float
    reason_code: MarginAlertReason


class MarginBlock(BaseModel):
    '''
        Profitability section. `available` is False when the uploaded file had
        no unit-cost column, in which case every list is empty and the UI
        hides the block instead of rendering zeros.
    '''
    available: bool = False
    kpis: list[KpiCard] = []
    by_category: list[MarginRow] = []
    by_product: list[MarginRow] = []
    by_client: list[MarginRow] = []
    by_seller: list[MarginRow] = []
    alerts: list[MarginAlert] = []


# --- Portfolio health ---

class PortfolioMovement(BaseModel):
    '''Client movement in one month: new, recovered, retained and lost.'''
    month: str
    active: int
    new_clients: int
    recovered: int
    retained: int
    lost: int
    churn: Optional[float] = None


class RiskReason(str, Enum):
    '''
        Why a client is listed as at risk or lost.

        A stable code, never a sentence: the wording belongs to whoever shows it
        (the frontend today, the interpretation layer tomorrow). The facts that
        justify it travel in the same row (`days_without_purchase`, `change`).
    '''
    LONG_SILENCE = 'LONG_SILENCE'
    SILENCE = 'SILENCE'
    PURCHASE_DROP = 'PURCHASE_DROP'


class ClientAtRisk(BaseModel):
    '''
        A client whose purchases dropped sharply or who stopped buying.
        Recency is measured against the newest date in the dataset, not today,
        so an old file does not report the whole portfolio as lost.
    '''
    client: str
    monthly_average_amount: float
    last_month_amount: float
    change: Optional[float] = None
    days_without_purchase: int
    last_purchase: Optional[str] = None
    reason_code: Optional[RiskReason] = None


class PortfolioBlock(BaseModel):
    '''What the portfolio engine produces, without the HTTP envelope.'''
    kpis: list[KpiCard] = []
    movement: list[PortfolioMovement] = []
    at_risk: list[ClientAtRisk] = []
    total_at_risk: int = 0
    lost: list[ClientAtRisk] = []
    total_lost: int = 0


class PortfolioResponse(PortfolioBlock):
    '''
        Portfolio health for GET /v1/analytics/portfolio/{dataset_id}.

        `at_risk` and `lost` are deliberately separate lists: a client
        who slipped this month is a visit, one who has been gone half a year is
        a campaign. Merged, the short actionable list drowns in the long one.
    '''
    dataset_id: str
    period: PeriodInfo = PeriodInfo()

# --- Commercial summary (assembled last: it embeds every block above) ---

class CommercialSummaryBlock(BaseModel):
    '''
        The sales picture the summary engine derives from the dataset, without
        the HTTP envelope and without the blocks assembled by the controller.
    '''
    kpis: list[KpiCard] = []
    best_clients: list[RankRow] = []
    worst_clients: list[RankRow] = []
    top_products: list[RankRow] = []
    bottom_products: list[RankRow] = []
    by_category: list[DistRow] = []
    by_channel: list[DistRow] = []
    by_region: list[DistRow] = []
    by_seller: list[DistRow] = []
    monthly_trend: list[TrendPoint] = []


class CommercialSummaryResponse(CommercialSummaryBlock):
    '''
        Full commercial summary for GET /v1/analytics/summary/{dataset_id}.

        The first block answers 'how much did we sell'; the four that follow
        answer the questions a manager asks next — is it growing, how exposed
        are we, how efficiently are we selling, and what does it actually earn.
        Every section is pre-labeled and pre-aggregated for tables + charts.
    '''
    dataset_id: str
    period: PeriodInfo = PeriodInfo()
    growth: GrowthBlock = GrowthBlock()
    concentration: ConcentrationBlock = ConcentrationBlock()
    efficiency: EfficiencyBlock = EfficiencyBlock()
    margin: MarginBlock = MarginBlock()
