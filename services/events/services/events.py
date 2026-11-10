'''
    The two logs EVENTS keeps: the audit of who changed what, and the usage of
    every API call. Both are written and read the same way —an id and a
    timestamp on the way in, the bodies capped, a paginated read through the
    index by microservice and date—, so one implementation serves both and
    each log is only its table and its record schema.
'''
import uuid
from dataclasses import dataclass

from boto3.resources.base import ServiceResource
from pydantic import BaseModel

from core.crud import create_item, get_all_records_paginated
from core.environment import load_and_validate_env_vars
from core.logger_config import custom_logger as logger
from core.utils import get_current_time_gmt
from schemas.audit import AuditRecordResponseSchema, AuditRecordsPage
from schemas.usage_log import UsageLogResponseSchema, UsageLogsPage
from services.payload_limits import cap_log_bodies, cap_many

ENV_VARS = load_and_validate_env_vars({
    'DYNAMODB_TABLE_NAME_AUDIT': str,
    'DYNAMODB_TABLE_NAME_USAGE': str
})

# Both tables carry an index on microservice + date: declaring it turns a
# listing into a direct query instead of a scan.
INDEX_PARTITION = 'microservice'


@dataclass(frozen = True)
class EventLog:
    '''
        One of the logs: where it is stored and what its records and pages
        look like.
    '''
    name: str
    table: str
    record: type[BaseModel]
    page: type[BaseModel]


AUDIT_LOG = EventLog(name = 'audit', table = ENV_VARS['DYNAMODB_TABLE_NAME_AUDIT'],
                     record = AuditRecordResponseSchema, page = AuditRecordsPage)
USAGE_LOG = EventLog(name = 'usage', table = ENV_VARS['DYNAMODB_TABLE_NAME_USAGE'],
                     record = UsageLogResponseSchema, page = UsageLogsPage)


def record_event(
    dynamodb_resource: ServiceResource,
    log: EventLog,
    event: BaseModel
) -> BaseModel:
    '''
        Stores one record with a new id and the current timestamp. The bodies
        are capped first: full bodies are what inflates every record and makes
        any read of the table expensive.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            log (EventLog): Which log.
            event (BaseModel): The record as posted.

        Returns:
            BaseModel: The record as stored, in the log's record schema.
    '''
    item = cap_log_bodies({**event.model_dump(), 'id': str(uuid.uuid4()),
                           'timestamp': get_current_time_gmt().isoformat()})
    stored = create_item(dynamodb_resource = dynamodb_resource, table_name = log.table,
                         item_data = item, unique_key_attribute = 'id')
    return log.record(**stored)


def list_events(
    dynamodb_resource: ServiceResource,
    log: EventLog,
    query: BaseModel
) -> BaseModel:
    '''
        One page of a log, filtered.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            log (EventLog): Which log.
            query (BaseModel): The filters, the page size and the cursor.

        Returns:
            BaseModel: The page, in the log's page schema.
    '''
    message = f'Reading the {log.name} log.'
    logger.info(message)
    response = get_all_records_paginated(
        dynamodb_resource = dynamodb_resource,
        table_name = log.table,
        query_params = query.model_dump(exclude_none = True),
        index_partition_attribute = INDEX_PARTITION
    )
    # Records written before the cap still carry their full bodies: a page of
    # 100 went past the Lambda's 6 MB response limit.
    return log.page(records = [log.record(**item) for item in cap_many(response['items'])],
                    last_evaluated_key = response['last_evaluated_key'])
