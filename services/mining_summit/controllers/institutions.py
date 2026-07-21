'''
    Institutions controllers.
'''
from boto3.resources.base import ServiceResource

from schemas.institutions import (
    InstitutionCreateSchema,
    InstitutionCuposUpdateSchema,
    InstitutionQuerySchema,
    InstitutionResponseSchema,
    InstitutionsListResponseSchema,
    InstitutionUpdateSchema
)
from services.institutions import (
    create_institution,
    delete_institution,
    get_institution,
    list_institutions,
    update_institution,
    update_institution_cupos
)
from services.participants import count_active_by_institution
from services.utils import handle_service_errors


@handle_service_errors
def list_institutions_controller(
    dynamodb_resource: ServiceResource,
    query_params: InstitutionQuerySchema
) -> InstitutionsListResponseSchema:
    '''
        Controller to retrieve the institutions catalog with an optional
        category filter, plus the summed planned cupos.
    '''
    category = query_params.category.value if query_params.category else None
    records = list_institutions(
        dynamodb_resource = dynamodb_resource,
        category = category
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
    # Attach live cupo occupancy so operators can see remaining quota.
    accredited = count_active_by_institution(
        dynamodb_resource = dynamodb_resource,
        institution_id = record['id']
    )
    record['accredited_count'] = accredited
    record['available_cupos'] = max(0, int(record['cupos']) - accredited)
    return InstitutionResponseSchema(**record)


@handle_service_errors
def update_institution_cupos_controller(
    dynamodb_resource: ServiceResource,
    institution_id: str,
    payload: InstitutionCuposUpdateSchema
) -> InstitutionResponseSchema:
    '''
        Controller to update an institution's participant quota (cupos).
        Restricted to ADMIN at the route layer.
    '''
    record = update_institution_cupos(
        dynamodb_resource = dynamodb_resource,
        institution_id = institution_id,
        cupos = payload.cupos
    )
    return InstitutionResponseSchema(**record)


@handle_service_errors
def create_institution_controller(
    dynamodb_resource: ServiceResource,
    payload: InstitutionCreateSchema
) -> InstitutionResponseSchema:
    '''
        Controller to register a new institution. Restricted to ADMIN.
    '''
    record = create_institution(
        dynamodb_resource = dynamodb_resource,
        payload = {**payload.model_dump(exclude_none = True), 'category': payload.category.value}
    )
    return InstitutionResponseSchema(**record)


@handle_service_errors
def update_institution_controller(
    dynamodb_resource: ServiceResource,
    institution_id: str,
    payload: InstitutionUpdateSchema
) -> InstitutionResponseSchema:
    '''
        Controller to update an institution's editable attributes. ADMIN only.
    '''
    fields = payload.model_dump(exclude_none = True)
    if 'category' in fields:
        fields['category'] = payload.category.value
    record = update_institution(
        dynamodb_resource = dynamodb_resource,
        institution_id = institution_id,
        fields = fields
    )
    return InstitutionResponseSchema(**record)


@handle_service_errors
def delete_institution_controller(
    dynamodb_resource: ServiceResource,
    institution_id: str
) -> None:
    '''
        Controller to delete an institution. Restricted to ADMIN.
    '''
    delete_institution(dynamodb_resource = dynamodb_resource, institution_id = institution_id)
