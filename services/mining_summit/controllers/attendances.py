'''
    Attendances controllers.
'''
from typing import Any, Dict
from boto3.resources.base import ServiceResource

from schemas.attendances import (
    AttendanceCreateSchema,
    AttendanceQuerySchema,
    AttendanceResponseSchema,
    AttendancesListResponseSchema
)
from services.attendances import list_attendances, register_attendance
from services.utils import handle_service_errors


@handle_service_errors
def register_attendance_controller(
    dynamodb_resource: ServiceResource,
    payload: AttendanceCreateSchema,
    current_user: str
) -> AttendanceResponseSchema:
    '''
        Controller to register a daily attendance. Auto-creates the participant
        on-the-fly if the CI is not registered yet.
    '''
    saved, participant_created = register_attendance(
        dynamodb_resource = dynamodb_resource,
        payload = payload.model_dump(exclude_none = True),
        marked_by = current_user
    )
    return AttendanceResponseSchema(
        **saved,
        participant_created = participant_created
    )


@handle_service_errors
def list_attendances_controller(
    dynamodb_resource: ServiceResource,
    query_params: AttendanceQuerySchema
) -> AttendancesListResponseSchema:
    '''
        Controller to retrieve attendances with optional CI / date filters.
    '''
    response: Dict[str, Any] = list_attendances(
        dynamodb_resource = dynamodb_resource,
        query_params = query_params.model_dump(exclude_none = True)
    )
    return AttendancesListResponseSchema(
        items = [
            AttendanceResponseSchema(**record, participant_created = False)
            for record in response['items']
        ],
        last_evaluated_key = response.get('last_evaluated_key')
    )
