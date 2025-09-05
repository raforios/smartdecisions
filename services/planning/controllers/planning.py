'''
    Planning controllers.
'''
import asyncio
import json
import time
from typing import Any, Dict, List, Optional, Union
from datetime import date
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException, Request
from services.crud import get_record
from services.planning import (
    assign_material_to_planning_detail,
    bulk_create_planning,
    create_planning_detail,
    delete_material_by_id,
    delete_planning_by_id,
    delete_planning_detail_by_id,
    get_filtered_plannings,
    get_materials_by_detail_id,
    get_plannings_by_week,
    get_plannings_by_date,
    create_planning_with_details,
    update_material_quantities,
    update_planning_detail,
    update_planning_with_details
)
from services.utils import UsageLogData, handle_service_errors, send_audit_event, send_usage_log
from services.logger_config import custom_logger as logger
from models.planning import (
    Planning,
    PlanningDetail
)
from schemas.planning import (
    MaterialAssignmentResponseSchema,
    MaterialAssignmentSchema,
    MaterialAssignmentUpdateSchema,
    PlanningCreateSchema,
    PlanningDetailCreateSchema,
    PlanningDetailResponseSchema,
    PlanningDetailUpdateSchema,
    PlanningFilterSchema,
    PlanningResponseSchema,
    PlanningUpdateSchema
)

@handle_service_errors('PLANNING')
async def create_planning_controller(
    planning_data: PlanningCreateSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> PlanningResponseSchema:
    '''
        Controller to create a new planning.
    '''
    planning = await create_planning_with_details(db = db, planning_data = planning_data)

    response_data = planning_data.model_dump(exclude_unset = True)
    response_data['id'] = planning.id
    response_data['created_at'] = planning.created_at

    return PlanningResponseSchema.model_validate(response_data, from_attributes = True)

@handle_service_errors('PLANNING')
async def get_planning_by_id_controller(
    planning_id: int,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> PlanningResponseSchema:
    '''
        Controller to retrieve a planning by its ID.
    '''
    eager_options = [
        joinedload(Planning.details).joinedload(PlanningDetail.materials)
    ]
    planning = get_record(db, Planning, planning_id, eager_load_options = eager_options)
    return PlanningResponseSchema.model_validate(planning, from_attributes = True)

@handle_service_errors('PLANNING')
async def update_planning_controller(
    planning_id: int,
    planning_data: PlanningUpdateSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> Union[PlanningResponseSchema, dict]:
    '''
        Controller to update an existing planning record.
    '''
    planning = await update_planning_with_details(
        db = db,
        planning_id = planning_id,
        planning_data = planning_data
    )
    return PlanningResponseSchema.model_validate(planning, from_attributes = True)

@handle_service_errors('PLANNING')
async def get_weekly_plannings_controller(
    week_number: int,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> List[PlanningResponseSchema]:
    '''
        Controller to get all plannings for a specific week.
    '''
    plannings = await get_plannings_by_week(db = db, week_number = week_number)
    return [PlanningResponseSchema.model_validate(p, from_attributes = True) for p in plannings]

@handle_service_errors('PLANNING')
async def get_daily_plannings_controller(
    date_to_filter: date,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> List[PlanningResponseSchema]:
    '''
        Controller to get all plannings for a specific date.
    '''
    plannings = await get_plannings_by_date(db = db, planning_date = date_to_filter)
    return [PlanningResponseSchema.model_validate(p, from_attributes = True) for p in plannings]

@handle_service_errors('PLANNING')
async def create_planning_detail_controller(
    detail_data: PlanningDetailCreateSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> PlanningDetailResponseSchema:
    '''
        Controller to create a new planning detail for an existing planning.
    '''
    detail = await create_planning_detail(db = db, detail_data = detail_data)
    return PlanningDetailResponseSchema.model_validate(detail, from_attributes = True)

@handle_service_errors('PLANNING')
async def delete_planning_controller(
    planning_id: int,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> dict:
    '''
        Controller to delete a planning by its ID.
    '''
    result = await delete_planning_by_id(
        db = db,
        planning_id = planning_id
    )
    return {
        'message': f'Planning with ID {result} deleted successfully.',
        'id': result
    }

@handle_service_errors('PLANNING')
async def get_materials_controller(
    planning_detail_id: int,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument # pylint: disable=unused-argument
) -> List[MaterialAssignmentResponseSchema]:
    '''
        Controller to retrieve all materials for a specific planning detail.
    '''
    materials = await get_materials_by_detail_id(
        db = db,
        planning_detail_id = planning_detail_id
    )
    return [MaterialAssignmentResponseSchema.model_validate(m,
                                        from_attributes = True) for m in materials]

@handle_service_errors('PLANNING')
async def assign_material_controller(
    planning_detail_id: int,
    material_data: MaterialAssignmentSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> MaterialAssignmentResponseSchema:
    '''
        Controller to assign a material to a planning detail.
    '''
    material = await assign_material_to_planning_detail(
        db = db,
        planning_detail_id = planning_detail_id,
        material_data = material_data
    )
    return MaterialAssignmentResponseSchema.model_validate(material,
                                                           from_attributes = True)

@handle_service_errors('PLANNING')
async def update_material_controller(
    material_assignment_id: int,
    material_data: MaterialAssignmentUpdateSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> MaterialAssignmentResponseSchema:
    '''
        Controller to update a material assignment record.
    '''
    material = await update_material_quantities(
        db = db,
        material_assignment_id = material_assignment_id,
        update_data = material_data
    )
    return MaterialAssignmentResponseSchema.model_validate(material,
                                                           from_attributes = True)

@handle_service_errors('PLANNING')
async def delete_material_controller(
    material_assignment_id: int,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> dict:
    '''
        Controller to delete a material assignment by its ID.
    '''
    result = await delete_material_by_id(
        db = db,
        material_assignment_id = material_assignment_id
    )
    return {
        'message': f'Material assignment {result} deleted successfully.',
        'id': result
    }

@handle_service_errors('PLANNING')
async def get_filtered_plannings_controller(
    db: Session,
    filters: PlanningFilterSchema,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> List[PlanningResponseSchema]:
    '''
        Controller to get plannings by a single, exclusive filter criterion.
    '''
    plannings = await get_filtered_plannings(
        db = db,
        filters = filters
    )
    return [PlanningResponseSchema.model_validate(p, from_attributes = True) for p in plannings]

@handle_service_errors('PLANNING')
async def delete_planning_detail_controller(
    planning_detail_id: int,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> dict:
    '''
        Controller to delete a planning detail record.
    '''
    result = await delete_planning_detail_by_id(
        db = db,
        planning_detail_id = planning_detail_id
    )
    return {
        'message': f'Planning detail {result} deleted successfully.',
        'id': result
    }

@handle_service_errors('PLANNING')
async def update_planning_detail_controller(
    planning_detail_id: int,
    update_data: PlanningDetailUpdateSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> Union[PlanningDetailResponseSchema, dict]:
    '''
        Controller to update a planning detail record.
    '''
    detail = await update_planning_detail(
        db = db,
        planning_detail_id = planning_detail_id,
        update_data = update_data
    )
    return PlanningDetailResponseSchema.model_validate(detail, from_attributes = True)

async def bulk_upload_planning_controller(
    request: Request,
    db: Session,
    file_name: str,
    current_user: str,
    delimiter: Optional[str] = ',',
    auth_token: str = None,
) -> Dict[str, Any]:
    '''
        Controller to handle the bulk upload of planning data from a CSV file.
    '''
    logger.info(f'Starting bulk upload for file: {file_name}')
    
    start_time = time.perf_counter()
    status_code = 201
    
    try:
        result = await bulk_create_planning(
            db = db,
            file_name = file_name,
            delimiter = delimiter,
            auth_token = auth_token
        )
        
        # ✅ Llama a las funciones de auditoría y logs.
        # Enviar evento de auditoría.
        audit_event_data = {
            'microservice': 'PLANNING',
            'entity_name': 'Planning',
            'entity_id': 0,
            'action': 'BULK_CREATE',
            'user_id': 'usr_test',
            'old_values': None,
            'new_values': json.dumps(result)
        }
        asyncio.create_task(send_audit_event(audit_event_data))

    except HTTPException as e:
        status_code = e.status_code
        result = {'detail': str(e.detail)}
        raise e
    
    finally:
        # Enviar log de uso
        end_time = time.perf_counter()
        log_data = UsageLogData(
            microservice = 'PLANNING',
            endpoint = request.url.path,
            method = request.method,
            status_code = status_code,
            ip_address = request.client.host,
            user_id = current_user,
            request_body = {'file_name': file_name},
            response_body = result,
            response_time_ms = int((end_time - start_time) * 1000)
        )
        asyncio.create_task(send_usage_log(log_data.model_dump()))
        
    return result