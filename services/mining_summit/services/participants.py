'''
    Business logic for the Participants module of the Mining Summit service.
'''
from typing import Any, Dict, List, Optional
from boto3.resources.base import ServiceResource

from services.crud import (
    create_item,
    find_item_by_key,
    get_all_records_paginated,
    get_item_by_key
)
from services.environment import load_and_validate_env_vars
from services.logger_config import custom_logger as logger
from services.utils import get_current_time_gmt, handle_service_errors

ENV_VARS = load_and_validate_env_vars({
    'DYNAMODB_TABLE_NAME_PARTICIPANTS': str
})

PARTICIPANTS_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_PARTICIPANTS']


def _build_participant_item(payload: Dict[str, Any]) -> Dict[str, Any]:
    '''
        Builds the DynamoDB item shape for a new participant, stamping the
        registration date and timestamp using the configured target timezone.
    '''
    now = get_current_time_gmt()
    return {
        'ci': payload['ci'].strip(),
        'first_name': payload['first_name'].strip(),
        'last_name': payload['last_name'].strip(),
        'email': payload.get('email'),
        'phone': payload.get('phone'),
        'department': payload.get('department'),
        'company': payload.get('company'),
        'registered_date': now.date().isoformat(),
        'registered_at': now.isoformat()
    }


def _apply_date_range(
    items: List[Dict[str, Any]],
    date_field: str,
    date_from: Optional[str],
    date_to: Optional[str]
) -> List[Dict[str, Any]]:
    '''
        Filters a list of items by an inclusive date range on the given field.
        DynamoDB Scan does not natively express date-range filters in our
        generic CRUD primitive, so the bound is applied client-side over the
        already-paginated batch.
    '''
    if not date_from and not date_to:
        return items
    filtered: List[Dict[str, Any]] = []
    for item in items:
        value = item.get(date_field)
        if not value:
            continue
        if date_from and value < date_from:
            continue
        if date_to and value > date_to:
            continue
        filtered.append(item)
    return filtered


@handle_service_errors
def create_participant(
    dynamodb_resource: ServiceResource,
    payload: Dict[str, Any]
) -> Dict[str, Any]:
    '''
        Persists a new participant ensuring the CI is unique.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            payload (Dict[str, Any]): Participant data (already validated).

        Returns:
            Dict[str, Any]: The persisted participant item.
    '''
    item = _build_participant_item(payload)
    message = f'Creating participant ci={item["ci"]}'
    logger.info(message)
    return create_item(
        dynamodb_resource = dynamodb_resource,
        table_name = PARTICIPANTS_TABLE,
        item_data = item,
        unique_key_attribute = 'ci'
    )


@handle_service_errors
def get_participant_by_ci(
    dynamodb_resource: ServiceResource,
    ci: str
) -> Dict[str, Any]:
    '''
        Retrieves a participant by CI. Raises RegisterNotFoundError if missing.
    '''
    return get_item_by_key(
        dynamodb_resource = dynamodb_resource,
        table_name = PARTICIPANTS_TABLE,
        key = {'ci': ci.strip()}
    )


@handle_service_errors
def find_participant_by_ci(
    dynamodb_resource: ServiceResource,
    ci: str
) -> Optional[Dict[str, Any]]:
    '''
        Retrieves a participant by CI. Returns None if not found (no exception).
    '''
    return find_item_by_key(
        dynamodb_resource = dynamodb_resource,
        table_name = PARTICIPANTS_TABLE,
        key = {'ci': ci.strip()}
    )


@handle_service_errors
def list_participants(
    dynamodb_resource: ServiceResource,
    query_params: Dict[str, Any]
) -> Dict[str, Any]:
    '''
        Lists participants with optional filters and pagination. Equality
        filters (department, company) are pushed down to DynamoDB; the
        registered_from/registered_to range is applied client-side.
    '''
    date_from = query_params.pop('registered_from', None)
    date_to = query_params.pop('registered_to', None)

    response = get_all_records_paginated(
        dynamodb_resource = dynamodb_resource,
        table_name = PARTICIPANTS_TABLE,
        query_params = query_params
    )
    response['items'] = _apply_date_range(
        items = response['items'],
        date_field = 'registered_date',
        date_from = date_from,
        date_to = date_to
    )
    return response


@handle_service_errors
def scan_all_participants(
    dynamodb_resource: ServiceResource
) -> List[Dict[str, Any]]:
    '''
        Scans the full participants table. Used by the statistics report,
        which needs the entire dataset to compute aggregations.
    '''
    table = dynamodb_resource.Table(PARTICIPANTS_TABLE)
    items: List[Dict[str, Any]] = []
    response = table.scan()
    items.extend(response.get('Items', []))
    while 'LastEvaluatedKey' in response:
        response = table.scan(ExclusiveStartKey = response['LastEvaluatedKey'])
        items.extend(response.get('Items', []))
    return items
