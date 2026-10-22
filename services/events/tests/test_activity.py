'''
    Recent activity: the counts and lists the ADMIN's dashboard reads.

    Pure: imports only schemas and the summary module, which need no
    configuration, so the CI runs them with no .env.
'''
from datetime import datetime, timezone

from services.activity_summary import (
    hour_keys,
    latest_changes,
    latest_errors,
    summarize_service
)

NOW = datetime(2026, 10, 21, 14, 30, tzinfo = timezone.utc)


def test_the_period_has_one_key_per_hour_oldest_first() -> None:
    '''Three hours back from 14:30 are 12, 13 and 14.'''
    assert hour_keys(NOW, 3) == ['2026-10-21T12', '2026-10-21T13', '2026-10-21T14']


def test_a_service_is_counted_by_class_and_by_hour() -> None:
    '''2xx are answered; 4xx and 5xx are failures, each in its hour.'''
    calls = [
        {'timestamp': '2026-10-21T13:05:00', 'status_code': 200, 'response_time_ms': 100},
        {'timestamp': '2026-10-21T13:40:00', 'status_code': 404, 'response_time_ms': 300},
        {'timestamp': '2026-10-21T14:10:00', 'status_code': 500},
        {'timestamp': '2026-10-21T09:00:00', 'status_code': 200}
    ]
    summary = summarize_service('FINANCE', calls, hour_keys(NOW, 3))
    assert (summary.total, summary.ok, summary.client_errors, summary.server_errors) == (4, 2, 1, 1)
    assert summary.avg_response_ms == 200
    assert [(bucket.ok, bucket.errors) for bucket in summary.buckets] == [(0, 0), (1, 1), (0, 1)]


def test_a_quiet_service_has_no_mean_time() -> None:
    '''No calls: zeros everywhere and no invented average.'''
    summary = summarize_service('QUOTES', [], hour_keys(NOW, 2))
    assert (summary.total, summary.avg_response_ms) == (0, None)


def test_only_failures_are_listed_newest_first() -> None:
    '''The answered call is left out; the newest failure comes first.'''
    calls = [
        {'timestamp': '2026-10-21T13:00:00', 'microservice': 'AI', 'status_code': 502},
        {'timestamp': '2026-10-21T14:00:00', 'microservice': 'FINANCE', 'status_code': 422,
         'user_app': 'ana@acme.com'},
        {'timestamp': '2026-10-21T14:05:00', 'microservice': 'FINANCE', 'status_code': 200}
    ]
    listed = latest_errors(calls, 10)
    assert [(call.microservice, call.status_code) for call in listed] == [
        ('FINANCE', 422), ('AI', 502)]
    assert (listed[0].user_app, listed[0].user_id) == ('ana@acme.com', None)


def test_changes_are_listed_newest_first_and_capped() -> None:
    '''Only the requested number of the newest changes.'''
    changes = [{'timestamp': f'2026-10-21T1{hour}:00:00', 'microservice': 'FINANCE',
                'action': 'UPDATE', 'entity_id': hour} for hour in range(4)]
    listed = latest_changes(changes, 2)
    assert [change.timestamp for change in listed] == ['2026-10-21T13:00:00',
                                                       '2026-10-21T12:00:00']
    assert listed[0].entity_id == '3'
