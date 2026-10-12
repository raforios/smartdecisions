'''
    Tests for what the exchange rate took from the credit (Rafael, rule 8):
    the balance in bolivianos never moves; the dollars measure the
    devaluation from the day of the credit to the day of the payment, and to
    today for what is still open.
'''
import pandas as pd

from services import currency
from services.receivables_fx import build_credit_devaluation

TODAY = '2026-10-10'

# The dollar went from 10 in August to 12.5 in September; today it is at 16.
SERIES = {
    'USD': [{'date': '2026-08-01', 'rate': 10.0}, {'date': '2026-09-01', 'rate': 12.5},
            {'date': '2026-10-05', 'rate': 16.0}],
    'USDT': [{'date': '2026-08-01', 'rate': 8.0}],
}


def _sales() -> pd.DataFrame:
    '''
        Two credit invoices of August and one cash sale.

        Returns:
            pd.DataFrame: Normalized sales rows.
    '''
    rows = [('A', '2026-08-05', 100.0, 'CREDITO'), ('B', '2026-08-10', 50.0, 'CREDITO'),
            ('C', '2026-08-12', 30.0, 'CONTADO')]
    return pd.DataFrame([{'order_id': order, 'pos_id': 'X', 'pos_name': 'X',
                          'date': pd.Timestamp(day), 'total_amount': amount,
                          'payment_terms': terms} for order, day, amount, terms in rows])


def _payments() -> pd.DataFrame:
    '''
        A paid whole in September; B paid in part.

        Returns:
            pd.DataFrame: Normalized payment rows.
    '''
    return pd.DataFrame({'order_id': ['A', 'B'],
                         'payment_date': ['2026-09-02', '2026-09-03'],
                         'paid_amount': [100.0, 20.0]})


def test_what_was_collected_lost_the_devaluation_between_credit_and_payment(monkeypatch):
    '''120 Bs were 12 USD when given and 9.60 USD when they came back.'''
    monkeypatch.setattr(currency, '_fetch_rates', lambda code, *args: SERIES[code])

    fx = build_credit_devaluation(_sales(), _payments(), 'Bearer t', TODAY)

    assert (fx.credit.bob, fx.credit.usd) == (150.0, 15.0)
    assert (fx.collected_at_credit.bob, fx.collected_at_credit.usd) == (120.0, 12.0)
    assert (fx.collected_at_payment.bob, fx.collected_at_payment.usd) == (120.0, 9.6)
    assert fx.collected_lost.usd == -2.4
    assert fx.collected_lost.bob == 0.0


def test_what_is_still_open_is_measured_against_today(monkeypatch):
    '''The 30 Bs B still owes were 3 USD at the credit and are 1.88 today.'''
    monkeypatch.setattr(currency, '_fetch_rates', lambda code, *args: SERIES[code])

    fx = build_credit_devaluation(_sales(), _payments(), 'Bearer t', TODAY)

    assert (fx.open_at_credit.bob, fx.open_at_credit.usd) == (30.0, 3.0)
    assert (fx.open_today.bob, fx.open_today.usd) == (30.0, 1.88)
    assert fx.open_lost.usd == -1.12


def test_a_dataset_without_credit_has_no_devaluation():
    '''Only cash sales: there is no credit for the rate to erode.'''
    cash = _sales().assign(payment_terms = 'CONTADO')

    assert build_credit_devaluation(cash, None, 'Bearer t', TODAY) is None
