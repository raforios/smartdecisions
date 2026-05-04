'''
    Attendances: routes handler.
'''
from fastapi import APIRouter, Depends, status
from boto3.resources.base import ServiceResource

from controllers.attendances import (
    list_attendances_controller,
    register_attendance_controller
)
from schemas.attendances import (
    AttendanceCreateSchema,
    AttendanceQuerySchema,
    AttendanceResponseSchema,
    AttendancesListResponseSchema
)
from services.db_connection import GET_DB_DEPENDENCY
from services.logger_config import custom_logger as logger
from services.security import get_current_user

router = APIRouter(prefix = '/v1/mining-summit/attendances', tags = ['Attendances'])


@router.post(
    '',
    response_model = AttendanceResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Register attendance for a CI',
    description = (
        'Registers a daily attendance. If the CI is not registered yet, '
        'the participant is created on-the-fly (first_name and last_name are '
        'required in that case).'
    )
)
def register_attendance_endpoint(
    payload: AttendanceCreateSchema,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to register an attendance.
    '''
    message = f'Registering attendance for ci={payload.ci}'
    logger.info(message)
    return register_attendance_controller(
        dynamodb_resource = dynamodb_resource,
        payload = payload,
        current_user = current_user
    )


@router.get(
    '',
    response_model = AttendancesListResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'List attendances',
    description = 'Returns attendances filtered by CI and/or date range.'
)
def list_attendances_endpoint(
    query_params: AttendanceQuerySchema = Depends(),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(get_current_user)
):
    '''
        Endpoint to retrieve the attendances list.
    '''
    message = 'Retrieving attendances list.'
    logger.info(message)
    return list_attendances_controller(
        dynamodb_resource = dynamodb_resource,
        query_params = query_params
    )
