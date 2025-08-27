'''
    Planning controllers.
'''
from typing import List
from datetime import date
from sqlalchemy.orm import Session, joinedload
from services.crud import get_record
from services.planning import (
    assign_material_to_planning_detail,
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
from services.utils import handle_service_errors
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

@handle_service_errors
def create_planning_controller(
    planning_data: PlanningCreateSchema,
    db: Session
) -> PlanningResponseSchema:
    '''
        Controller to create a new planning.
    '''
    planning = create_planning_with_details(db = db, planning_data = planning_data)
    return PlanningResponseSchema.model_validate(planning, from_attributes = True)

@handle_service_errors
def get_planning_by_id_controller(
    planning_id: int,
    db: Session
) -> PlanningResponseSchema:
    '''
        Controller to retrieve a planning by its ID.
    '''
    eager_options = [
        joinedload(Planning.details).joinedload(PlanningDetail.materials)
    ]
    planning = get_record(db, Planning, planning_id, eager_load_options = eager_options)
    return PlanningResponseSchema.model_validate(planning, from_attributes = True)

@handle_service_errors
def update_planning_controller(
    planning_id: int,
    planning_data: PlanningUpdateSchema,
    db: Session
) -> PlanningResponseSchema:
    '''
        Controller to update an existing planning record.
    '''
    planning = update_planning_with_details(
        db = db,
        planning_id = planning_id,
        planning_data = planning_data
    )
    return PlanningResponseSchema.model_validate(planning, from_attributes = True)

@handle_service_errors
def get_weekly_plannings_controller(
    week_number: int,
    db: Session
) -> List[PlanningResponseSchema]:
    '''
        Controller to get all plannings for a specific week.
    '''
    plannings = get_plannings_by_week(db = db, week_number = week_number)
    return [PlanningResponseSchema.model_validate(p, from_attributes = True) for p in plannings]

@handle_service_errors
def get_daily_plannings_controller(
    date_to_filter: date,
    db: Session
) -> List[PlanningResponseSchema]:
    '''
        Controller to get all plannings for a specific date.
    '''
    plannings = get_plannings_by_date(db = db, planning_date = date_to_filter)
    return [PlanningResponseSchema.model_validate(p, from_attributes = True) for p in plannings]

@handle_service_errors
def create_planning_detail_controller(
    detail_data: PlanningDetailCreateSchema,
    db: Session
) -> PlanningDetailResponseSchema:
    '''
        Controller to create a new planning detail for an existing planning.
    '''
    detail = create_planning_detail(db=db, detail_data = detail_data)
    return PlanningDetailResponseSchema.model_validate(detail, from_attributes = True)

@handle_service_errors
def delete_planning_controller(
    planning_id: int,
    db: Session
) -> dict:
    '''
        Controller to delete a planning by its ID.
    '''
    return delete_planning_by_id(db=db, planning_id=planning_id)

@handle_service_errors
def get_materials_controller(
    planning_detail_id: int,
    db: Session
) -> List[MaterialAssignmentResponseSchema]:
    '''
        Controller to retrieve all materials for a specific planning detail.
    '''
    materials = get_materials_by_detail_id(db = db, planning_detail_id = planning_detail_id)
    return [MaterialAssignmentResponseSchema.model_validate(m,
                                        from_attributes = True) for m in materials]

@handle_service_errors
def assign_material_controller(
    planning_detail_id: int,
    material_data: MaterialAssignmentSchema,
    db: Session
) -> MaterialAssignmentResponseSchema:
    '''
        Controller to assign a material to a planning detail.
    '''
    material = assign_material_to_planning_detail(
        db = db,
        planning_detail_id = planning_detail_id,
        material_data = material_data
    )
    return MaterialAssignmentResponseSchema.model_validate(material, from_attributes = True)

@handle_service_errors
def update_material_controller(
    material_assignment_id: int,
    material_data: MaterialAssignmentUpdateSchema,
    db: Session
) -> MaterialAssignmentResponseSchema:
    '''
        Controller to update a material assignment record.
    '''
    material = update_material_quantities(
        db = db,
        material_assignment_id = material_assignment_id,
        update_data = material_data
    )
    return MaterialAssignmentResponseSchema.model_validate(material, from_attributes = True)

@handle_service_errors
def delete_material_controller(
    material_assignment_id: int,
    db: Session
) -> dict:
    '''
        Controller to delete a material assignment by its ID.
    '''
    return delete_material_by_id(
        db = db,
        material_assignment_id = material_assignment_id
    )

@handle_service_errors
def get_filtered_plannings_controller(
    db: Session,
    filters: PlanningFilterSchema
) -> List[PlanningResponseSchema]:
    '''
        Controller to get plannings by a single, exclusive filter criterion.
    '''
    plannings = get_filtered_plannings(
        db = db,
        company_id = filters.company_id,
        team_id = filters.team_id,
        service_id = filters.service_id,
        planned_route_id = filters.planned_route_id,
    )
    return [PlanningResponseSchema.model_validate(p, from_attributes = True) for p in plannings]

@handle_service_errors
def delete_planning_detail_controller(
    planning_detail_id: int,
    db: Session
) -> dict:
    '''
        Controller to delete a planning detail record.
    '''
    return delete_planning_detail_by_id(db=db, planning_detail_id=planning_detail_id)

@handle_service_errors
def update_planning_detail_controller(
    planning_detail_id: int,
    update_data: PlanningDetailUpdateSchema,
    db: Session
) -> PlanningDetailResponseSchema:
    '''
        Controller to update a planning detail record.
    '''
    # We convert the Pydantic schema to a dictionary, excluding fields that are None.
    data_to_update = update_data.model_dump(exclude_unset=True)
    detail = update_planning_detail(
        db = db,
        planning_detail_id = planning_detail_id,
        update_data = data_to_update
    )
    return PlanningDetailResponseSchema.model_validate(detail, from_attributes = True)
