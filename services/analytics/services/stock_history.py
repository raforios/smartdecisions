'''
    The inventory over time: every photo INGEST keeps, valued at cost and at
    its sale price. A photo is history (rule 5): its dollars are those of its
    own day, and the same bolivianos at today's rate go next to them. On the
    latest photo that comparison is the price check — what the price list was
    worth in dollars the day it was loaded against what it is worth now.
'''
import pandas as pd

from schemas.analytics import ReferenceRates
from schemas.stock import StockPhoto
from services.analytics_utils import AMOUNT_DECIMALS
from services.currency import (
    PARALLEL_CURRENCY, PARALLEL_FALLBACK_CURRENCY, money_at, rates_per_row
)
from services.stock import ON_HAND, SNAPSHOT_DATE, UNIT_COST

UNIT_PRICE = 'unit_price'
_DATE = 'date'


def _value(
    photo: pd.DataFrame,
    column: str
) -> float | None:
    '''
        Units on hand times a unit amount, when the photo carries it.

        Args:
            photo (pd.DataFrame): The rows of one photo.
            column (str): The unit cost or the unit price.

        Returns:
            float | None: Bolivianos, or None without that column.
    '''
    if column not in photo.columns:
        return None
    amounts = pd.to_numeric(photo[column], errors = 'coerce')
    if amounts.isna().all():
        return None
    return float((pd.to_numeric(photo[ON_HAND], errors = 'coerce') * amounts).sum())


def _photo(
    photo: pd.DataFrame,
    day: pd.Timestamp,
    then: ReferenceRates,
    today_rates: ReferenceRates
) -> StockPhoto:
    '''
        One photo with its values: at its own day's rate and, at price, today.

        Args:
            photo (pd.DataFrame): The rows of that photo.
            day (pd.Timestamp): Its date.
            then (ReferenceRates): The rates of its day.
            today_rates (ReferenceRates): Today's rates.

        Returns:
            StockPhoto: The photo.
    '''
    at_cost, at_price = _value(photo, UNIT_COST), _value(photo, UNIT_PRICE)
    units = pd.to_numeric(photo[ON_HAND], errors = 'coerce').fillna(0)
    return StockPhoto(
        date = pd.Timestamp(day).date().isoformat(),
        products = int(photo['product_id'].nunique()),
        units_on_hand = round(float(units.sum()), AMOUNT_DECIMALS),
        out_of_stock = int((units <= 0).sum()),
        value_at_cost = money_at(at_cost, then) if at_cost is not None else None,
        value_at_price = money_at(at_price, then) if at_price is not None else None,
        value_at_price_today = money_at(at_price, today_rates) if at_price is not None else None
    )


def build_stock_history(
    stock: pd.DataFrame,
    auth_token: str,
    today_rates: ReferenceRates
) -> list[StockPhoto]:
    '''
        One row per stored photo, oldest first.

        Args:
            stock (pd.DataFrame): Every stored photo, normalized.
            auth_token (str): The caller's Authorization header, for QUOTES.
            today_rates (ReferenceRates): Today's official dollar and USDT.

        Returns:
            list[StockPhoto]: The photos with their values.
    '''
    frame = stock.assign(**{SNAPSHOT_DATE: pd.to_datetime(stock[SNAPSHOT_DATE],
                                                          errors = 'coerce')})
    days = sorted(frame[SNAPSHOT_DATE].dropna().unique())
    if not days:
        return []
    dated = pd.DataFrame({_DATE: days})
    usd, _ = rates_per_row(dated, PARALLEL_FALLBACK_CURRENCY, auth_token)
    usdt, _ = rates_per_row(dated, PARALLEL_CURRENCY, auth_token)
    return [
        _photo(frame.loc[frame[SNAPSHOT_DATE] == day], day,
               ReferenceRates(usd = float(day_usd), usdt = float(day_usdt)), today_rates)
        for day, day_usd, day_usdt in zip(days, usd, usdt)
    ]
