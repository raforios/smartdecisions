'''
    A month chosen on its own, set against today.

    The month reads at its close: that is its photo, and the past is never
    updated. Next to it goes the same figure at today's rate, so the manager
    sees what that month is worth now. Its days are history too, each at the
    rate of its own day; their dollars may not add up to the month's, and that
    is not adjusted.
'''
import pandas as pd

from schemas.analytics import ChosenMonth, DaySale, Money, ReferenceRates
from services.analytics_utils import AMOUNT_DECIMALS
from services.currency import (
    PARALLEL_CURRENCY, PARALLEL_FALLBACK_CURRENCY, USD_FACTOR, USDT_FACTOR,
    current_rate, money_at, rates_per_row
)

_DATE = 'date'
_AMOUNT = 'total_amount'


def _days(
    dataframe: pd.DataFrame,
    auth_token: str
) -> list[DaySale]:
    '''
        The sales of each day at the rate of that day.

        Args:
            dataframe (pd.DataFrame): The month's sales rows.
            auth_token (str): The caller's Authorization header, for QUOTES.

        Returns:
            list[DaySale]: One entry per day with sales, in date order.
    '''
    daily = dataframe.groupby(
        pd.to_datetime(dataframe[_DATE]).dt.normalize()
    )[_AMOUNT].sum().rename_axis(_DATE).reset_index()
    usd, _ = rates_per_row(daily, PARALLEL_FALLBACK_CURRENCY, auth_token)
    usdt, _ = rates_per_row(daily, PARALLEL_CURRENCY, auth_token)
    return [
        DaySale(date = day.date().isoformat(),
                amount = money_at(float(bob), ReferenceRates(usd = float(day_usd),
                                                           usdt = float(day_usdt))))
        for day, bob, day_usd, day_usdt in zip(daily[_DATE], daily[_AMOUNT], usd, usdt)
    ]


def build_chosen_month(
    dataframe: pd.DataFrame,
    auth_token: str,
    today: str
) -> ChosenMonth | None:
    '''
        The chosen month at its close, at today's rate and day by day.

        Args:
            dataframe (pd.DataFrame): Sales rows with the month-close factors
                of `with_month_close_factors`.
            auth_token (str): The caller's Authorization header, for QUOTES.
            today (str): Today, YYYY-MM-DD.

        Returns:
            ChosenMonth | None: None unless the rows are exactly one month.
    '''
    if dataframe.empty or USD_FACTOR not in dataframe.columns:
        return None
    months = pd.to_datetime(dataframe[_DATE]).dt.strftime('%Y-%m').unique()
    if len(months) != 1:
        return None

    close = ReferenceRates(usd = 1 / float(dataframe[USD_FACTOR].iloc[0]),
                           usdt = 1 / float(dataframe[USDT_FACTOR].iloc[0]))
    now = ReferenceRates(usd = current_rate(PARALLEL_FALLBACK_CURRENCY, auth_token, today),
                         usdt = current_rate(PARALLEL_CURRENCY, auth_token, today))
    bob = float(dataframe[_AMOUNT].sum())
    total = money_at(bob, close)
    total_today = money_at(bob, now)
    days = _days(dataframe, auth_token)
    return ChosenMonth(
        month = str(months[0]),
        close_rates = ReferenceRates(usd = round(close.usd, AMOUNT_DECIMALS),
                                     usdt = round(close.usdt, AMOUNT_DECIMALS)),
        today_rates = now,
        total = total,
        total_today = total_today,
        difference = Money(bob = 0.0,
                           usd = round(total_today.usd - total.usd, AMOUNT_DECIMALS),
                           usdt = round(total_today.usdt - total.usdt, AMOUNT_DECIMALS)),
        days = days,
        days_total = Money(
            bob = round(sum(day.amount.bob for day in days), AMOUNT_DECIMALS),
            usd = round(sum(day.amount.usd for day in days), AMOUNT_DECIMALS),
            usdt = round(sum(day.amount.usdt for day in days), AMOUNT_DECIMALS))
    )
