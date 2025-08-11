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
    create_planning_controller,
    get_planning_by_id_controller,
    update_planning_controller,
    get_weekly_plannings_controller,
    get_daily_plannings_controller
)
from schemas.planning import (
    PlanningCreateSchema,
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
