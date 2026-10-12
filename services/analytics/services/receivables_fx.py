'''
    What the exchange rate took from the credit (Rafael, rule 8).

    A receivable does not change with the rate: it is owed in bolivianos and
    collected in bolivianos. The rate only measures the devaluation between
    the day the credit was given and the day it was collected; for what is
    still open, between that day and today. Nothing here touches a balance.
'''
import pandas as pd

from schemas.analytics import Money
from schemas.receivables import CreditDevaluation
from services.analytics_utils import AMOUNT_DECIMALS, DATE, ORDER
from services.currency import (
    PARALLEL_CURRENCY, PARALLEL_FALLBACK_CURRENCY, current_rate, rates_per_row
)
from services.receivables import CREDIT, PAID_AMOUNT, PAYMENT_DATE, TERMS, invoice_frame


def _dollars(
    bob: pd.Series,
    days: pd.Series,
    auth_token: str
) -> tuple[float, float]:
    '''
        The sum of `bob` with each amount at the rate of its own day.

        Args:
            bob (pd.Series): Amounts in bolivianos.
            days (pd.Series): The day of each amount, aligned with `bob`.
            auth_token (str): The caller's Authorization header, for QUOTES.

        Returns:
            tuple[float, float]: Official dollars and USDT.
    '''
    if bob.empty:
        return 0.0, 0.0
    frame = pd.DataFrame({DATE: days.to_numpy()})
    usd, _ = rates_per_row(frame, PARALLEL_FALLBACK_CURRENCY, auth_token)
    usdt, _ = rates_per_row(frame, PARALLEL_CURRENCY, auth_token)
    values = bob.to_numpy(dtype = float)
    return (float((values / usd.to_numpy(dtype = float)).sum()),
            float((values / usdt.to_numpy(dtype = float)).sum()))


def _money(
    bob: float,
    dollars: tuple[float, float]
) -> Money:
    '''
        Bolivianos with their dollars, rounded.

        Args:
            bob (float): Bolivianos.
            dollars (tuple[float, float]): Official dollars and USDT.

        Returns:
            Money: The three amounts.
    '''
    return Money(bob = round(bob, AMOUNT_DECIMALS), usd = round(dollars[0], AMOUNT_DECIMALS),
                 usdt = round(dollars[1], AMOUNT_DECIMALS))


def _lost(
    then: Money,
    now: Money
) -> Money:
    '''
        The dollars the same bolivianos lost between two readings.

        Args:
            then (Money): The earlier reading.
            now (Money): The later reading.

        Returns:
            Money: Zero bolivianos; the dollar difference (negative = lost).
    '''
    return Money(bob = 0.0, usd = round(now.usd - then.usd, AMOUNT_DECIMALS),
                 usdt = round(now.usdt - then.usdt, AMOUNT_DECIMALS))


def _dated_payments(
    collections: pd.DataFrame | None,
    credit: pd.DataFrame
) -> pd.DataFrame:
    '''
        The payments of credit invoices that say when they were made, with the
        day the credit was given.

        Args:
            collections (pd.DataFrame | None): Normalized payment rows.
            credit (pd.DataFrame): Credit invoices, with `date`.

        Returns:
            pd.DataFrame: The invoice, `paid`, `paid_on` and `given_on` per payment.
    '''
    columns = {ORDER, PAID_AMOUNT, PAYMENT_DATE}
    if collections is None or collections.empty or not columns <= set(collections.columns):
        return pd.DataFrame(columns = [ORDER, 'paid', 'paid_on', 'given_on'])
    payments = pd.DataFrame({
        ORDER: collections[ORDER],
        'paid': pd.to_numeric(collections[PAID_AMOUNT], errors = 'coerce'),
        'paid_on': pd.to_datetime(collections[PAYMENT_DATE], errors = 'coerce')
    }).merge(credit[[ORDER, DATE]].rename(columns = {DATE: 'given_on'}), on = ORDER)
    return payments.dropna(subset = ['paid', 'paid_on', 'given_on'])


def build_credit_devaluation(
    sales: pd.DataFrame,
    collections: pd.DataFrame | None,
    auth_token: str,
    today: str
) -> CreditDevaluation | None:
    '''
        The credit given, what was collected and what is still open, each in
        the dollars of the day that matters to it.

        Args:
            sales (pd.DataFrame): Normalized sales rows, in bolivianos.
            collections (pd.DataFrame | None): Normalized payment rows.
            auth_token (str): The caller's Authorization header, for QUOTES.
            today (str): Today, YYYY-MM-DD.

        Returns:
            CreditDevaluation | None: None when the dataset has no credit.
    '''
    invoices = invoice_frame(sales) if TERMS in sales.columns else None
    if invoices is None:
        return None
    credit = invoices.loc[invoices['terms'].astype(str).str.upper() == CREDIT]
    if credit.empty:
        return None

    payments = _dated_payments(collections, credit)
    paid = payments.groupby(ORDER)['paid'].sum()
    balance = (credit['amount'] - credit[ORDER].map(paid).fillna(0.0)).clip(lower = 0)

    collected_at_credit = _money(float(payments['paid'].sum()), _dollars(
        payments['paid'], payments['given_on'], auth_token))
    collected_at_payment = _money(float(payments['paid'].sum()), _dollars(
        payments['paid'], payments['paid_on'], auth_token))
    open_at_credit = _money(float(balance.sum()),
                            _dollars(balance, credit['date'], auth_token))
    rates = (current_rate(PARALLEL_FALLBACK_CURRENCY, auth_token, today),
             current_rate(PARALLEL_CURRENCY, auth_token, today))
    open_today = _money(float(balance.sum()),
                        (float(balance.sum()) / rates[0], float(balance.sum()) / rates[1]))
    return CreditDevaluation(
        credit = _money(float(credit['amount'].sum()),
                        _dollars(credit['amount'], credit['date'], auth_token)),
        collected_at_credit = collected_at_credit,
        collected_at_payment = collected_at_payment,
        collected_lost = _lost(collected_at_credit, collected_at_payment),
        open_at_credit = open_at_credit,
        open_today = open_today,
        open_lost = _lost(open_at_credit, open_today)
    )
