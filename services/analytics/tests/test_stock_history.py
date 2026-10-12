'''
    Tests for the inventory over time: each photo in the dollars of its own
    day (rule 5, the past is not updated) and, next to it, the same at today.
'''
import pandas as pd

from schemas.analytics import ReferenceRates
from services import currency
from services.stock_history import build_stock_history

SERIES = {
    'USD': [{'date': '2026-08-01', 'rate': 10.0}, {'date': '2026-09-01', 'rate': 12.5}],
    'USDT': [{'date': '2026-08-01', 'rate': 10.0}],
}


def _photos() -> pd.DataFrame:
    '''
        Two photos, August and September; one product ran out in September.

        Returns:
            pd.DataFrame: Normalized stock rows.
    '''
    return pd.DataFrame({
        'snapshot_date': ['2026-08-31', '2026-08-31', '2026-09-30', '2026-09-30'],
        'product_id': ['A', 'B', 'A', 'B'],
        'on_hand': [10.0, 5.0, 8.0, 0.0],
        'unit_cost': [6.0, 4.0, 6.0, 4.0],
        'unit_price': [10.0, 8.0, 10.0, 8.0],
    })


def test_each_photo_reads_in_the_dollars_of_its_own_day(monkeypatch):
    '''August's 140 Bs at price were 14 USD then; September's 80 Bs, 6.40 USD.'''
    monkeypatch.setattr(currency, '_fetch_rates', lambda code, *args: SERIES[code])

    photos = build_stock_history(_photos(), 'Bearer t', ReferenceRates(usd = 16.0, usdt = 16.0))

    assert [photo.date for photo in photos] == ['2026-08-31', '2026-09-30']
    assert (photos[0].value_at_price.bob, photos[0].value_at_price.usd) == (140.0, 14.0)
    assert (photos[1].value_at_price.bob, photos[1].value_at_price.usd) == (80.0, 6.4)
    assert photos[0].value_at_cost.bob == 80.0
    assert photos[1].out_of_stock == 1


def test_next_to_each_photo_goes_the_same_at_today(monkeypatch):
    '''The price list of September, 80 Bs, is 5 USD at today's 16.'''
    monkeypatch.setattr(currency, '_fetch_rates', lambda code, *args: SERIES[code])

    photos = build_stock_history(_photos(), 'Bearer t', ReferenceRates(usd = 16.0, usdt = 16.0))

    assert photos[-1].value_at_price_today.usd == 5.0
    assert photos[-1].value_at_price_today.bob == photos[-1].value_at_price.bob


def test_a_photo_without_prices_has_no_price_value(monkeypatch):
    '''An old photo loaded before the price was required is still counted.'''
    monkeypatch.setattr(currency, '_fetch_rates', lambda code, *args: SERIES[code])

    photos = build_stock_history(_photos().drop(columns = ['unit_price']), 'Bearer t',
                                 ReferenceRates(usd = 16.0, usdt = 16.0))

    assert photos[0].value_at_price is None
    assert photos[0].units_on_hand == 15.0
