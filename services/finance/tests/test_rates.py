'''
    Tests for the rates the report shows its figures with, asked to QUOTES.

    What they defend: every period is read at the rate of its own close, a
    day before the float takes the fixed rate QUOTES reports, a rate that
    does not exist stays empty, and a QUOTES that cannot answer never stops
    the report.
'''
from datetime import date
from unittest.mock import Mock, patch

import requests

from schemas.report import ReportError
from services import rates

TODAY = date(2026, 10, 17)
SERIES = {
    'USD': [{'date': '2026-06-27', 'rate': 9.73}, {'date': '2026-09-30', 'rate': 11.62}],
    'USDT': [{'date': '2026-06-27', 'rate': 10.10}, {'date': '2026-10-16', 'rate': 11.81}],
}


def _quotes(
    url: str,
    params: dict,
    **_
) -> Mock:
    '''
        QUOTES as the service answers: the series, or the rate of one day.

        Returns:
            Mock: The response.
    '''
    if url.endswith('/at'):
        fixed = params['currency'] == 'USD'
        payload = {'rate': 6.86, 'regime': 'FIXED'} if fixed else {}
        return Mock(ok = fixed, status_code = 200 if fixed else 404, json = lambda: payload)
    return Mock(ok = True, status_code = 200,
                json = lambda: {'rates': SERIES[params['currency']]})


def test_a_period_closes_on_its_last_day_or_today():
    '''September closes on the 30th; the open October and 2026 close today.'''
    assert rates.period_close('2026-09', TODAY) == date(2026, 9, 30)
    assert rates.period_close('2026-10', TODAY) == TODAY
    assert rates.period_close('2026', TODAY) == TODAY
    assert rates.period_close('2025', TODAY) == date(2025, 12, 31)


def test_each_period_is_read_at_its_own_rate():
    '''The float months take the series; a year before it, the fixed rate.'''
    with patch.object(rates.requests, 'get', _quotes):
        found, notices = rates.period_rates(['2026-09', '2026-10', '2025'], TODAY, 'Bearer x')
    assert not notices
    assert (found['2026-09'].usd, found['2026-09'].usdt) == (11.62, 10.10)
    assert (found['2026-10'].usd, found['2026-10'].usdt) == (11.62, 11.81)
    # Before the float: the dollar was fixed; USDT had no series, and stays empty.
    assert (found['2025'].usd, found['2025'].usdt) == (6.86, None)


def test_quotes_down_never_stops_the_report():
    '''No rates and a notice; the bolivianos are still there.'''
    def _down(
        *_,
        **__
    ):
        raise requests.exceptions.ConnectionError('down')
    with patch.object(rates.requests, 'get', _down):
        found, notices = rates.period_rates(['2026-09'], TODAY, 'Bearer x')
    assert (found, notices) == ({}, [ReportError.RATES_UNAVAILABLE])
