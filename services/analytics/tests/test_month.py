'''
    Tests for a month chosen on its own (Rafael, rules 6 and 9): the month at
    its close, the same at today's rate with the difference, and each day at
    its own day's rate without adjusting the sum.
'''
import pandas as pd

from services import currency
from services.month import build_chosen_month

TODAY = '2026-10-10'

# August moved from 10 to 12.5 inside the month; today the dollar is at 16.
SERIES = {
    'USD': [{'date': '2026-08-05', 'rate': 10.0}, {'date': '2026-08-20', 'rate': 12.5},
            {'date': '2026-10-05', 'rate': 16.0}],
    'USDT': [{'date': '2026-08-01', 'rate': 8.0}],
}


def _august(monkeypatch) -> pd.DataFrame:
    '''
        Two August sales with their month-close factors.

        Args:
            monkeypatch: Pytest fixture that replaces QUOTES.

        Returns:
            pd.DataFrame: The rows as the controller hands them over.
    '''
    monkeypatch.setattr(currency, '_fetch_rates', lambda code, *args: SERIES[code])
    sales = pd.DataFrame({'date': pd.to_datetime(['2026-08-05', '2026-08-20']),
                          'total_amount': [100.0, 150.0]})
    return currency.with_month_close_factors(sales, 'Bearer t', TODAY)


def test_the_month_reads_at_its_close_and_next_to_it_at_today(monkeypatch):
    '''August is its photo at August 31; the same bolivianos today are worth less.'''
    month = build_chosen_month(_august(monkeypatch), 'Bearer t', TODAY)

    assert month.month == '2026-08'
    assert (month.close_rates.usd, month.today_rates.usd) == (12.5, 16.0)
    assert (month.total.bob, month.total.usd) == (250.0, 20.0)
    assert (month.total_today.bob, month.total_today.usd) == (250.0, 15.62)
    assert month.difference.usd == -4.38
    assert month.difference.bob == 0.0


def test_each_day_keeps_its_own_rate_and_the_sum_is_not_adjusted(monkeypatch):
    '''The days add up in bolivianos; their dollars differ from the month's.'''
    month = build_chosen_month(_august(monkeypatch), 'Bearer t', TODAY)

    assert [(day.date, day.amount.usd) for day in month.days] == [
        ('2026-08-05', 10.0), ('2026-08-20', 12.0)]
    assert month.days_total.bob == month.total.bob
    assert month.days_total.usd == 22.0
    assert month.days_total.usd != month.total.usd


def test_more_than_one_month_has_no_chosen_month(monkeypatch):
    '''The general view is not a chosen month: nothing to set against today.'''
    monkeypatch.setattr(currency, '_fetch_rates', lambda code, *args: SERIES[code])
    sales = pd.DataFrame({'date': pd.to_datetime(['2026-08-05', '2026-09-20']),
                          'total_amount': [100.0, 150.0]})
    read = currency.with_month_close_factors(sales, 'Bearer t', TODAY)

    assert build_chosen_month(read, 'Bearer t', TODAY) is None
