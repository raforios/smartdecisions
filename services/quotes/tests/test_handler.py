'''
    Tests for the Lambda entry point.

    The function answers two kinds of caller: API Gateway sends HTTP events and
    EventBridge sends a scheduled one, which carries no request at all. Getting
    the discrimination wrong is invisible in every unit test of the domain and
    breaks the whole service the moment it is deployed — Mangum would fail
    looking for a request that a scheduled event never has.
'''
from unittest.mock import patch

import pytest

from fastapi import HTTPException

import main
from schemas.quotes import QuotesError


SCHEDULED_EVENT = {'source': 'aws.events', 'detail-type': 'Scheduled Event'}
HTTP_EVENT = {
    'version': '2.0',
    'rawPath': '/v1/quotes/exchange-rates',
    'requestContext': {'http': {'method': 'GET', 'path': '/v1/quotes/exchange-rates'}},
}


def test_scheduled_event_runs_the_sync():
    '''A scheduled event must reach the sync, never the ASGI adapter.'''
    expected = {'stored': 3, 'already_present': 4}

    async def _sync():
        return expected

    with patch.object(main, 'scheduled_sync_service', _sync), \
         patch.object(main, '_asgi_handler') as asgi:
        result = main.handler(SCHEDULED_EVENT, None)

    assert result == expected
    asgi.assert_not_called()


def test_manual_task_event_runs_the_sync():
    '''
        A console invocation can trigger the same path without waiting for the
        schedule, which is how the sync gets tested after a deploy.
    '''
    async def _sync():
        return {'stored': 1, 'already_present': 0}

    with patch.object(main, 'scheduled_sync_service', _sync), \
         patch.object(main, '_asgi_handler') as asgi:
        main.handler({'task': 'sync_rates'}, None)

    asgi.assert_not_called()


def test_http_event_goes_to_the_asgi_adapter():
    '''
        Every request that is not the schedule keeps its old path. This is the
        assertion that protects the API from the dispatch above.
    '''
    with patch.object(main, '_asgi_handler') as asgi:
        asgi.return_value = {'statusCode': 200}
        result = main.handler(HTTP_EVENT, None)

    assert result == {'statusCode': 200}
    asgi.assert_called_once()


def test_a_failed_scheduled_sync_fails_the_invocation():
    '''
        A sync that could not read the source must mark the invocation as
        failed, so the retry policy applies and the failure is visible. Swallowing
        it would leave a hole in the series that nobody ever sees.
    '''
    async def _sync():
        raise HTTPException(status_code = 503,
                            detail = QuotesError.SOURCE_UNAVAILABLE.value)

    with patch.object(main, 'scheduled_sync_service', _sync):
        with pytest.raises(RuntimeError) as failure:
            main.handler(SCHEDULED_EVENT, None)

    assert QuotesError.SOURCE_UNAVAILABLE.value in str(failure.value)
