'''
    Institutions controllers.
'''
from boto3.resources.base import ServiceResource

from schemas.institutions import (
    InstitutionQuerySchema,
    InstitutionResponseSchema,
    InstitutionsListResponseSchema
)
from services.institutions import get_institution, list_institutions
from services.utils import handle_service_errors


@handle_service_errors
def list_institutions_controller(
    dynamodb_resource: ServiceResource,
    query_params: InstitutionQuerySchema
) -> InstitutionsListResponseSchema:
    '''
        Controller to retrieve the institutions catalog with optional
        category/role filters, plus the summed planned cupos.
    '''
    category = query_params.category.value if query_params.category else None
    role = query_params.role.value if query_params.role else None
    records = list_institutions(
        dynamodb_resource = dynamodb_resource,
        category = category,
        role = role
    )
    return InstitutionsListResponseSchema(
        items = [InstitutionResponseSchema(**record) for record in records],
        total_cupos = sum(record['cupos'] for record in records)
    )


@handle_service_errors
def get_institution_controller(
    dynamodb_resource: ServiceResource,
    institution_id: str
) -> InstitutionResponseSchema:
    '''
        Controller to retrieve a single institution by its slug identifier.
    '''
    record = get_institution(
        dynamodb_resource = dynamodb_resource,
        institution_id = institution_id
    )
    return InstitutionResponseSchema(**record)
