'''
    API Routes for Planning Microservice.
'''
from typing import List
from datetime import date
from fastapi import APIRouter, Depends, status, Path
from sqlalchemy.orm import Session
from services.db_connection import GET_DB_DEPENDENCY
from services.security import get_current_user
from services.logger_config import custom_logger as logger
from controllers.planning import (
    assign_material_controller,
    create_planning_controller,
    create_planning_detail_controller,
    delete_material_controller,
    delete_planning_controller,
    delete_planning_detail_controller,
    get_filtered_plannings_controller,
    get_materials_controller,
    get_planning_by_id_controller,
    update_material_controller,
    update_planning_controller,
    get_weekly_plannings_controller,
    get_daily_plannings_controller,
    update_planning_detail_controller
)
from schemas.planning import (
    MaterialAssignmentResponseSchema,
    MaterialAssignmentSchema,
    MaterialAssignmentUpdateSchema,
    PlanningCreateSchema,
    PlanningDetailBaseSchema,
    PlanningDetailCreateSchema,
    PlanningDetailResponseSchema,
    PlanningDetailUpdateSchema,
    PlanningFilterSchema,
    PlanningResponseSchema,
    PlanningUpdateSchema
)

router = APIRouter(prefix = '/v1/plannings', tags = ['Planning'])

@router.post(
    '/',
    response_model = PlanningResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Create a new planning',
    description = 'Creates a new planning record with general information.'
)
def create_planning_endpoint(
    planning_data: PlanningCreateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to create a new planning.
    '''
    message = f'User: {current_user}. Received request to create planning.'
    logger.info(message)
    return create_planning_controller(planning_data, db)

@router.get(
    '/filter',
    response_model = List[PlanningResponseSchema],
    status_code = status.HTTP_200_OK,
    summary = 'Filter plannings by an exclusive criterion',
    description = '''Retrieves a list of plannings based on a single, exclusive filter.
    Only one query parameter can be provided at a time.'''
)
def get_filtered_plannings_endpoint(
    filters: PlanningFilterSchema = Depends(),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to search plannings by a single filter.
    '''
    message = f'''User: {current_user}. Received request to filter plannings.
            Filters: company_id = {filters.company_id}, team_id = {filters.team_id},
            service_id = {filters.service_id}, planned_route_id = {filters.planned_route_id}'''
    logger.info(message)

    return get_filtered_plannings_controller(
        db = db,
        filters = filters
    )

@router.get(
    '/{planning_id}',
    response_model = PlanningResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Get a planning by ID',
    description = 'Retrieves a single planning record with its details by its unique ID.'
)
def get_planning_by_id_endpoint(
    planning_id: int = Path(..., gt = 0),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to retrieve a specific planning.
    '''
    message = f'User: {current_user}. Received request to get planning with ID: {planning_id}'
    logger.info(message)
    return get_planning_by_id_controller(planning_id, db)

@router.put(
    '/{planning_id}',
    response_model = PlanningResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Update a planning',
    description = 'Updates an existing planning record by its unique ID.'
)
def update_planning_endpoint(
    planning_id: int = Path(..., gt = 0),
    planning_data: PlanningUpdateSchema = ...,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to update an existing planning.
    '''
    message = f'User: {current_user}. Received request to update planning with ID: {planning_id}'
    logger.info(message)
    return update_planning_controller(planning_id, planning_data, db)

@router.get(
    '/weekly/{week_number}',
    response_model = List[PlanningResponseSchema],
    status_code = status.HTTP_200_OK,
    summary = 'Get plannings for a specific week',
    description = 'Retrieves all planning records for a given week number.'
)
def get_weekly_plannings_endpoint(
    week_number: int = Path(..., ge = 1, le = 53),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to get plannings by week number.
    '''
    message = f'''User: {current_user}. Received request to get weekly plannings
            for week {week_number}.'''
    logger.info(message)
    return get_weekly_plannings_controller(week_number, db)

@router.get(
    '/daily/{planning_date}',
    response_model = List[PlanningResponseSchema],
    status_code = status.HTTP_200_OK,
    summary = 'Get plannings for a specific date',
    description = 'Retrieves all planning records that are active on a given date.'
)
def get_daily_plannings_endpoint(
    planning_date: date = Path(..., description = 'Date in YYYY-MM-DD format'),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to get plannings by date.
    '''
    message = f'''User: {current_user}. Received request to get daily plannings
            for date {planning_date}.'''
    logger.info(message)
    return get_daily_plannings_controller(planning_date, db)

@router.post(
    '/{planning_id}/details',
    response_model = PlanningDetailResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Create a new planning detail',
    description = 'Creates a new planning detail for an existing planning.'
)
def create_planning_detail_endpoint(
    detail_data: PlanningDetailBaseSchema,
    planning_id: int = Path(..., gt = 0),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to create a new planning detail.
    '''
    message = f'''User: {current_user}. Received request to create planning
            detail for planning ID: {planning_id}'''
    logger.info(message)

    detail_with_id = PlanningDetailCreateSchema(
        planning_id = planning_id, **detail_data.model_dump()
    )

    return create_planning_detail_controller(detail_with_id, db)

@router.delete(
    '/{planning_id}',
    status_code = status.HTTP_200_OK,
    summary = 'Delete a planning by ID',
    description = '''Deletes a planning record and all associated data by its ID,
                but only if its status is CREATED.'''
)
def delete_planning_endpoint(
    planning_id: int = Path(..., gt=0),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to delete a specific planning.
    '''
    message = f'User: {current_user}. Received request to delete planning with ID: {planning_id}'
    logger.info(message)
    return delete_planning_controller(planning_id, db)

@router.get(
    '/{planning_id}/details/{planning_detail_id}/materials',
    response_model = List[MaterialAssignmentSchema],
    status_code = status.HTTP_200_OK,
    summary = 'Get all material assignments for a planning detail',
    description = '''Retrieves all material assignments associated with a specific
                planning detail record.'''
)
def get_materials_endpoint(
    planning_detail_id: int = Path(..., gt = 0),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to retrieve materials for a planning detail.
    '''
    message = f'''User: {current_user}. Received request to get materials for planning
            detail ID: {planning_detail_id}'''
    logger.info(message)
    return get_materials_controller(planning_detail_id, db)

@router.post(
    '/{planning_id}/details/{planning_detail_id}/materials',
    response_model = MaterialAssignmentResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Assign material to a planning detail',
    description = 'Assigns a new material record to a specific planning detail.'
)
def assign_material_endpoint(
    planning_id: int = Path(..., gt = 0),
    planning_detail_id: int = Path(..., gt = 0),
    material_data: MaterialAssignmentSchema = ...,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to assign a new material.
    '''
    message = f'''User: {current_user}. Received request to assign material to planning detail
            ID: {planning_detail_id} and planning ID: {planning_id}'''
    logger.info(message)
    return assign_material_controller(planning_detail_id, material_data, db)

@router.patch(
    '/{planning_id}/details/{planning_detail_id}/materials/{material_assignment_id}',
    response_model = MaterialAssignmentSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Update material quantities',
    description = 'Updates the used and returned quantities for a material assignment.'
)
def update_material_endpoint(
    material_assignment_id: int = Path(..., gt = 0),
    material_data: MaterialAssignmentUpdateSchema = ...,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to update a material assignment.
    '''
    message = f'''User: {current_user}. Received request to update material
            ID: {material_assignment_id}'''
    logger.info(message)
    return update_material_controller(material_assignment_id, material_data, db)

@router.patch(
    '/{planning_id}/details/{planning_detail_id}',
    response_model = PlanningDetailResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Update a planning detail',
    description = 'Updates a specific planning detail record with partial data.'
)
def update_planning_detail_endpoint(
    planning_id: int = Path(..., gt=0),
    planning_detail_id: int = Path(..., gt = 0),
    detail_data: PlanningDetailUpdateSchema = ...,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to update a planning detail.
    '''
    message = f'''User: {current_user}. Received request to update planning detai
            ID: {planning_detail_id} for planning ID: {planning_id}'''
    logger.info(message)

    return update_planning_detail_controller(
        planning_detail_id = planning_detail_id,
        update_data = detail_data,
        db = db
    )

@router.delete(
    '/{planning_id}/details/{planning_detail_id}/materials/{material_assignment_id}',
    status_code=status.HTTP_200_OK,
    summary='Delete a material assignment by ID',
    description = 'Deletes a specific material assignment record.'
)
def delete_material_endpoint(
    material_assignment_id: int = Path(..., gt=0),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to delete a material assignment.
    '''
    message = f'''User: {current_user}. Received request to delete material
            ID: {material_assignment_id}'''
    logger.info(message)
    return delete_material_controller(material_assignment_id, db)

@router.delete(
    '/{planning_id}/details/{planning_detail_id}',
    status_code = status.HTTP_200_OK,
    summary = 'Delete a planning detail',
    description = 'Deletes a specific planning detail record.'
)
def delete_planning_detail_endpoint(
    planning_id: int = Path(..., gt=0),
    planning_detail_id: int = Path(..., gt=0),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to delete a planning detail.
    '''
    message = f'''User: {current_user}. Received request to delete planning detail
            ID:{planning_detail_id} and ID plan: {planning_id}'''
    logger.info(message)
    return delete_planning_detail_controller(planning_detail_id, db)
