'''
    Recent activity of the platform: reads the last hours of each service.

    Both tables have an index by microservice and date, so each service is a
    Query over its own last hours, never a scan of the whole table. Only the
    fields the dashboard shows are read: the bodies are what weighs.
'''
from datetime import timedelta
from typing import Any
from boto3.dynamodb.conditions import Key
from boto3.resources.base import ServiceResource
from schemas.activity import ActivityQuerySchema, ActivityResponseSchema
from services.activity_summary import (
    hour_keys,
    latest_changes,
    latest_errors,
    summarize_service
)
from services.environment import load_and_validate_env_vars
from services.logger_config import custom_logger as logger
from services.utils import get_current_time_gmt

ENV_VARS = load_and_validate_env_vars({
    'DYNAMODB_TABLE_NAME_USAGE': str,
    'DYNAMODB_TABLE_NAME_AUDIT': str
})
USAGE_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_USAGE']
AUDIT_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_AUDIT']

# The index both tables carry: partitioned by microservice, sorted by date.
ACTIVITY_INDEX = 'microservice-timestamp-index'
CALL_FIELDS = ('microservice', 'timestamp', 'method', 'endpoint', 'status_code',
               'user_id', 'user_app', 'response_time_ms')
CHANGE_FIELDS = ('microservice', 'timestamp', 'entity_name', 'entity_id', 'action', 'user_id')
# How many of each list the dashboard shows.
LIST_SIZE = 20


def _recent(
    table: Any,
    microservice: str,
    since: str,
    fields: tuple[str, ...]
) -> list[dict[str, Any]]:
    '''
        Every record of one service since a moment, only the given fields.

        Args:
            table (Any): The DynamoDB table.
            microservice (str): Service name.
            since (str): ISO moment the period starts at.
            fields (tuple[str, ...]): Attributes to read.

        Returns:
            list[dict[str, Any]]: The records.
    '''
    names = {f'#f{index}': field for index, field in enumerate(fields)}
    kwargs = {
        'IndexName': ACTIVITY_INDEX,
        'KeyConditionExpression': Key('microservice').eq(microservice)
        & Key('timestamp').gte(since),
        'ProjectionExpression': ', '.join(names),
        'ExpressionAttributeNames': names
    }
    items: list[dict[str, Any]] = []
    while True:
        page = table.query(**kwargs)
        items.extend(page.get('Items', []))
        if 'LastEvaluatedKey' not in page:
            return items
        kwargs['ExclusiveStartKey'] = page['LastEvaluatedKey']


def recent_activity(
    dynamodb_resource: ServiceResource,
    query: ActivityQuerySchema
) -> ActivityResponseSchema:
    '''
        Each service's calls of the last hours and what deserves a look first.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            query (ActivityQuerySchema): Services and hours.

        Returns:
            ActivityResponseSchema: Counts per service and hour, the latest
            failed calls and the latest audited changes.
    '''
    now = get_current_time_gmt()
    since = (now - timedelta(hours = query.hours)).isoformat()
    names = [name.strip() for name in query.microservices.split(',') if name.strip()]
    usage = dynamodb_resource.Table(USAGE_TABLE)
    audit = dynamodb_resource.Table(AUDIT_TABLE)
    calls = {name: _recent(usage, name, since, CALL_FIELDS) for name in names}
    changes = [change for name in names for change in _recent(audit, name, since, CHANGE_FIELDS)]
    keys = hour_keys(now, query.hours)
    message = (f'Recent activity of {len(names)} services over {query.hours} h: '
               f'{sum(len(items) for items in calls.values())} calls, {len(changes)} changes.')
    logger.info(message)
    return ActivityResponseSchema(
        since = since,
        hours = query.hours,
        services = [summarize_service(name, items, keys) for name, items in calls.items()],
        latest_errors = latest_errors(
            [call for items in calls.values() for call in items], LIST_SIZE),
        latest_changes = latest_changes(changes, LIST_SIZE)
    )
