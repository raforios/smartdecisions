'''
    The exchange-rate effect: what the rate does to sales, margin and the
    ability to restock, for a distributor that buys in dollars and sells in
    bolivianos.
'''

from pydantic import BaseModel, Field

from schemas.analytics import PeriodInfo


class MonthlyFx(BaseModel):
    '''
        One month of sales read in both currencies.
    '''
    month: str
    sales_bob: float
    sales_usd: float
    average_rate: float | None = Field(
        None, description = 'Bolivianos per dollar the month sold at, weighted by sales.'
    )


class FxTotals(BaseModel):
    '''
        The margin at what the merchandise cost against what replacing it
        costs today.
    '''
    revenue: float
    historical_cost: float
    replacement_cost: float
    historical_margin: float
    replacement_margin: float
    historical_margin_pct: float | None = None
    replacement_margin_pct: float | None = None


class CategoryFx(BaseModel):
    '''
        The same comparison for one category.
    '''
    category: str
    revenue: float
    usd_cost_share: float = Field(..., ge = 0, le = 1)
    historical_margin_pct: float | None = None
    replacement_margin_pct: float | None = None


class UncoveredProduct(BaseModel):
    '''
        A product whose last price no longer covers what replacing it costs.
    '''
    product_id: str
    product_name: str | None = None
    category: str | None = None
    last_price: float
    last_cost: float
    replacement_cost: float
    gap: float = Field(..., description = 'Last price minus replacement cost; negative.')


class PurchasingPower(BaseModel):
    '''
        What the period's sales buy in dollars at each day's rate and at
        today's.
    '''
    usd_at_own_day: float
    usd_at_today: float
    difference: float
    difference_pct: float | None = None


class FxEffectBlock(BaseModel):
    '''
        The three questions of the view: did I really grow, does my price
        cover replacing, how much merchandise does what I sold buy.
    '''
    rate_today: float
    rate_is_hypothetical: bool = False
    monthly: list[MonthlyFx] = Field(default_factory = list)
    growth_bob_pct: float | None = None
    growth_usd_pct: float | None = None
    totals: FxTotals | None = Field(
        None, description = 'Absent when the file carries no unit cost.'
    )
    by_category: list[CategoryFx] = Field(default_factory = list)
    uncovered: list[UncoveredProduct] = Field(default_factory = list)
    uncovered_count: int = 0
    purchasing_power: PurchasingPower | None = None


class FxEffectResponse(FxEffectBlock):
    '''
        GET /v1/analytics/fx-effect/{dataset_id}.
    '''
    dataset_id: str
    source: str = Field(..., description = 'The dollar used: USD (official) or USDT.')
    period: PeriodInfo = PeriodInfo()
