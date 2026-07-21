'''
    Business logic for the mesas (working tables ≡ aulas) and their allocation
    to the thematic axes of the Mining Summit.

    Aulas are stored parametrically in the DynamoDB table `mining_summit_aulas`
    (partition key: code). Each aula carries its own capacity and the thematic
    axis it is allocated to, so both the per-aula capacity and the aula↔axis
    binding can be adjusted at runtime through the admin endpoints without any
    code change. The six axes themselves remain a fixed catalog (summit_rules).
'''
from typing import Any, Dict, List, Optional
from boto3.resources.base import ServiceResource

from schemas.enums import ThematicAxis
from services.crud import create_item, get_item_by_key, scan_all_items
from services.environment import load_and_validate_env_vars
from services.exceptions import InvalidInputError, RegisterNotFoundError
from services.logger_config import custom_logger as logger
from services.summit_rules import AXIS_METADATA
from services.utils import handle_service_errors

ENV_VARS = load_and_validate_env_vars({
    'DYNAMODB_TABLE_NAME_AULAS': str
})

AULAS_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_AULAS']


def _enrich_aula(aula: Dict[str, Any]) -> Dict[str, Any]:
    '''
        Normalizes numeric types and attaches the axis number/label metadata.

        A pivot aula (free disposition) has no axis yet, so its axis metadata is
        left as None until an admin allocates it to a thematic axis.

        Args:
            aula (Dict[str, Any]): Raw aula item from DynamoDB.

        Returns:
            Dict[str, Any]: Aula including 'axis_number' and 'axis_label'
                (None for pivot aulas).
    '''
    raw_axis = aula.get('axis')
    number, label = (
        AXIS_METADATA[ThematicAxis(raw_axis)] if raw_axis else (None, None)
    )
    return {
        **aula,
        'axis': raw_axis or None,
        'capacity': int(aula['capacity']),
        'axis_number': number,
        'axis_label': label
    }


def _scan_aulas(dynamodb_resource: ServiceResource) -> List[Dict[str, Any]]:
    '''
        Scans the full aulas table (small reference set, 17 items).

        Returns:
            List[Dict[str, Any]]: Raw aula items.
    '''
    return scan_all_items(dynamodb_resource, AULAS_TABLE)


@handle_service_errors
def list_mesas(
    dynamodb_resource: ServiceResource,
    axis: Optional[str] = None
) -> List[Dict[str, Any]]:
    '''
        Returns the allocated aulas, optionally filtered by thematic axis,
        ordered by axis number then aula code.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            axis (Optional[str]): Axis value to filter by.

        Returns:
            List[Dict[str, Any]]: Matching aulas enriched with axis metadata.
    '''
    mesas = [_enrich_aula(item) for item in _scan_aulas(dynamodb_resource)]
    if axis:
        mesas = [mesa for mesa in mesas if mesa['axis'] == axis]
    # Pivot aulas (axis_number is None) are listed last, after the six axes.
    max_number = len(ThematicAxis) + 1
    return sorted(
        mesas,
        key = lambda mesa: (mesa['axis_number'] or max_number, mesa['code'])
    )


@handle_service_errors
def get_mesa(dynamodb_resource: ServiceResource, code: str) -> Dict[str, Any]:
    '''
        Returns a single enriched aula by its code.

        Raises:
            RegisterNotFoundError: If no aula matches the code.
    '''
    item = get_item_by_key(
        dynamodb_resource = dynamodb_resource,
        table_name = AULAS_TABLE,
        key = {'code': code.strip()}
    )
    return _enrich_aula(item)


@handle_service_errors
def update_mesa(
    dynamodb_resource: ServiceResource,
    code: str,
    changes: Dict[str, Any]
) -> Dict[str, Any]:
    '''
        Updates the parametric attributes of an aula (block, location, capacity
        and/or axis).

        Only the supplied keys of `changes` are applied. Enforces that the aula
        exists before writing, so a typo does not silently create a new record.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            code (str): Aula code (partition key).
            changes (Dict[str, Any]): Any of 'block', 'location', 'capacity',
                'axis' to overwrite. Missing keys are left untouched. An 'axis'
                key set to None de-allocates the aula back to a pivot.

        Returns:
            Dict[str, Any]: The updated, enriched aula.

        Raises:
            InvalidInputError: If nothing is provided to update or capacity <= 0.
            RegisterNotFoundError: If the aula does not exist.
    '''
    if not changes:
        raise InvalidInputError(detail = 'Provide at least one field to update.')
    capacity = changes.get('capacity')
    if capacity is not None and capacity <= 0:
        raise InvalidInputError(detail = 'Aula capacity must be a positive integer.')

    # Ensure the aula exists (get_item_by_key raises if missing).
    current = get_item_by_key(
        dynamodb_resource = dynamodb_resource,
        table_name = AULAS_TABLE,
        key = {'code': code.strip()}
    )
    updated = {**current}
    for text_field in ('block', 'location'):
        if changes.get(text_field) is not None:
            updated[text_field] = changes[text_field].strip()
    if capacity is not None:
        updated['capacity'] = int(capacity)
    if 'axis' in changes:
        # An explicit None de-allocates the aula (drops the axis attribute).
        if changes['axis']:
            updated['axis'] = changes['axis']
        else:
            updated.pop('axis', None)
    dynamodb_resource.Table(AULAS_TABLE).put_item(Item = updated)
    message = f'Aula {code} updated (capacity={updated["capacity"]}, axis={updated.get("axis")}).'
    logger.info(message)
    return _enrich_aula(updated)


@handle_service_errors
def create_mesa(
    dynamodb_resource: ServiceResource,
    payload: Dict[str, Any]
) -> Dict[str, Any]:
    '''
        Registers a new aula (e.g. an extra classroom assigned to the summit)
        with its capacity and, optionally, a thematic axis. Omitting the axis
        creates a pivot aula (free disposition) to be allocated later. The code
        must be unique.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            payload (Dict[str, Any]): code, block, location, capacity and an
                optional axis (None for a pivot aula).

        Returns:
            Dict[str, Any]: The persisted, enriched aula.

        Raises:
            InvalidInputError: If capacity is not positive.
            RegisterAlreadyExistsError: If an aula with that code already exists.
    '''
    if int(payload['capacity']) <= 0:
        raise InvalidInputError(detail = 'Aula capacity must be a positive integer.')
    item = {
        'code': payload['code'].strip(),
        'block': payload['block'].strip(),
        'location': payload['location'].strip(),
        'capacity': int(payload['capacity'])
    }
    # A pivot aula is stored without an axis attribute (free disposition).
    if payload.get('axis'):
        item['axis'] = payload['axis']
    saved = create_item(
        dynamodb_resource = dynamodb_resource,
        table_name = AULAS_TABLE,
        item_data = item,
        unique_key_attribute = 'code'
    )
    message = (f'Aula {saved["code"]} created '
               f'(capacity={saved["capacity"]}, axis={saved.get("axis")}).')
    logger.info(message)
    return _enrich_aula(saved)


@handle_service_errors
def delete_mesa(dynamodb_resource: ServiceResource, code: str) -> None:
    '''
        Deletes an aula by its code. Enforces existence first so a wrong code is
        reported instead of silently succeeding.

        Raises:
            RegisterNotFoundError: If the aula does not exist.
    '''
    key = {'code': code.strip()}
    table = dynamodb_resource.Table(AULAS_TABLE)
    if not table.get_item(Key = key).get('Item'):
        error_msg = f'Aula with code {code} not found in {AULAS_TABLE}.'
        logger.warning(error_msg)
        raise RegisterNotFoundError(detail = error_msg)
    table.delete_item(Key = key)
    message = f'Aula {code} deleted.'
    logger.info(message)


@handle_service_errors
def list_axes(dynamodb_resource: ServiceResource) -> List[Dict[str, Any]]:
    '''
        Returns the six thematic axes with their allocated aula count and the
        aggregated seat capacity (the sum of the capacities of the aulas bound
        to each axis), ordered by official number.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.

        Returns:
            List[Dict[str, Any]]: Axis summaries ordered by official number.
    '''
    mesas = [_enrich_aula(item) for item in _scan_aulas(dynamodb_resource)]
    summaries: List[Dict[str, Any]] = []
    for axis in ThematicAxis:
        number, label = AXIS_METADATA[axis]
        axis_mesas = [mesa for mesa in mesas if mesa['axis'] == axis.value]
        summaries.append({
            'axis': axis.value,
            'number': number,
            'label': label,
            'mesas': len(axis_mesas),
            'capacity': sum(mesa['capacity'] for mesa in axis_mesas)
        })
    return summaries
