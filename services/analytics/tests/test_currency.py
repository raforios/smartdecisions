'''
    Tests for reading a report in another currency.

    The rule they defend: every amount converts at the rate of ITS OWN row's
    day. Converting a whole year at one rate turns a devaluation into growth,
    and that is the failure this module exists to prevent.
'''
from unittest.mock import patch

import pandas as pd
import pytest

from schemas.receivables import ReceivablesResponse
from services import currency
from services.exceptions import ServiceUnavailableError

# The float began in June and the rate moved: 6.96 in July, 7.40 in September.
# The exact shape QUOTES answers (`ExchangeRatePoint`). The fixture used to
# say `official_rate`, the code read the same wrong name, and every report in
# dollars answered 500 in production while this suite stayed green.
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


def test_each_row_converts_at_the_rate_of_its_own_day():
    '''
        The point of the whole module.

        Two sales of a different number of bolivianos are the SAME hundred
        dollars once each is read at the rate of its month. Converting both at
        September's rate would show the July sale as smaller than it was.
    '''
    with patch.object(currency, '_fetch_rates', lambda *args: PUBLISHED):
        converted, applied = currency.convert_frame(_sales(), 'USD', 'Bearer t')

    assert [round(value, 2) for value in converted['total_amount']] == [100.0, 100.0]
    assert [round(value, 2) for value in converted['unit_price']] == [10.0, 10.0]
    assert applied['rows_converted'] == 2
    assert applied['rows_without_rate'] == 0


def test_a_quantity_is_not_money():
    '''
        A rate applies to an amount, never to a count. Converting a quantity
        would be silent nonsense, so the money columns are named explicitly.
    '''
    with patch.object(currency, '_fetch_rates', lambda *args: PUBLISHED):
        converted, _ = currency.convert_frame(_sales(), 'USD', 'Bearer t')

    assert list(converted['quantity']) == [10, 10]


def test_the_rate_of_a_day_without_publication_is_the_last_one_before_it():
    '''
        The BCB does not publish every day, so a sale of a Sunday settles at
        Friday's figure — and the report has to convert it with that one.
    '''
    frame = pd.DataFrame([{'date': '2026-08-20', 'total_amount': 696.0}])

    with patch.object(currency, '_fetch_rates', lambda *args: PUBLISHED):
        converted, _ = currency.convert_frame(frame, 'USD', 'Bearer t')

    # August has no publication of its own: July's rate is still in force.
    assert round(converted['total_amount'].iloc[0], 2) == 100.0


def test_a_row_of_the_fixed_regime_converts_at_the_fixed_rate():
    '''
        The series starts when the boliviano floated. A sale of January was
        paid at the fixed rate, which QUOTES reports for that day: Andina's
        whole 2025 file read as zero dollars before this, because every row
        fell before the first published rate.
    '''
    frame = pd.DataFrame([
        {'date': '2026-01-10', 'total_amount': 686.0},
        {'date': '2026-09-15', 'total_amount': 740.0},
    ])

    with patch.object(currency, '_fetch_rates', lambda *args: PUBLISHED), \
         patch.object(currency, '_fixed_rate_before', lambda *args: 6.86):
        converted, applied = currency.convert_frame(frame, 'USD', 'Bearer t')

    assert round(converted['total_amount'].iloc[0], 2) == 100.0
    assert applied['rows_at_fixed_rate'] == 1
    assert applied['rows_without_rate'] == 0


def test_a_row_with_no_rate_at_all_keeps_its_amount_and_is_reported():
    '''
        A real gap —no publication and not the fixed regime— is not invented:
        the row keeps its own amount and the answer says how many did. It used
        to become NaN, and a NaN sums as zero.
    '''
    frame = pd.DataFrame([
        {'date': '2026-07-01', 'total_amount': 686.0},
        {'date': '2026-09-15', 'total_amount': 740.0},
    ])
    later = [{'date': '2026-09-01', 'rate': 7.40}]

    with patch.object(currency, '_fetch_rates', lambda *args: later), \
         patch.object(currency, '_fixed_rate_before', lambda *args: None):
        converted, applied = currency.convert_frame(frame, 'USD', 'Bearer t')

    assert converted['total_amount'].iloc[0] == 686.0
    assert applied['rows_without_rate'] == 1
    assert applied['rows_converted'] == 1


def test_asking_for_the_base_currency_converts_nothing():
    '''
        The file is written in bolivianos: asking for them is asking for the
        file as it is, and the answer says nothing was applied.
    '''
    converted, applied = currency.convert_frame(_sales(), currency.BASE_CURRENCY, 'Bearer t')

    assert applied is None
    assert list(converted['total_amount']) == [696.0, 740.0]


def test_quotes_being_down_is_said_and_not_guessed():
    '''
        A report in dollars without rates is not a report with zeros: it is a
        report that cannot be produced, and it says so with a code.
    '''
    def _refuse(*args): # pylint: disable=unused-argument
        raise ServiceUnavailableError(detail = 'RATES_UNAVAILABLE')

    with patch.object(currency, '_fetch_rates', _refuse):
        with pytest.raises(ServiceUnavailableError):
            currency.convert_frame(_sales(), 'USD', 'Bearer t')


def test_in_usdt_the_days_before_the_series_read_at_the_official_rate():
    '''
        Case 10 of the FX spec. The USDT series starts the day it was
        connected, so earlier rows read at the official rate of their day —
        and the answer says how many, instead of passing them off as USDT.
    '''
    usdt = [{'date': '2026-09-10', 'rate': 7.50}]

    def _series(
        code: str,
        *_args: object
    ) -> list:
        '''The USDT series, or the official one.'''
        return usdt if code == currency.PARALLEL_CURRENCY else PUBLISHED

    with patch.object(currency, '_fetch_rates', _series):
        converted, applied = currency.convert_frame(_sales(), currency.PARALLEL_CURRENCY,
                                                    'Bearer t')

    assert [round(value, 2) for value in converted['total_amount']] == [100.0, 98.67]
    assert applied['rows_at_fallback'] == 1
    assert applied['fallback_currency'] == currency.PARALLEL_FALLBACK_CURRENCY
    assert applied['rows_without_rate'] == 0


def test_one_rate_divides_money_and_leaves_units():
    '''One rate for every amount: units, counts and shares do not move.'''
    snapshot = pd.DataFrame([{'product_id': 'P1', 'on_hand': 3.0, 'unit_cost': 74.0}])

    converted = currency.divide_money(snapshot, ('unit_cost',), 7.40)

    assert round(float(converted['unit_cost'].iloc[0]), 2) == 10.0
    assert float(converted['on_hand'].iloc[0]) == 3.0
    assert currency.divide_money(snapshot, ('unit_cost',), None).equals(snapshot)
    assert currency.divide_money(None, ('unit_cost',), 7.40) is None


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
