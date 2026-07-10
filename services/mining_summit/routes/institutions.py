'''
    Institutions: routes handler.
'''
from fastapi import APIRouter, Depends, Path, status

from controllers.institutions import (
    get_institution_controller,
    list_institutions_controller
)
from schemas.institutions import (
    InstitutionQuerySchema,
    InstitutionResponseSchema,
    InstitutionsListResponseSchema
)
from services.logger_config import custom_logger as logger
from services.security import get_current_user

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
    _: str = Depends(get_current_user)
):
    '''
        Endpoint to retrieve the institutions reference catalog.
    '''
    message = 'Retrieving institutions catalog.'
    logger.info(message)
    return list_institutions_controller(query_params = query_params)


@router.get(
    '/{institution_id}',
    response_model = InstitutionResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Get institution by id',
    description = 'Retrieves a single reference institution by its slug identifier.'
)
def get_institution_endpoint(
    institution_id: str = Path(..., min_length = 1, max_length = 120),
    _: str = Depends(get_current_user)
):
    '''
        Endpoint to retrieve a single institution.
    '''
    message = f'Retrieving institution id={institution_id}'
    logger.info(message)
    return get_institution_controller(institution_id = institution_id)
