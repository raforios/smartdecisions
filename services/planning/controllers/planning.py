'''
    Planning controllers.
'''
from typing import List, Callable, Any
from datetime import date
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError
from services.logger_config import custom_logger as logger
from services.exceptions import RegisterNotFoundError
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
from models.planning import (
    MaterialAssignment,
    Planning,
    PlanningDetail
)
from schemas.planning import (
    MaterialAssignmentSchema,
    MaterialAssignmentUpdateSchema,
    PlanningCreateSchema,
    PlanningDetailCreateSchema,
    PlanningDetailUpdateSchema,
    PlanningFilterSchema,
    PlanningUpdateSchema
)

def _handle_controller_call(
    func: Callable,
    operation: str,
    *args: Any,
    **kwargs: Any
) -> Any:
    '''
        Generic utility function to handle common try/except blocks in controllers.
        
        Args:
            func (Callable): The function to be called (the core logic).
            operation (str): A string describing the operation for logging purposes.
            *args, **kwargs: Arguments to pass to the function.
    '''
    try:
        message = f'Starting controller operation: {operation}'
        logger.info(message)
        return func(*args, **kwargs)
    except (RegisterNotFoundError, SQLAlchemyError) as e:
        error_msg = f'Failed to {operation}: {e}'
        logger.error(error_msg, exc_info = True)
        raise e
    except Exception as e:
        error_msg = f'Unexpected error during {operation}: {e}'
        logger.critical(error_msg, exc_info = True)
        raise RuntimeError('An unexpected internal error occurred.') from e

def create_planning_controller(
    planning_data: PlanningCreateSchema,
    db: Session
) -> Planning:
    '''
        Controller to create a new planning.
    '''
    return _handle_controller_call(
        create_planning_with_details,
        'create planning',
        db = db,
        planning_data = planning_data
    )

def get_planning_by_id_controller(
    planning_id: int,
    db: Session
) -> Planning:
    '''
        Controller to retrieve a planning by its ID.
    '''
    def _fetch_planning():
        eager_options = [
            joinedload(Planning.details).joinedload(PlanningDetail.materials)
        ]
        return get_record(db, Planning, planning_id, eager_load_options=eager_options)

    return _handle_controller_call(
        _fetch_planning,
        f'fetch planning with ID {planning_id}'
    )

def update_planning_controller(
    planning_id: int,
    planning_data: PlanningUpdateSchema,
    db: Session
) -> Planning:
    '''
        Controller to update an existing planning record.
    '''
    return _handle_controller_call(
        update_planning_with_details,
        f'update planning with ID {planning_id}',
        db = db,
        planning_id = planning_id,
        planning_data = planning_data
    )

def get_weekly_plannings_controller(
    week_number: int,
    db: Session
) -> List[Planning]:
    '''
        Controller to get all plannings for a specific week.
    '''
    return _handle_controller_call(
        get_plannings_by_week,
        f'fetch weekly plannings for week {week_number}',
        db = db,
        week_number = week_number
    )

def get_daily_plannings_controller(
    date_to_filter: date,
    db: Session
) -> List[Planning]:
    '''
        Controller to get all plannings for a specific date.
    '''
    return _handle_controller_call(
        get_plannings_by_date,
        f'fetch daily plannings for date {date_to_filter}',
        db = db,
        planning_date = date_to_filter
    )

def create_planning_detail_controller(
    detail_data: PlanningDetailCreateSchema,
    db: Session
) -> PlanningDetail:
    '''
        Controller to create a new planning detail for an existing planning.
    '''
    return _handle_controller_call(
        create_planning_detail,
        'create planning detail',
        db = db,
        detail_data = detail_data
    )

def delete_planning_controller(
    planning_id: int,
    db: Session
) -> dict:
    '''
        Controller to delete a planning by its ID.
    '''
    return _handle_controller_call(
        delete_planning_by_id,
        f'delete planning with ID {planning_id}',
        db = db,
        planning_id = planning_id
    )

def get_materials_controller(
    planning_detail_id: int,
    db: Session
) -> List[MaterialAssignment]:
    '''
        Controller to retrieve all materials for a specific planning detail.
    '''
    return _handle_controller_call(
        get_materials_by_detail_id,
        f'fetch materials for planning detail {planning_detail_id}',
        db = db,
        planning_detail_id = planning_detail_id
    )

def assign_material_controller(
    planning_detail_id: int,
    material_data: MaterialAssignmentSchema,
    db: Session
) -> MaterialAssignment:
    '''
        Controller to assign a material to a planning detail.
    '''
    return _handle_controller_call(
        assign_material_to_planning_detail,
        f'assign material to planning detail {planning_detail_id}',
        db = db,
        planning_detail_id = planning_detail_id,
        material_data = material_data
    )

def update_material_controller(
    material_assignment_id: int,
    material_data: MaterialAssignmentUpdateSchema,
    db: Session
) -> MaterialAssignment:
    '''
        Controller to update a material assignment record.
    '''
    return _handle_controller_call(
        update_material_quantities,
        f'update material with ID {material_assignment_id}',
        db = db,
        material_assignment_id = material_assignment_id,
        update_data = material_data
    )

def delete_material_controller(
    material_assignment_id: int,
    db: Session
) -> dict:
    '''
        Controller to delete a material assignment by its ID.
    '''
    return _handle_controller_call(
        delete_material_by_id,
        f'delete material with ID {material_assignment_id}',
        db = db,
        material_assignment_id = material_assignment_id
    )

def get_filtered_plannings_controller(
    db: Session,
    filters: PlanningFilterSchema
) -> List[Planning]:
    '''
        Controller to get plannings by a single, exclusive filter criterion.
    '''
    return _handle_controller_call(
        get_filtered_plannings,
        'get filtered plannings',
        db = db,
        company_id = filters.company_id,
        team_id = filters.team_id,
        service_id = filters.service_id,
        planned_route_id = filters.planned_route_id,
    )

def delete_planning_detail_controller(
    planning_detail_id: int,
    db: Session
) -> dict:
    '''
        Controller to delete a planning detail record.
    
    '''
    return _handle_controller_call(
        delete_planning_detail_by_id,
        f'delete planning detail with ID {planning_detail_id}',
        db=db,
        planning_detail_id=planning_detail_id
    )

def update_planning_detail_controller(
    planning_detail_id: int,
    update_data: PlanningDetailUpdateSchema,
    db: Session
) -> PlanningDetail:
    '''
        Controller to update a planning detail record.
    '''
    # We convert the Pydantic schema to a dictionary, excluding fields that are None.
    data_to_update = update_data.model_dump(exclude_unset=True)

    return _handle_controller_call(
        update_planning_detail,
        f'update planning detail with ID {planning_detail_id}',
        db = db,
        planning_detail_id = planning_detail_id,
        update_data = data_to_update
    )
