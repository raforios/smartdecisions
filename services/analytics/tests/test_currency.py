'''
    Tests for reading a report in another currency.

    The rule they defend: every amount converts at the rate of ITS OWN row's
    day. Converting a whole year at one rate turns a devaluation into growth,
    and that is the failure this module exists to prevent.
'''
from unittest.mock import patch

import pandas as pd
import pytest

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


def _payments() -> pd.DataFrame:
    '''
        Two payments of the same dollars, months apart, with one quantity
        that is not money.

        Returns:
            pd.DataFrame: The collections frame, as INGEST normalizes it.
    '''
    return pd.DataFrame([
        {'order_id': 'F-1', 'payment_date': '2026-07-15', 'paid_amount': 696.0},
        {'order_id': 'F-2', 'payment_date': '2026-09-15', 'paid_amount': 740.0},
    ])


def test_a_payment_converts_at_the_rate_of_its_invoice_day():
    '''
        A payment settles part of an invoice, so it converts at the rate the
        invoice converted at. At the rate of the day it was paid, an invoice
        paid in full in bolivianos stayed open in dollars, and the count of
        debtors moved with the currency.
    '''
    invoice_days = pd.Series({'F-1': '2026-07-15', 'F-2': '2026-07-20'})
    with patch.object(currency, '_fetch_rates', lambda *args: PUBLISHED):
        converted = currency.convert_payments(_payments(), 'USD', 'Bearer t', invoice_days)

    # F-2 was paid in September, but its invoice is from July: 6.96.
    assert [round(value, 2) for value in converted['paid_amount']] == [100.0, 106.32]
    assert list(converted['order_id']) == ['F-1', 'F-2']


def test_a_payment_without_its_invoice_converts_at_the_day_it_was_paid():
    '''An invoice outside the sales read leaves its payment's own day.'''
    with patch.object(currency, '_fetch_rates', lambda *args: PUBLISHED):
        converted = currency.convert_payments(_payments(), 'USD', 'Bearer t',
                                              pd.Series(dtype = str))

    assert [round(value, 2) for value in converted['paid_amount']] == [100.0, 100.0]


def test_payments_in_the_base_currency_are_untouched():
    '''Asking for bolivianos converts nothing, and no payments is no payments.'''
    no_invoices = pd.Series(dtype = str)
    assert currency.convert_payments(_payments(), currency.BASE_CURRENCY, 'Bearer t',
                                     no_invoices).equals(_payments())
    assert currency.convert_payments(None, 'USD', 'Bearer t', no_invoices) is None


def test_a_stock_snapshot_is_valued_at_todays_rate():
    '''
        The inventory in dollars answered the same figures as in bolivianos
        while saying "USD". The photo is what the stock is worth today, so it
        converts at today's rate; units are not money.
    '''
    snapshot = pd.DataFrame([{'product_id': 'P1', 'on_hand': 3.0, 'unit_cost': 74.0}])
    with patch.object(currency, '_fetch_rates', lambda *args: PUBLISHED):
        converted = currency.convert_snapshot(snapshot, 'USD', 'Bearer t', '2026-09-20')

    assert round(float(converted['unit_cost'].iloc[0]), 2) == 10.0
    assert float(converted['on_hand'].iloc[0]) == 3.0
