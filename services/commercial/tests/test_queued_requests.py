'''
    The queue SmartBilling fills: each record is served as the HTTP request it
    stands for, and a request not answered with a 2xx is reported as failed so
    SQS retries it.
'''
import asyncio
import json

import main
from services import utils

LIVE_PATH = '/v1/commercial/sales/live'


def _record(
    message_id: str,
    authorization: str
) -> dict:
    '''One SQS record carrying a queued live sale.'''
    return {'messageId': message_id, 'eventSource': utils.QUEUE_SOURCE, 'body': json.dumps({
        'path': LIVE_PATH, 'authorization': authorization,
        'body': {'rows': [{'date': '2026-11-06', 'order_id': 'A-1', 'product_name': 'Leche',
                           'quantity': 1}]}})}


def test_a_queued_request_meets_the_real_route_and_its_token_check():
    '''Through Mangum and the route itself: a forged token is refused and reported.'''
    # Mangum serves on the thread's loop, as it has one in Lambda; earlier
    # tests in the same run closed theirs.
    asyncio.set_event_loop(asyncio.new_event_loop())
    answer = main.handler({'Records': [_record('m-1', 'Bearer forged')]}, None)
    assert answer == {'batchItemFailures': [{'itemIdentifier': 'm-1'}]}


def test_only_the_failed_records_are_reported(monkeypatch):
    '''Each record is its own request; the one answered 2xx is done.'''
    served: list = []

    def _serve(
        event,
        _context
    ):
        served.append((event['rawPath'], event['headers']['authorization'],
                       json.loads(event['body'])['rows'][0]['order_id']))
        return {'statusCode': 200 if event['headers']['authorization'] == 'Bearer ok' else 500}

    monkeypatch.setattr(main, '_asgi_handler', _serve)
    answer = main.handler({'Records': [_record('m-1', 'Bearer ok'),
                                       _record('m-2', 'Bearer down')]}, None)
    assert served == [(LIVE_PATH, 'Bearer ok', 'A-1'), (LIVE_PATH, 'Bearer down', 'A-1')]
    assert answer == {'batchItemFailures': [{'itemIdentifier': 'm-2'}]}


def test_an_http_event_goes_to_mangum_untouched(monkeypatch):
    '''API Gateway's own events are not records.'''
    event = {'version': '2.0', 'rawPath': '/v1/commercial/health'}
    monkeypatch.setattr(main, '_asgi_handler', lambda received, _context: received)
    assert main.handler(event, None) is event


def test_a_queued_correction_is_served_with_its_method():
    '''A PATCH kept in the queue reaches the PATCH route, refused only for its token.'''
    record = {'messageId': 'm-9', 'eventSource': utils.QUEUE_SOURCE, 'body': json.dumps({
        'method': 'PATCH', 'path': '/v1/commercial/products/SKU-1',
        'authorization': 'Bearer forged', 'body': {'category': 'Vitaminas'}})}
    asyncio.set_event_loop(asyncio.new_event_loop())
    answer = main._asgi_handler(utils.queued_request(record), None) # pylint: disable=protected-access
    assert answer['statusCode'] == 401
