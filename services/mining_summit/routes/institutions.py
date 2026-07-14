'''
    Institutions: routes handler.
'''
from fastapi import APIRouter, Depends, Path, status
from boto3.resources.base import ServiceResource

from controllers.institutions import (
    create_institution_controller,
    delete_institution_controller,
    get_institution_controller,
    list_institutions_controller,
    update_institution_controller,
    update_institution_cupos_controller
)
from schemas.enums import RoleEnum
from schemas.institutions import (
    InstitutionCreateSchema,
    InstitutionCuposUpdateSchema,
    InstitutionQuerySchema,
    InstitutionResponseSchema,
    InstitutionsListResponseSchema,
    InstitutionUpdateSchema
)
from services.db_connection import GET_DB_DEPENDENCY
from services.logger_config import custom_logger as logger
from services.security import get_current_user, require_roles

router = APIRouter(prefix = '/v1/mining-summit/institutions', tags = ['Institutions'])


@router.get(
    '',
    response_model = InstitutionsListResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'List reference institutions',
    description = (
        'Returns the reference catalog of institutions from the official '
        'participation matrix, with the role and seat-assignment type derived '
        'from each category. Supports optional category/role filters.'
    )
)
def list_institutions_endpoint(
    query_params: InstitutionQuerySchema = Depends(),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(get_current_user)
):
    '''
        Endpoint to retrieve the institutions reference catalog.
    '''
    message = 'Retrieving institutions catalog.'
    logger.info(message)
    return list_institutions_controller(
        dynamodb_resource = dynamodb_resource,
        query_params = query_params
    )


@router.post(
    '',
    response_model = InstitutionResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Create an institution',
    description = (
        'Registers a new institution with its category and cupo. The id is '
        'derived from the name when not provided. Restricted to ADMIN.'
    )
)
def create_institution_endpoint(
    payload: InstitutionCreateSchema,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(RoleEnum.ADMIN.value))
):
    '''
        Endpoint to create a new institution.
    '''
    message = f'Creating institution name={payload.name}'
    logger.info(message)
    return create_institution_controller(
        dynamodb_resource = dynamodb_resource,
        payload = payload
    )


@router.get(
    '/{institution_id}',
    response_model = InstitutionResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Get institution by id',
    description = 'Retrieves a single reference institution by its slug identifier.'
)
def get_institution_endpoint(
    institution_id: str = Path(..., min_length = 1, max_length = 120),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(get_current_user)
):
    '''
        Endpoint to retrieve a single institution.
    '''
    message = f'Retrieving institution id={institution_id}'
    logger.info(message)
    return get_institution_controller(
        dynamodb_resource = dynamodb_resource,
        institution_id = institution_id
    )


@router.patch(
    '/{institution_id}/cupos',
    response_model = InstitutionResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Update institution cupos',
    description = (
        'Updates the participant quota (cupos) assigned to an institution. This '
        'parametric quota drives the ETL load limit. Restricted to ADMIN.'
    )
)
def update_institution_cupos_endpoint(
    payload: InstitutionCuposUpdateSchema,
    institution_id: str = Path(..., min_length = 1, max_length = 120),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(RoleEnum.ADMIN.value))
):
    '''
        Endpoint to update an institution's participant quota.
    '''
    message = f'Updating cupos for institution id={institution_id}'
    logger.info(message)
    return update_institution_cupos_controller(
        dynamodb_resource = dynamodb_resource,
        institution_id = institution_id,
        payload = payload
    )


@router.patch(
    '/{institution_id}',
    response_model = InstitutionResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Update an institution',
    description = (
        'Updates the editable attributes of an institution (name, abbreviation, '
        'category, cupos). Restricted to ADMIN.'
    )
)
def update_institution_endpoint(
    payload: InstitutionUpdateSchema,
    institution_id: str = Path(..., min_length = 1, max_length = 120),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(RoleEnum.ADMIN.value))
):
    '''
        Endpoint to update an institution.
    '''
    message = f'Updating institution id={institution_id}'
    logger.info(message)
    return update_institution_controller(
        dynamodb_resource = dynamodb_resource,
        institution_id = institution_id,
        payload = payload
    )


@router.delete(
    '/{institution_id}',
    status_code = status.HTTP_204_NO_CONTENT,
    summary = 'Delete an institution',
    description = 'Removes an institution from the catalog. Restricted to ADMIN.'
)
def delete_institution_endpoint(
    institution_id: str = Path(..., min_length = 1, max_length = 120),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(RoleEnum.ADMIN.value))
):
    '''
        Endpoint to delete an institution.
    '''
    message = f'Deleting institution id={institution_id}'
    logger.info(message)
    delete_institution_controller(
        dynamodb_resource = dynamodb_resource,
        institution_id = institution_id
    )
