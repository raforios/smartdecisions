'''
    Tests for the Lambda entry point.

    The function answers two kinds of caller: API Gateway sends HTTP events and
    EventBridge sends a scheduled one, which carries no request at all. Getting
    the discrimination wrong is invisible in every unit test of the domain and
    breaks the whole service the moment it is deployed — Mangum would fail
    looking for a request that a scheduled event never has.
'''
import json
from datetime import date
from unittest.mock import patch

import pytest

from fastapi import HTTPException

import main
from schemas.quotes import QuotesError


SCHEDULED_EVENT = {'source': 'aws.events', 'detail-type': 'Scheduled Event'}


def _sync_payload():
    '''
        A sync result as the domain returns it, dates included.

        Returns:
            dict: Payload matching SyncResult, with real `date` objects.
    '''
    return {
        'currency': 'USD',
        'requested_days': 7,
        'stored': 3,
        'already_present': 4,
        'without_publication': 0,
        'date_from': date(2026, 8, 29),
        'date_to': date(2026, 9, 4),
    }
HTTP_EVENT = {
    'version': '2.0',
    'rawPath': '/v1/quotes/exchange-rates',
    'requestContext': {'http': {'method': 'GET', 'path': '/v1/quotes/exchange-rates'}},
}


def test_scheduled_event_runs_the_sync():
    '''A scheduled event must reach the sync, never the ASGI adapter.'''
    async def _sync():
        return _sync_payload()

    with patch.object(main, 'scheduled_sync_service', _sync), \
         patch.object(main, '_asgi_handler') as asgi:
        result = main.handler(SCHEDULED_EVENT, None)

    assert result['stored'] == 3
    asgi.assert_not_called()


def test_scheduled_result_is_json_serialisable():
    '''
        The Lambda runtime marshals the return value as JSON and cannot handle a
        `date`. On the HTTP path FastAPI does that conversion; a scheduled
        invocation has no FastAPI in front of it, so returning the raw payload
        fails *after* the sync already wrote — the work succeeds and the
        invocation still reports an error, which then gets retried.
    '''
    async def _sync():
        return _sync_payload()

    with patch.object(main, 'scheduled_sync_service', _sync):
        result = main.handler(SCHEDULED_EVENT, None)

    json.dumps(result)
    assert result['date_from'] == '2026-08-29'


def test_manual_task_event_runs_the_sync():
    '''
        A console invocation can trigger the same path without waiting for the
        schedule, which is how the sync gets tested after a deploy.
    '''
    async def _sync():
        return _sync_payload()

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
