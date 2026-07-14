'''
    Mesas controllers.
'''
from boto3.resources.base import ServiceResource

from schemas.mesas import (
    AxesListResponseSchema,
    AxisResponseSchema,
    MesaCreateSchema,
    MesaQuerySchema,
    MesaResponseSchema,
    MesasListResponseSchema,
    MesaUpdateSchema
)
from services.mesas import (
    create_mesa,
    delete_mesa,
    list_axes,
    list_mesas,
    update_mesa
)
from services.utils import handle_service_errors


@handle_service_errors
def list_mesas_controller(
    dynamodb_resource: ServiceResource,
    query_params: MesaQuerySchema
) -> MesasListResponseSchema:
    '''
        Controller to retrieve the mesas allocated to the thematic axes, with
        the total seat capacity, optionally filtered by axis.
    '''
    axis = query_params.axis.value if query_params.axis else None
    records = list_mesas(dynamodb_resource = dynamodb_resource, axis = axis)
    return MesasListResponseSchema(
        items = [MesaResponseSchema(**record) for record in records],
        total_capacity = sum(record['capacity'] for record in records)
    )


@handle_service_errors
def update_mesa_controller(
    dynamodb_resource: ServiceResource,
    code: str,
    payload: MesaUpdateSchema
) -> MesaResponseSchema:
    '''
        Controller to update the parametric attributes (capacity/axis) of an
        aula. Restricted to ADMIN at the route layer.
    '''
    record = update_mesa(
        dynamodb_resource = dynamodb_resource,
        code = code,
        capacity = payload.capacity,
        axis = payload.axis.value if payload.axis else None
    )
    return MesaResponseSchema(**record)


@handle_service_errors
def create_mesa_controller(
    dynamodb_resource: ServiceResource,
    payload: MesaCreateSchema
) -> MesaResponseSchema:
    '''
        Controller to register a new aula. Restricted to ADMIN at the route layer.
    '''
    record = create_mesa(
        dynamodb_resource = dynamodb_resource,
        payload = {**payload.model_dump(), 'axis': payload.axis.value}
    )
    return MesaResponseSchema(**record)


@handle_service_errors
def delete_mesa_controller(dynamodb_resource: ServiceResource, code: str) -> None:
    '''
        Controller to delete an aula. Restricted to ADMIN at the route layer.
    '''
    delete_mesa(dynamodb_resource = dynamodb_resource, code = code)


@handle_service_errors
def list_axes_controller(dynamodb_resource: ServiceResource) -> AxesListResponseSchema:
    '''
        Controller to retrieve the six thematic axes with their mesa allocation
        and aggregated capacity, plus summit-wide totals.
    '''
    records = list_axes(dynamodb_resource = dynamodb_resource)
    return AxesListResponseSchema(
        items = [AxisResponseSchema(**record) for record in records],
        total_mesas = sum(record['mesas'] for record in records),
        total_capacity = sum(record['capacity'] for record in records)
    )
