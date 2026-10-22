'''
    Recent activity: the counts and the lists, from records already read.

    Pure on purpose, with no configuration: the CI of GitHub Actions runs the
    base services' tests with no .env, and this is the part worth testing.
'''
from datetime import datetime, timedelta
from typing import Any
from schemas.activity import HourBucket, RecentCall, RecentChange, ServiceActivity

# Below this a call was answered; from here on it failed.
ERROR_FROM = 400
SERVER_ERROR_FROM = 500


def hour_keys(
    now: datetime,
    hours: int
) -> list[str]:
    '''
        The hours of the period, oldest first, as the records write them.

        Args:
            now (datetime): Current time, aware of the service time zone.
            hours (int): How many hours back.

        Returns:
            list[str]: Keys like 2026-10-21T14.
    '''
    start = now.replace(minute = 0, second = 0, microsecond = 0) - timedelta(hours = hours - 1)
    return [(start + timedelta(hours = step)).strftime('%Y-%m-%dT%H') for step in range(hours)]


def summarize_service(
    microservice: str,
    calls: list[dict[str, Any]],
    keys: list[str]
) -> ServiceActivity:
    '''
        One service's calls counted by class and by hour.

        Args:
            microservice (str): Service name.
            calls (list[dict[str, Any]]): Its usage records in the period.
            keys (list[str]): The hours of the period.

        Returns:
            ServiceActivity: Totals, mean response time and hourly buckets.
    '''
    codes = [int(call.get('status_code', 0)) for call in calls]
    times = [int(call['response_time_ms']) for call in calls
             if call.get('response_time_ms') is not None]
    by_hour = {key: [0, 0] for key in keys}
    for call, code in zip(calls, codes):
        slot = by_hour.get(str(call.get('timestamp', ''))[:13])
        if slot is not None:
            slot[1 if code >= ERROR_FROM else 0] += 1
    return ServiceActivity(
        microservice = microservice,
        total = len(codes),
        ok = sum(code < ERROR_FROM for code in codes),
        client_errors = sum(ERROR_FROM <= code < SERVER_ERROR_FROM for code in codes),
        server_errors = sum(code >= SERVER_ERROR_FROM for code in codes),
        avg_response_ms = round(sum(times) / len(times)) if times else None,
        buckets = [HourBucket(hour = key, ok = ok, errors = errors)
                   for key, (ok, errors) in by_hour.items()]
    )


def latest_errors(
    calls: list[dict[str, Any]],
    limit: int
) -> list[RecentCall]:
    '''
        The newest failed calls of every service.

        Args:
            calls (list[dict[str, Any]]): Usage records of every service.
            limit (int): How many to keep.

        Returns:
            list[RecentCall]: Newest first.
    '''
    failed = [call for call in calls if int(call.get('status_code', 0)) >= ERROR_FROM]
    failed.sort(key = lambda call: str(call.get('timestamp', '')), reverse = True)
    return [RecentCall(
        timestamp = str(call['timestamp']),
        microservice = str(call['microservice']),
        method = call.get('method'),
        endpoint = call.get('endpoint'),
        status_code = int(call['status_code']),
        user_id = None if call.get('user_id') is None else str(call['user_id']),
        response_time_ms = None if call.get('response_time_ms') is None
        else int(call['response_time_ms'])
    ) for call in failed[:limit]]


def latest_changes(
    changes: list[dict[str, Any]],
    limit: int
) -> list[RecentChange]:
    '''
        The newest audited changes of every service.

        Args:
            changes (list[dict[str, Any]]): Audit records of every service.
            limit (int): How many to keep.

        Returns:
            list[RecentChange]: Newest first.
    '''
    ordered = sorted(changes, key = lambda change: str(change.get('timestamp', '')),
                     reverse = True)
    return [RecentChange(
        timestamp = str(change['timestamp']),
        microservice = str(change['microservice']),
        entity_name = change.get('entity_name'),
        entity_id = None if change.get('entity_id') is None else str(change['entity_id']),
        action = change.get('action'),
        user_id = None if change.get('user_id') is None else str(change['user_id'])
    ) for change in ordered[:limit]]
