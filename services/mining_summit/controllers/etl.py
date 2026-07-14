'''
    ETL controllers.
'''
from boto3.resources.base import ServiceResource

from schemas.etl import EtlLoadResponseSchema, ResponsibleSchema
from services.etl import load_participants_from_excel
from services.utils import handle_service_errors


@handle_service_errors
def load_participants_controller(
    dynamodb_resource: ServiceResource,
    file_bytes: bytes,
    institution_id: str,
    responsible: ResponsibleSchema,
    role: str
) -> EtlLoadResponseSchema:
    '''
        Controller that runs the participant batch load for a single institution
        file and returns the accreditation summary. Restricted to ADMIN at the
        route layer.
    '''
    summary = load_participants_from_excel(
        dynamodb_resource = dynamodb_resource,
        file_bytes = file_bytes,
        institution_id = institution_id,
        responsible = responsible.model_dump(),
        role = role
    )
    return EtlLoadResponseSchema(**summary)
