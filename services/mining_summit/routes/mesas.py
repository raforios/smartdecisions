'''
    Mesas and thematic axes: routes handler.
'''
from fastapi import APIRouter, Depends, status

from controllers.mesas import list_axes_controller, list_mesas_controller
from schemas.mesas import (
    AxesListResponseSchema,
    MesaQuerySchema,
    MesasListResponseSchema
)
from services.logger_config import custom_logger as logger
from services.security import get_current_user

router = APIRouter(prefix = '/v1/mining-summit', tags = ['Mesas'])


@router.get(
    '/mesas',
    response_model = MesasListResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'List working tables (mesas)',
    description = (
        'Returns the fixed campus rooms (aulas ≡ mesas) allocated to the '
        'thematic axes, with each mesa capacity and the total seat capacity. '
        'Supports an optional axis filter.'
    )
)
def list_mesas_endpoint(
    query_params: MesaQuerySchema = Depends(),
    _: str = Depends(get_current_user)
):
    '''
        Endpoint to retrieve the mesas allocated to the thematic axes.
    '''
    message = 'Retrieving mesas allocation.'
    logger.info(message)
    return list_mesas_controller(query_params = query_params)


@router.get(
    '/axes',
    response_model = AxesListResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'List thematic axes',
    description = (
        'Returns the six thematic axes (ejes) with their allocated mesa count '
        'and aggregated seat capacity, plus summit-wide totals.'
    )
)
def list_axes_endpoint(_: str = Depends(get_current_user)):
    '''
        Endpoint to retrieve the thematic axes with their mesa allocation.
    '''
    message = 'Retrieving thematic axes.'
    logger.info(message)
    return list_axes_controller()
