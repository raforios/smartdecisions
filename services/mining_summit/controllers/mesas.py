'''
    Mesas controllers.
'''
from schemas.mesas import (
    AxesListResponseSchema,
    AxisResponseSchema,
    MesaQuerySchema,
    MesaResponseSchema,
    MesasListResponseSchema
)
from services.mesas import list_axes, list_mesas
from services.utils import handle_service_errors


@handle_service_errors
def list_mesas_controller(query_params: MesaQuerySchema) -> MesasListResponseSchema:
    '''
        Controller to retrieve the mesas allocated to the thematic axes, with
        the total seat capacity, optionally filtered by axis.
    '''
    axis = query_params.axis.value if query_params.axis else None
    records = list_mesas(axis = axis)
    return MesasListResponseSchema(
        items = [MesaResponseSchema(**record) for record in records],
        total_capacity = sum(record['capacity'] for record in records)
    )


@handle_service_errors
def list_axes_controller() -> AxesListResponseSchema:
    '''
        Controller to retrieve the six thematic axes with their mesa allocation
        and aggregated capacity, plus summit-wide totals.
    '''
    records = list_axes()
    return AxesListResponseSchema(
        items = [AxisResponseSchema(**record) for record in records],
        total_mesas = sum(record['mesas'] for record in records),
        total_capacity = sum(record['capacity'] for record in records)
    )
