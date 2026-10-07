'''
    The exchange-rate effect, for a distributor that buys in dollars and sells
    in bolivianos.

    Three questions, all from the sales file and the rate series:

        * Did I really grow? Sales by month in bolivianos and in dollars at the
          rate of each day: rising in Bs and falling in USD is devaluation,
          not growth.
        * Does my price cover replacing? The cost of each sale is taken in
          dollars at the rate of its day and brought to today's rate: the
          replacement cost. A product whose last price is below it loses money
          on every unit it restocks.
        * How much merchandise does what I sold buy? The same bolivianos at
          each day's rate and at today's.

    The share of the cost bought in dollars is the account's policy, by
    category: a category bought locally keeps its historical cost. The file
    has no purchase date, so the rate of the sale's day stands in for the rate
    the merchandise was bought at.
'''

import pandas as pd

from schemas.fx_effect import (
    CategoryFx,
    FxEffectBlock,
    FxTotals,
    MonthlyFx,
    PurchasingPower,
    UncoveredProduct
)
from schemas.objectives import CommercialPolicySchema
from services.analytics_utils import (
    AMOUNT,
    CATEGORY,
    COST,
    DATE,
    PRICE,
    PRODUCT_ID,
    PRODUCT_NAME,
    QUANTITY,
    money,
    ratio
)
from services.environment import load_and_validate_env_vars
from services.logger_config import custom_logger as logger
from services.margin import has_cost_data

_SETTINGS = load_and_validate_env_vars({'FX_UNCOVERED_ROWS': int})
UNCOVERED_ROWS = _SETTINGS['FX_UNCOVERED_ROWS']
_PERCENT = 100.0
_NO_CATEGORY = 'SIN_CATEGORIA'


def _percent(
    numerator: float,
    denominator: float
) -> float | None:
    '''
        A percentage with two decimals, or None over nothing.

        Args:
            numerator (float): Part.
            denominator (float): Whole.

        Returns:
            float | None: The percentage.
    '''
    return round(ratio(numerator, denominator) * _PERCENT, 2) if denominator else None


def _monthly(frame: pd.DataFrame) -> list[MonthlyFx]:
    '''
        Sales by month in both currencies.

        Args:
            frame (pd.DataFrame): Rows with `month`, `total_amount` and `usd`.

        Returns:
            list[MonthlyFx]: One row per month, oldest first.
    '''
    grouped = frame.groupby('month', as_index = False)[[AMOUNT, 'usd']].sum()
    return [MonthlyFx(month = row['month'], sales_bob = money(row[AMOUNT]),
                      sales_usd = money(row['usd']),
                      average_rate = round(ratio(row[AMOUNT], row['usd']), 4)
                      if row['usd'] else None)
            for _, row in grouped.sort_values('month').iterrows()]


def _growth(monthly: list[MonthlyFx]) -> tuple:
    '''
        First month against last, in each currency.

        Args:
            monthly (list[MonthlyFx]): The series.

        Returns:
            tuple: Growth in bolivianos and in dollars, percent; None with
                fewer than two months.
    '''
    if len(monthly) < 2:
        return None, None
    first, last = monthly[0], monthly[-1]
    return (_percent(last.sales_bob - first.sales_bob, first.sales_bob),
            _percent(last.sales_usd - first.sales_usd, first.sales_usd))


def _shares(
    frame: pd.DataFrame,
    policy: CommercialPolicySchema
) -> pd.Series:
    '''
        The dollar share of the cost of each row, from its category.

        Args:
            frame (pd.DataFrame): Rows with `category`.
            policy (CommercialPolicySchema): The account's shares.

        Returns:
            pd.Series: Share per row, 0 to 1.
    '''
    by_category: dict[str, float] = policy.usd_cost_share_by_category or {}
    default = policy.usd_cost_share if policy.usd_cost_share is not None else 1.0
    return frame[CATEGORY].map(lambda category: by_category.get(category, default))


def _costs(
    frame: pd.DataFrame,
    rate_today: float
) -> pd.DataFrame:
    '''
        Historical and replacement cost of each row.

        Args:
            frame (pd.DataFrame): Rows with cost, quantity, rate and share.
            rate_today (float): Bolivianos per dollar now.

        Returns:
            pd.DataFrame: The rows with `historical` and `replacement`.
    '''
    historical = frame[COST] * frame[QUANTITY]
    in_dollars = historical * frame['share'] / frame['rate']
    replacement = in_dollars * rate_today + historical * (1 - frame['share'])
    return frame.assign(historical = historical,
                        replacement = replacement.where(frame['rate'].notna(), historical))


def _totals(frame: pd.DataFrame) -> FxTotals:
    '''
        Margin at historical cost against margin at replacement cost.

        Args:
            frame (pd.DataFrame): Rows with `historical` and `replacement`.

        Returns:
            FxTotals: The comparison.
    '''
    revenue = float(frame[AMOUNT].sum())
    historical = float(frame['historical'].sum())
    replacement = float(frame['replacement'].sum())
    return FxTotals(
        revenue = money(revenue), historical_cost = money(historical),
        replacement_cost = money(replacement),
        historical_margin = money(revenue - historical),
        replacement_margin = money(revenue - replacement),
        historical_margin_pct = _percent(revenue - historical, revenue),
        replacement_margin_pct = _percent(revenue - replacement, revenue)
    )


def _by_category(frame: pd.DataFrame) -> list[CategoryFx]:
    '''
        The comparison by category, the largest first.

        Args:
            frame (pd.DataFrame): Rows with costs and share.

        Returns:
            list[CategoryFx]: One row per category.
    '''
    grouped = frame.groupby(CATEGORY, as_index = False).agg(
        revenue = (AMOUNT, 'sum'), historical = ('historical', 'sum'),
        replacement = ('replacement', 'sum'), share = ('share', 'first')
    ).sort_values('revenue', ascending = False)
    return [CategoryFx(
        category = str(row[CATEGORY]), revenue = money(row['revenue']),
        usd_cost_share = float(row['share']),
        historical_margin_pct = _percent(row['revenue'] - row['historical'], row['revenue']),
        replacement_margin_pct = _percent(row['revenue'] - row['replacement'], row['revenue'])
    ) for _, row in grouped.iterrows()]


def _uncovered(frame: pd.DataFrame) -> list[UncoveredProduct]:
    '''
        The products whose last price is below what replacing one unit costs,
        the widest gap first.

        Args:
            frame (pd.DataFrame): Rows with costs, sorted by date.

        Returns:
            list[UncoveredProduct]: Every product in that situation.
    '''
    last = frame.sort_values(DATE).groupby(PRODUCT_ID, as_index = False).last()
    unit_replacement = last['replacement'] / last[QUANTITY]
    gap = last[PRICE] - unit_replacement
    rows = last.assign(unit_replacement = unit_replacement, gap = gap)
    rows = rows[rows['gap'] < 0].sort_values('gap')
    return [UncoveredProduct(
        product_id = str(row[PRODUCT_ID]),
        product_name = str(row[PRODUCT_NAME]) if PRODUCT_NAME in rows else None,
        category = str(row[CATEGORY]), last_price = money(row[PRICE]),
        last_cost = money(row[COST]), replacement_cost = money(row['unit_replacement']),
        gap = money(row['gap'])
    ) for _, row in rows.iterrows()]


def _purchasing_power(
    frame: pd.DataFrame,
    rate_today: float
) -> PurchasingPower:
    '''
        The period's sales in dollars at each day's rate and at today's.

        Args:
            frame (pd.DataFrame): Rows with `total_amount` and `usd`.
            rate_today (float): Bolivianos per dollar now.

        Returns:
            PurchasingPower: Both readings and the difference.
    '''
    own_day = float(frame['usd'].sum())
    today = float(frame[AMOUNT].sum()) / rate_today
    return PurchasingPower(usd_at_own_day = money(own_day), usd_at_today = money(today),
                           difference = money(today - own_day),
                           difference_pct = _percent(today - own_day, own_day))


def build_fx_effect(
    sales: pd.DataFrame,
    rates: pd.Series,
    rate_today: float,
    policy: CommercialPolicySchema
) -> FxEffectBlock:
    '''
        The exchange-rate effect over the sales of a window.

        Args:
            sales (pd.DataFrame): Normalized sales rows, in bolivianos.
            rates (pd.Series): Rate of each row's own day, aligned to `sales`;
                empty where there is none.
            rate_today (float): Bolivianos per dollar now, or the hypothetical
                one the user asked to simulate.
            policy (CommercialPolicySchema): The dollar share of the cost.

        Returns:
            FxEffectBlock: Growth, margins, uncovered products and purchasing
                power. Margins are absent when the file carries no unit cost.
    '''
    frame = sales.reset_index(drop = True).assign(rate = rates.reset_index(drop = True))
    frame[CATEGORY] = frame.get(CATEGORY, pd.Series(dtype = object)).fillna(_NO_CATEGORY)
    frame['month'] = pd.to_datetime(frame[DATE]).dt.strftime('%Y-%m')
    frame['usd'] = (frame[AMOUNT] / frame['rate']).where(frame['rate'].notna(), 0.0)

    monthly = _monthly(frame)
    growth_bob, growth_usd = _growth(monthly)
    block = FxEffectBlock(rate_today = rate_today, monthly = monthly,
                          growth_bob_pct = growth_bob, growth_usd_pct = growth_usd,
                          purchasing_power = _purchasing_power(frame, rate_today))

    if has_cost_data(frame):
        costed = _costs(frame[frame[COST] > 0].assign(share = _shares(frame, policy)),
                        rate_today)
        uncovered = _uncovered(costed)
        block.totals = _totals(costed)
        block.by_category = _by_category(costed)
        block.uncovered = uncovered[:UNCOVERED_ROWS]
        block.uncovered_count = len(uncovered)

    message = (f'FX effect over {len(frame)} row(s) at today\'s rate {rate_today}: '
               f'{block.uncovered_count} product(s) below replacement cost.')
    logger.info(message)
    return block
