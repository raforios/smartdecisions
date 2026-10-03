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


def test_a_row_before_the_first_published_rate_is_left_alone_and_reported():
    '''
        Converting at a figure nobody published would be inventing one. The
        row keeps its amount and the answer says how many did, which is the
        difference between a gap and a silent lie.
    '''
    frame = pd.DataFrame([
        {'date': '2026-01-10', 'total_amount': 686.0},
        {'date': '2026-09-15', 'total_amount': 740.0},
    ])

    with patch.object(currency, '_fetch_rates', lambda *args: PUBLISHED):
        converted, applied = currency.convert_frame(frame, 'USD', 'Bearer t')

    assert pd.isna(converted['total_amount'].iloc[0])
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
