'''
    Business logic for the Institutions catalog of the Mining Summit.

    The catalog lives in the DynamoDB table `mining_summit_institutions` (seeded
    from the official participation matrix by tools/mining_summit/
    import_institutions.py). It is served read-only. The participant role is no
    longer derived here: it belongs to each person (ETL row or registration form).
'''
import re
import unicodedata
from typing import Any, Dict, List, Optional

from boto3.resources.base import ServiceResource

from services.crud import create_item, get_all_records_paginated, get_item_by_key
from services.environment import load_and_validate_env_vars
from services.exceptions import InvalidInputError, RegisterNotFoundError
from services.logger_config import custom_logger as logger
from services.utils import handle_service_errors

ENV_VARS = load_and_validate_env_vars({
    'DYNAMODB_TABLE_NAME_INSTITUTIONS': str
})

INSTITUTIONS_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_INSTITUTIONS']


def _enrich(institution: Dict[str, Any]) -> Dict[str, Any]:
    '''
        Normalizes DynamoDB numeric types (Decimal) to int.

        Args:
            institution (Dict[str, Any]): Raw catalog item from DynamoDB.

        Returns:
            Dict[str, Any]: The institution with normalized numeric fields.
    '''
    return {
        **institution,
        # 'number' is legacy (row in the official matrix); optional going forward.
        'number': int(institution['number']) if institution.get('number') is not None else None,
        'cupos': int(institution['cupos'])
    }


@handle_service_errors
def list_institutions(
    dynamodb_resource: ServiceResource,
    category: Optional[str] = None
) -> List[Dict[str, Any]]:
    '''
        Returns the catalog, optionally filtered by category, ordered
        alphabetically by name.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            category (Optional[str]): Category value to filter by.

        Returns:
            List[Dict[str, Any]]: Matching institutions.
    '''
    response = get_all_records_paginated(
        dynamodb_resource = dynamodb_resource,
        table_name = INSTITUTIONS_TABLE,
        query_params = {}
    )
    items = [_enrich(item) for item in response['items']]
    if category:
        items = [item for item in items if item['category'] == category]
    return sorted(items, key = lambda item: (item.get('name') or '').lower())


@handle_service_errors
def get_institution(
    dynamodb_resource: ServiceResource,
    institution_id: str
) -> Dict[str, Any]:
    '''
        Returns a single enriched institution by id.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            institution_id (str): The institution slug identifier.

        Returns:
            Dict[str, Any]: The enriched institution entry.

        Raises:
            RegisterNotFoundError: If no institution matches the id.
    '''
    item = get_item_by_key(
        dynamodb_resource = dynamodb_resource,
        table_name = INSTITUTIONS_TABLE,
        key = {'id': institution_id.strip()}
    )
    return _enrich(item)


@handle_service_errors
def update_institution_cupos(
    dynamodb_resource: ServiceResource,
    institution_id: str,
    cupos: int
) -> Dict[str, Any]:
    '''
        Updates the participant quota (cupos) assigned to an institution. This
        parametric quota drives the ETL load limit and the raffle capacity.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            institution_id (str): The institution slug identifier.
            cupos (int): New non-negative quota.

        Returns:
            Dict[str, Any]: The updated, enriched institution.

        Raises:
            InvalidInputError: If cupos is negative.
            RegisterNotFoundError: If the institution does not exist.
    '''
    if cupos < 0:
        raise InvalidInputError(detail = 'cupos must be a non-negative integer.')
    # Ensure the institution exists before writing.
    get_item_by_key(
        dynamodb_resource = dynamodb_resource,
        table_name = INSTITUTIONS_TABLE,
        key = {'id': institution_id.strip()}
    )
    dynamodb_resource.Table(INSTITUTIONS_TABLE).update_item(
        Key = {'id': institution_id.strip()},
        UpdateExpression = 'SET cupos = :cupos',
        ExpressionAttributeValues = {':cupos': int(cupos)}
    )
    message = f'Institution {institution_id} cupos updated to {cupos}.'
    logger.info(message)
    return get_institution(dynamodb_resource, institution_id)


def _slugify(text: str) -> str:
    '''Builds a URL-safe slug id from a name (lowercase, ascii, dash-joined).'''
    ascii_text = ''.join(
        char for char in unicodedata.normalize('NFKD', text)
        if not unicodedata.combining(char)
    ).lower()
    return re.sub(r'[^a-z0-9]+', '-', ascii_text).strip('-')


@handle_service_errors
def create_institution(
    dynamodb_resource: ServiceResource,
    payload: Dict[str, Any]
) -> Dict[str, Any]:
    '''
        Registers a new institution. The id is taken from the payload or derived
        from the name (slug); it must be unique.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            payload (Dict[str, Any]): name, category, cupos, optional
                abbreviation and id.

        Returns:
            Dict[str, Any]: The persisted, enriched institution.

        Raises:
            InvalidInputError: If cupos is negative or the name is empty.
            RegisterAlreadyExistsError: If the id already exists.
    '''
    if int(payload['cupos']) < 0:
        raise InvalidInputError(detail = 'cupos must be a non-negative integer.')
    name = payload['name'].strip()
    institution_id = (payload.get('id') or _slugify(name)).strip()
    if not institution_id:
        raise InvalidInputError(detail = 'Could not derive a valid id from the name.')
    item = {
        'id': institution_id,
        'name': name,
        'abbreviation': (payload.get('abbreviation') or '').strip() or None,
        'category': payload['category'],
        'cupos': int(payload['cupos'])
    }
    saved = create_item(
        dynamodb_resource = dynamodb_resource,
        table_name = INSTITUTIONS_TABLE,
        item_data = item,
        unique_key_attribute = 'id'
    )
    message = f'Institution {saved["id"]} created.'
    logger.info(message)
    return _enrich(saved)


@handle_service_errors
def update_institution(
    dynamodb_resource: ServiceResource,
    institution_id: str,
    fields: Dict[str, Any]
) -> Dict[str, Any]:
    '''
        Updates the editable attributes of an institution (name, abbreviation,
        category, cupos). Only supplied fields change.

        Raises:
            InvalidInputError: If nothing is provided or cupos is negative.
            RegisterNotFoundError: If the institution does not exist.
    '''
    current = get_item_by_key(
        dynamodb_resource = dynamodb_resource,
        table_name = INSTITUTIONS_TABLE,
        key = {'id': institution_id.strip()}
    )
    if 'cupos' in fields and int(fields['cupos']) < 0:
        raise InvalidInputError(detail = 'cupos must be a non-negative integer.')
    editable = {'name', 'abbreviation', 'category', 'cupos'}
    changes = {key: value for key, value in fields.items() if key in editable}
    if not changes:
        raise InvalidInputError(detail = 'Provide at least one field to update.')
    if 'cupos' in changes:
        changes['cupos'] = int(changes['cupos'])
    updated = {**current, **changes}
    dynamodb_resource.Table(INSTITUTIONS_TABLE).put_item(Item = updated)
    message = f'Institution {institution_id} updated ({", ".join(changes)}).'
    logger.info(message)
    return _enrich(updated)


@handle_service_errors
def delete_institution(dynamodb_resource: ServiceResource, institution_id: str) -> None:
    '''
        Deletes an institution by id. Enforces existence first.

        Raises:
            RegisterNotFoundError: If the institution does not exist.
    '''
    key = {'id': institution_id.strip()}
    table = dynamodb_resource.Table(INSTITUTIONS_TABLE)
    if not table.get_item(Key = key).get('Item'):
        error_msg = f'Institution with id {institution_id} not found.'
        logger.warning(error_msg)
        raise RegisterNotFoundError(detail = error_msg)
    table.delete_item(Key = key)
    message = f'Institution {institution_id} deleted.'
    logger.info(message)
