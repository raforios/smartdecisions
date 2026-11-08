'''
    The queue SmartBilling fills: each record is served as the HTTP request it
    stands for, through the real route and its token check.
'''
import asyncio
import json
import time

from fastapi.testclient import TestClient
from jose import jwt

import main
from routes import entries as entries_routes
from schemas.entries import LoadChannel, LoadFlow, LoadResultSchema
from services import security, utils

LOADS_PATH = '/v1/finance/loads'


def _record(
    message_id: str,
    authorization: str
) -> dict:
    '''One SQS record carrying a queued load.'''
    return {'messageId': message_id, 'eventSource': utils.QUEUE_SOURCE, 'body': json.dumps({
        'path': LOADS_PATH, 'authorization': authorization,
        'body': {'flow': 'PROCESSED', 'rows': [{'date': '2026-11', 'periodicity': 'MONTHLY',
                                                'account_code': '4.1.05', 'amount': 10}]}})}


def test_a_queued_load_meets_the_real_route_and_its_token_check():
    '''Through Mangum and the route itself: a forged token is refused and reported.'''
    # Mangum serves on the thread's loop, as it has one in Lambda; earlier
    # tests in the same run may have closed theirs.
    asyncio.set_event_loop(asyncio.new_event_loop())
    answer = main.handler({'Records': [_record('m-1', 'Bearer forged')]}, None)
    assert answer == {'batchItemFailures': [{'itemIdentifier': 'm-1'}]}


def test_an_http_event_goes_to_mangum_untouched(monkeypatch):
    '''API Gateway's own events are not records.'''
    event = {'version': '2.0', 'rawPath': '/v1/finance/health'}
    monkeypatch.setattr(main, '_asgi_handler', lambda received, _context: received)
    assert main.handler(event, None) is event


def _bearer(role: str) -> str:
    '''A token of the company's user with `role`, signed like AUTH signs.'''
    token = jwt.encode({'email': f'{role.lower()}@farmacia.bo', 'role': role,
                        'client': 'The Pharma', 'exp': time.time() + 600},
                       security.SECRET_KEY, algorithm = security.ALGORITHM)
    return f'Bearer {token}'


def test_any_user_loads_through_the_queue_and_only_a_manager_loads_directly(monkeypatch):
    '''A seller's sale reaches FINANCE through SmartBilling; the seller cannot load figures.'''
    loaded: list = []

    async def _load(**kwargs):
        loaded.append(kwargs['client'])
        return LoadResultSchema(load_id = 'L-1', flow = LoadFlow.PROCESSED,
                                channel = LoadChannel.API, accepted = 1, rejected = [])

    monkeypatch.setattr(entries_routes, 'load_entries_controller', _load)
    asyncio.set_event_loop(asyncio.new_event_loop())
    answer = main.handler({'Records': [_record('m-1', _bearer('SELLER'))]}, None)
    assert answer == {'batchItemFailures': []} and loaded == ['The Pharma']

    body = json.loads(_record('m-2', '')['body'])['body']
    client = TestClient(main.app)
    refused = client.post(LOADS_PATH, json = body, headers = {'Authorization': _bearer('SELLER')})
    assert refused.status_code == 403
    accepted = client.post(LOADS_PATH, json = body, headers = {'Authorization': _bearer('MANAGER')})
    assert accepted.status_code == 201 and len(loaded) == 2
