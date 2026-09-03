'''
    Shared test fixtures: an in-memory stand-in for the DynamoDB table, so the
    suite never touches the table configured in .env.

    Both the domain tests and the controller tests need the same store, and the
    fake reader is the piece that must not drift between them: a query that
    filters differently here than in production would make the suite agree with
    itself and disagree with AWS.
'''
from datetime import date, timedelta

import pytest

from models.quotes import USD, ExchangeRateItem
from services import bcb_source, quotes


# First day of the float regime; the series every fixture builds starts here
# because that is where a projection is allowed to begin.
FLOAT_START = date(2026, 6, 27)


def build_history(days: int, start_rate: float = 9.73,
                  step: float = 0.04) -> list[ExchangeRateItem]:
    '''
        Builds a rate history that climbs steadily, like the float regime did.

        Args:
            days (int): How many days to build.
            start_rate (float): Rate on the first day.
            step (float): Daily increase.

        Returns:
            list[ExchangeRateItem]: The series, oldest first.
    '''
    return [
        ExchangeRateItem(
            currency = USD,
            date = FLOAT_START + timedelta(days = offset),
            official_rate = round(start_rate + step * offset, 4),
            source = bcb_source.SOURCE_NAME,
            retrieved_at = '2026-09-03T00:00:00+00:00'
        )
        for offset in range(days)
    ]


@pytest.fixture(name = 'store')
def _store():
    '''
        Replaces the DynamoDB access with an in-memory dictionary.

        Yields:
            dict: The stored items, keyed by (currency, date). Tests seed it by
                writing straight into it.
    '''
    items: dict = {}

    def _query(currency: str, start = None, end = None) -> list[ExchangeRateItem]:
        return sorted(
            (item for (code, day), item in items.items()
             if code == currency
             and (start is None or day >= start)
             and (end is None or day <= end)),
            key = lambda item: item.date
        )

    with pytest.MonkeyPatch.context() as patcher:
        patcher.setattr(quotes, 'get_rate',
                        lambda currency, day: items.get((currency, day)))
        patcher.setattr(quotes, 'put_rate',
                        lambda rate: items.__setitem__((rate.currency, rate.date), rate))
        patcher.setattr(quotes, 'query_rates', _query)
        yield items


@pytest.fixture(name = 'seeded_store')
def _seeded_store(store: dict) -> dict:
    '''
        A store already holding enough float-regime history to earn a projection.

        Args:
            store (dict): The empty in-memory store.

        Returns:
            dict: The same store, seeded with 60 days.
    '''
    for item in build_history(60):
        store[(item.currency, item.date)] = item
    return store
