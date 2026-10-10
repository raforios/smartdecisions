'''
    Tests for reading a report in another currency.

    The rule they defend: every amount converts at the rate of ITS OWN row's
    day. Converting a whole year at one rate turns a devaluation into growth,
    and that is the failure this module exists to prevent.
'''
from unittest.mock import patch

import pandas as pd
import pytest

from schemas.analytics import Money
from schemas.receivables import ReceivablesResponse
from services import currency
from services.exceptions import ServiceUnavailableError

# The float began in June and the rate moved: 6.96 in July, 7.40 in September.
# The exact shape QUOTES answers (`ExchangeRatePoint`). The fixture used to
# say `official_rate`, the code read the same wrong name, and every report in
# dollars answered 500 in production while this suite stayed green.
# Every month in these tests is already closed.
TODAY = '2026-10-10'

PUBLISHED = [
    {'date': '2026-07-01', 'rate': 6.96},
    {'date': '2026-09-01', 'rate': 7.40},
]


def _sales() -> pd.DataFrame:
    '''
        Two sales of the same amount, months apart.

        Returns:
            pd.DataFrame: The frame.
    '''
    return pd.DataFrame([
        {'date': '2026-07-15', 'total_amount': 696.0, 'unit_price': 69.6, 'quantity': 10},
        {'date': '2026-09-15', 'total_amount': 740.0, 'unit_price': 74.0, 'quantity': 10},
    ])


def _factors(
    frame: pd.DataFrame,
    code: str = 'USD'
) -> list[float]:
    '''
        The rate each row was read at, recovered from its factor.

        Args:
            frame (pd.DataFrame): Rows returned by `with_day_factors`.
            code (str): 'USD' or the parallel currency.

        Returns:
            list[float]: Bolivianos per unit, None where there is no rate.
    '''
    column = currency.USD_FACTOR if code == 'USD' else currency.USDT_FACTOR
    return [None if pd.isna(value) else round(1 / value, 2) for value in frame[column]]


def test_each_sale_is_read_at_its_months_closing_rate():
    '''
        The point of the whole module.

        Two sales of a different number of bolivianos are the SAME hundred
        dollars once each is read at the close of its month. Reading both at
        September's rate would show the July sale as smaller than it was.
    '''
    with patch.object(currency, '_fetch_rates', lambda *args: PUBLISHED):
        read = currency.with_month_close_factors(_sales(), 'Bearer t', TODAY)

    dollars = read['total_amount'] * read[currency.USD_FACTOR]
    assert [round(value, 2) for value in dollars] == [100.0, 100.0]
    # The bolivianos and the units are never touched.
    assert list(read['total_amount']) == [696.0, 740.0]
    assert list(read['quantity']) == [10, 10]


def test_the_rate_of_a_day_without_publication_is_the_last_one_before_it():
    '''
        The BCB does not publish every day, so a sale of a Sunday settles at
        Friday's figure.
    '''
    frame = pd.DataFrame([{'date': '2026-08-20', 'total_amount': 696.0}])

    with patch.object(currency, '_fetch_rates', lambda *args: PUBLISHED):
        read = currency.with_month_close_factors(frame, 'Bearer t', TODAY)

    # August has no publication of its own: July's rate is still in force.
    assert _factors(read) == [6.96]


def test_a_row_of_the_fixed_regime_reads_at_the_fixed_rate():
    '''
        The series starts when the boliviano floated. A sale of January was
        paid at the fixed rate, which QUOTES reports for that day.
    '''
    frame = pd.DataFrame([
        {'date': '2026-01-10', 'total_amount': 686.0},
        {'date': '2026-09-15', 'total_amount': 740.0},
    ])

    with patch.object(currency, '_fetch_rates', lambda *args: PUBLISHED), \
         patch.object(currency, '_fixed_rate_before', lambda *args: 6.86):
        read = currency.with_month_close_factors(frame, 'Bearer t', TODAY)

    assert _factors(read) == [6.86, 7.40]


def test_a_row_with_no_rate_at_all_has_no_dollars():
    '''
        A real gap —no publication and not the fixed regime— is not invented:
        the row has no factor, so it adds no dollars.
    '''
    frame = pd.DataFrame([
        {'date': '2026-07-01', 'total_amount': 686.0},
        {'date': '2026-09-15', 'total_amount': 740.0},
    ])
    later = [{'date': '2026-09-01', 'rate': 7.40}]

    with patch.object(currency, '_fetch_rates', lambda *args: later), \
         patch.object(currency, '_fixed_rate_before', lambda *args: None):
        read = currency.with_month_close_factors(frame, 'Bearer t', TODAY)

    assert _factors(read) == [None, 7.40]


def test_an_empty_frame_needs_no_rates():
    '''Nothing to read: no call to QUOTES and the frame as it came.'''
    empty = _sales().iloc[0:0]

    assert currency.with_month_close_factors(empty, 'Bearer t', TODAY) is empty


def test_quotes_being_down_is_said_and_not_guessed():
    '''
        Sales in dollars without rates are not sales worth zero dollars: the
        report cannot be produced, and it says so with a code.
    '''
    def _refuse(*args): # pylint: disable=unused-argument
        raise ServiceUnavailableError(detail = 'RATES_UNAVAILABLE')

    with patch.object(currency, '_fetch_rates', _refuse):
        with pytest.raises(ServiceUnavailableError):
            currency.with_month_close_factors(_sales(), 'Bearer t', TODAY)


def test_in_usdt_the_days_before_the_series_read_at_the_official_rate():
    '''
        Case 10 of the FX spec. The USDT series starts the day it was
        connected, so earlier rows read at the official rate of their day.
    '''
    usdt = [{'date': '2026-09-10', 'rate': 7.50}]

    def _series(
        code: str,
        *_args: object
    ) -> list:
        '''The USDT series, or the official one.'''
        return usdt if code == currency.PARALLEL_CURRENCY else PUBLISHED

    with patch.object(currency, '_fetch_rates', _series):
        read = currency.with_month_close_factors(_sales(), 'Bearer t', TODAY)

    assert _factors(read, currency.PARALLEL_CURRENCY) == [6.96, 7.50]


def test_a_response_counted_in_bolivianos_carries_the_three_currencies(monkeypatch):
    '''
        8.000 bolivianos at 11,85 and 11,90 read 675,11 USD and 672,27 USDT;
        a count is not money and stays as it is.
    '''
    rates = {'USD': 11.85, 'USDT': 11.90}
    monkeypatch.setattr(currency, '_fetch_rates', lambda code, *args: [
        {'date': '2026-10-08', 'rate': rates[code]}
    ])

    response = currency.in_three_currencies(
        ReceivablesResponse,
        {'dataset_id': 'd', 'kpis': {'receivable_total': 8000.0, 'open_invoices': 3}},
        'Bearer t', '2026-10-08'
    )

    assert response.kpis.receivable_total.model_dump() == \
        {'bob': 8000.0, 'usd': 675.11, 'usdt': 672.27}
    assert response.kpis.open_invoices == 3
    assert response.rates.usdt == 11.90


def test_a_month_reads_at_its_last_day_and_the_open_month_at_today(monkeypatch):
    '''August closes at August 31; the month in progress, at today's rate.'''
    series = {'USD': [{'date': '2026-08-10', 'rate': 10.0}, {'date': '2026-08-31', 'rate': 12.5},
                      {'date': '2026-10-05', 'rate': 16.0}],
              'USDT': [{'date': '2026-08-01', 'rate': 8.0}]}
    monkeypatch.setattr(currency, '_fetch_rates', lambda code, *args: series[code])
    sales = pd.DataFrame({'date': pd.to_datetime(['2026-08-05', '2026-08-20', '2026-10-02']),
                          'total_amount': [100.0, 100.0, 100.0]})

    with_factors = currency.with_month_close_factors(sales, 'Bearer t', '2026-10-10')

    assert list(with_factors[currency.USD_FACTOR]) == [0.08, 0.08, 0.0625]
    assert list(with_factors[currency.USDT_FACTOR]) == [0.125, 0.125, 0.125]


def test_money_sums_groups_the_three_currencies_together():
    '''The dollars of a group are its rows' amounts times each row's factor.'''
    frame = pd.DataFrame({'client': ['A', 'A', 'B'], 'amount': [100.0, 200.0, 50.0],
                          currency.USD_FACTOR: [0.1, 0.05, 0.1],
                          currency.USDT_FACTOR: [0.1, 0.1, 0.1]})

    sums = currency.money_sums(frame, frame['amount'], 'client', by_month = True)

    assert sums.loc['A'].to_dict() == {'bob': 300.0, 'usd': 20.0, 'usdt': 30.0}
    assert list(currency.money_sums(frame[['client', 'amount']], frame['amount'],
                                    'client', by_month = True).columns) == ['bob']


def test_an_amount_is_money_only_when_its_dollars_are_known():
    '''Without dollars the bolivianos stay a plain number.'''
    assert currency.to_money(10.004) == 10.0
    assert currency.to_money(10.0, 1.234, None) == Money(bob = 10.0, usd = 1.23, usdt = None)
    assert currency.money_row(pd.Series({'bob': 5.0, 'usd': 0.5, 'usdt': 0.4})).usdt == 0.4


def test_money_total_sums_the_whole_frame():
    '''One group for every row; an empty frame is zero bolivianos.'''
    frame = pd.DataFrame({'amount': [1.0, 2.0], currency.USD_FACTOR: [1.0, 0.5],
                          currency.USDT_FACTOR: [1.0, 1.0]})

    assert currency.money_total(frame, frame['amount'], by_month = True).to_dict() == \
        {'bob': 3.0, 'usd': 2.0, 'usdt': 3.0}
    assert currency.money_total(frame.iloc[0:0], frame['amount'].iloc[0:0])['bob'] == 0.0


def test_the_sum_of_several_months_reads_at_todays_rate(monkeypatch):
    '''
        The general view says what the business has now: the bolivianos of
        several months are added first and read at today's rate, while each
        month on its own still reads at its close.
    '''
    series = {'USD': [{'date': '2026-08-31', 'rate': 12.5}, {'date': '2026-10-05', 'rate': 16.0}],
              'USDT': [{'date': '2026-08-01', 'rate': 8.0}]}
    monkeypatch.setattr(currency, '_fetch_rates', lambda code, *args: series[code])
    sales = pd.DataFrame({'date': pd.to_datetime(['2026-08-05', '2026-10-02']),
                          'total_amount': [100.0, 300.0]})

    read = currency.with_month_close_factors(sales, 'Bearer t', '2026-10-10')

    assert currency.money_total(read, read['total_amount']).to_dict() == \
        {'bob': 400.0, 'usd': 25.0, 'usdt': 50.0}
    by_month = currency.money_sums(read, read['total_amount'],
                                   read['date'].dt.strftime('%Y-%m'), by_month = True)
    assert by_month.loc['2026-08', 'usd'] == 8.0
    assert by_month.loc['2026-10', 'usd'] == 18.75


def test_a_single_month_asked_for_reads_whole_at_its_close(monkeypatch):
    '''Choosing August shows August as it was: every sum at August 31.'''
    series = {'USD': [{'date': '2026-08-31', 'rate': 12.5}, {'date': '2026-10-05', 'rate': 16.0}],
              'USDT': [{'date': '2026-08-01', 'rate': 8.0}]}
    monkeypatch.setattr(currency, '_fetch_rates', lambda code, *args: series[code])
    august = pd.DataFrame({'date': pd.to_datetime(['2026-08-05', '2026-08-20']),
                           'client': ['A', 'B'], 'total_amount': [100.0, 150.0]})

    read = currency.with_month_close_factors(august, 'Bearer t', '2026-10-10')

    assert currency.money_total(read, read['total_amount'])['usd'] == 20.0
    assert currency.money_sums(read, read['total_amount'], 'client').loc['B', 'usd'] == 12.0
