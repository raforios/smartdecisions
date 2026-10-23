'''
    What the merchandise costs (plan phase 6, rules 1, 2 and 7).

    Each purchase is recorded at the rate of its own day: a cost paid in
    dollars becomes bolivianos at that day's rate, and that is its history.
    Next to it goes what the same purchase costs today — the same dollars at
    today's rate; a purchase paid in bolivianos costs the same — and the
    difference, which is what says whether to adjust the price and the next
    order. The last purchase of each product is set against the previous ones.
'''
import pandas as pd

from schemas.analytics import Money, ReferenceRates
from schemas.purchases import PurchaseRow
from services.analytics_utils import AMOUNT_DECIMALS
from services.currency import (
    PARALLEL_CURRENCY, PARALLEL_FALLBACK_CURRENCY, money_at, rates_per_row
)

_DATE = 'purchase_date'
_PRODUCT = 'product_id'
_COST = 'unit_cost'
_CURRENCY = 'currency'
_PERCENT = 100.0


def with_costs_in_bolivianos(
    purchases: pd.DataFrame,
    auth_token: str,
    today: ReferenceRates
) -> pd.DataFrame:
    '''
        Every purchase with its unit cost in bolivianos at the rate of its
        day, the rates of that day, and the same cost at today's rate.

        Args:
            purchases (pd.DataFrame): Normalized purchase rows.
            auth_token (str): The caller's Authorization header, for QUOTES.
            today (ReferenceRates): Today's official dollar and USDT.

        Returns:
            pd.DataFrame: The rows with `cost_bob`, `day_usd`, `day_usdt`
                and `cost_today_bob`, oldest first.
    '''
    frame = purchases.assign(**{_DATE: pd.to_datetime(purchases[_DATE], errors = 'coerce')})
    frame = frame.dropna(subset = [_DATE]).sort_values(_DATE).reset_index(drop = True)
    days = pd.DataFrame({'date': frame[_DATE]})
    usd, _ = rates_per_row(days, PARALLEL_FALLBACK_CURRENCY, auth_token)
    usdt, _ = rates_per_row(days, PARALLEL_CURRENCY, auth_token)
    frame['day_usd'] = usd.to_numpy(dtype = float)
    frame['day_usdt'] = usdt.to_numpy(dtype = float)
    cost = pd.to_numeric(frame[_COST], errors = 'coerce')
    currency = frame[_CURRENCY].astype(str).str.upper()
    day_rate = currency.map({'BOB': 1.0}).fillna(
        frame['day_usd'].where(currency == 'USD', frame['day_usdt']))
    today_rate = currency.map({'BOB': 1.0, 'USD': today.usd, 'USDT': today.usdt})
    frame['cost_bob'] = cost * day_rate
    frame['cost_today_bob'] = cost * today_rate
    return frame


def _day_money(row: pd.Series) -> Money:
    '''
        A purchase's unit cost in the three currencies of its own day.

        Args:
            row (pd.Series): One purchase, with `cost_bob` and the day's rates.

        Returns:
            Money: The cost as it was recorded.
    '''
    return money_at(float(row['cost_bob']),
                    ReferenceRates(usd = float(row['day_usd']), usdt = float(row['day_usdt'])))


def _margin(
    price: float | None,
    cost: float
) -> float | None:
    '''
        The margin of a price over a cost, in percent.

        Args:
            price (float | None): Sale price, bolivianos.
            cost (float): Unit cost, bolivianos.

        Returns:
            float | None: Percent, or None without a price.
    '''
    if not price:
        return None
    return round((price - cost) / price * _PERCENT, 1)


def _row(
    history: pd.DataFrame,
    price: float | None,
    today: ReferenceRates
) -> PurchaseRow:
    '''
        One product: its last purchase against the previous ones and today.

        Args:
            history (pd.DataFrame): Its purchases, oldest first.
            price (float | None): Its latest sale price, bolivianos.
            today (ReferenceRates): Today's rates.

        Returns:
            PurchaseRow: The row.
    '''
    last = history.iloc[-1]
    earlier = history.iloc[:-1]
    previous = earlier.iloc[-1] if not earlier.empty else None
    last_cost = _day_money(last)
    cost_today = money_at(float(last['cost_today_bob']), today)
    average = None
    if not earlier.empty:
        averages = [_day_money(row) for _, row in earlier.iterrows()]
        average = Money(**{
            key: round(sum(getattr(money, key) for money in averages) / len(averages),
                       AMOUNT_DECIMALS)
            for key in ('bob', 'usd', 'usdt')})
    before = float(previous['cost_bob']) if previous is not None else None
    return PurchaseRow(
        product_id = str(last[_PRODUCT]),
        product_name = None if pd.isna(last.get('product_name')) else str(last['product_name']),
        supplier = str(last['supplier']),
        last_date = last[_DATE].date().isoformat(),
        currency = str(last[_CURRENCY]).upper(),
        quantity = float(last['quantity']),
        last_cost = last_cost,
        previous_cost = _day_money(previous) if previous is not None else None,
        change_vs_previous = round((last_cost.bob - before) / before * _PERCENT, 1)
        if before else None,
        average_previous_cost = average,
        cost_today = cost_today,
        difference_today = Money(
            bob = round(cost_today.bob - last_cost.bob, AMOUNT_DECIMALS),
            usd = round(cost_today.usd - last_cost.usd, AMOUNT_DECIMALS),
            usdt = round(cost_today.usdt - last_cost.usdt, AMOUNT_DECIMALS)),
        sale_price = price,
        margin_at_last_cost = _margin(price, last_cost.bob),
        margin_at_cost_today = _margin(price, cost_today.bob)
    )


def build_purchase_rows(
    costed: pd.DataFrame,
    prices: dict[str, float],
    today: ReferenceRates
) -> list[PurchaseRow]:
    '''
        One row per product, the largest exposure to today's rate first.

        Args:
            costed (pd.DataFrame): Purchases from `with_costs_in_bolivianos`.
            prices (dict[str, float]): Latest sale price per product.
            today (ReferenceRates): Today's rates.

        Returns:
            list[PurchaseRow]: The products.
    '''
    rows = [_row(history, prices.get(str(product)), today)
            for product, history in costed.groupby(_PRODUCT, sort = False)]
    return sorted(rows, key = lambda row: abs(row.difference_today.bob) * row.quantity,
                  reverse = True)


def last_month_amount(
    costed: pd.DataFrame,
    auth_token: str,
    today: str
) -> tuple[str, Money]:
    '''
        What was bought in the last month with purchases, at its close.

        Args:
            costed (pd.DataFrame): Purchases from `with_costs_in_bolivianos`.
            auth_token (str): The caller's Authorization header, for QUOTES.
            today (str): Today, YYYY-MM-DD: the close of a month in progress.

        Returns:
            tuple[str, Money]: The month and its amount.
    '''
    months = costed[_DATE].dt.strftime('%Y-%m')
    month = str(months.max())
    rows = costed.loc[months == month]
    close = min(pd.Period(month, freq = 'M').to_timestamp(how = 'end').normalize(),
                pd.Timestamp(today))
    day = pd.DataFrame({'date': [close]})
    usd, _ = rates_per_row(day, PARALLEL_FALLBACK_CURRENCY, auth_token)
    usdt, _ = rates_per_row(day, PARALLEL_CURRENCY, auth_token)
    bob = float((rows['cost_bob'] * pd.to_numeric(rows['quantity'], errors = 'coerce')).sum())
    return month, money_at(bob, ReferenceRates(usd = float(usd.iloc[0]),
                                                usdt = float(usdt.iloc[0])))


def latest_prices(
    sales: pd.DataFrame,
    stock: pd.DataFrame | None
) -> dict[str, float]:
    '''
        The latest sale price of each product: the latest stock photo's,
        and for a product without one, the price of its last sale.

        Args:
            sales (pd.DataFrame): Normalized sales rows.
            stock (pd.DataFrame | None): Every stored stock photo.

        Returns:
            dict[str, float]: Bolivianos per product.
    '''
    prices: dict[str, float] = {}
    if 'unit_price' in sales.columns and 'date' in sales.columns:
        ordered = sales.sort_values('date')
        prices.update(ordered.groupby(ordered[_PRODUCT].astype(str))['unit_price']
                      .last().dropna().astype(float).to_dict())
    if stock is not None and 'unit_price' in stock.columns and 'snapshot_date' in stock.columns:
        dates = pd.to_datetime(stock['snapshot_date'], errors = 'coerce')
        photo = stock.loc[dates == dates.max()]
        prices.update(photo.groupby(photo[_PRODUCT].astype(str))['unit_price']
                      .mean().dropna().astype(float).to_dict())
    return prices
