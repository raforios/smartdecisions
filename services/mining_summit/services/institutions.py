'''
    Business logic for the Institutions catalog of the Mining Summit.

    The catalog lives in the DynamoDB table `mining_summit_institutions` (seeded
    from the official participation matrix by tools/mining_summit/
    import_institutions.py). It is served read-only; the role and seat-assignment
    type are derived per entry from the category so the rules stay single-sourced
    in summit_rules.
'''
from typing import Any, Dict, List, Optional
from boto3.resources.base import ServiceResource

from schemas.enums import InstitutionCategory
from services.crud import get_all_records_paginated, get_item_by_key
from services.environment import load_and_validate_env_vars
from services.summit_rules import resolve_assignment_type, resolve_role
from services.utils import handle_service_errors

ENV_VARS = load_and_validate_env_vars({
    'DYNAMODB_TABLE_NAME_INSTITUTIONS': str
})

INSTITUTIONS_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_INSTITUTIONS']


def _enrich(institution: Dict[str, Any]) -> Dict[str, Any]:
    '''
        Adds the derived role and seat-assignment type to a catalog entry and
        normalizes DynamoDB numeric types (Decimal) to int.

        Args:
            institution (Dict[str, Any]): Raw catalog item from DynamoDB.

        Returns:
            Dict[str, Any]: Entry including 'role' and 'assignment_type'.
    '''
    role = resolve_role(InstitutionCategory(institution['category']))
    return {
        **institution,
        'number': int(institution['number']),
        'cupos': int(institution['cupos']),
        'role': role.value,
        'assignment_type': resolve_assignment_type(role).value
    }


@handle_service_errors
def list_institutions(
    dynamodb_resource: ServiceResource,
    category: Optional[str] = None,
    role: Optional[str] = None
) -> List[Dict[str, Any]]:
    '''
        Returns the enriched catalog, optionally filtered by category and role,
        ordered by the original matrix number.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            category (Optional[str]): Category value to filter by.
            role (Optional[str]): Derived role value to filter by.

        Returns:
            List[Dict[str, Any]]: Matching enriched institutions.
    '''
    response = get_all_records_paginated(
        dynamodb_resource = dynamodb_resource,
        table_name = INSTITUTIONS_TABLE,
        query_params = {}
    )
    items = [_enrich(item) for item in response['items']]
    if category:
        items = [item for item in items if item['category'] == category]
    if role:
        items = [item for item in items if item['role'] == role]
    return sorted(items, key = lambda item: item['number'])


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
