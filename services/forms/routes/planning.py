'''
    Planning: routes handler
'''
from typing import Any, Dict, List, Optional
from datetime import date
from fastapi import APIRouter, Depends, Header, Query, Request, status, Path
from sqlalchemy.orm import Session
from services.db_connection import GET_DB_DEPENDENCY
from services.security import get_current_user
from services.logger_config import custom_logger as logger
from controllers.planning import (
    bulk_upload_planning_controller,
    create_planning_controller,
    create_planning_detail_controller,
    delete_planning_controller,
    delete_planning_detail_controller,
    get_filtered_plannings_controller,
    get_monitor_data_controller,
    get_planning_by_id_controller,
    update_planning_controller,
    get_weekly_plannings_controller,
    get_daily_plannings_controller,
    update_planning_detail_controller
)
from schemas.planning import (
    BulkUploadResponseSchema,
    PlanningCreateSchema,
    PlanningDetailBaseSchema,
    PlanningDetailCreateSchema,
    PlanningDetailResponseSchema,
    PlanningDetailUpdateSchema,
    PlanningFilterSchema,
    PlanningMonitorFilterSchema,
    PlanningResponseSchema,
    PlanningUpdateSchema
)

router = APIRouter(prefix = '/v1/planning', tags = ['Planning'])

@router.post(
    '/',
    response_model = PlanningResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Create a new planning',
    description = 'Creates a new planning record with general information.'
)
async def create_planning_endpoint(
    planning_data: PlanningCreateSchema,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to create a new planning.
    '''
    message = f'User: {current_user}. Received request to create planning.'
    logger.info(message)
    return await create_planning_controller(
        planning_data = planning_data,
        db = db,
        request = request,
        current_user = current_user
    )

@router.get(
    '/filter',
    response_model = List[PlanningResponseSchema],
    status_code = status.HTTP_200_OK,
    summary = 'Filter plannings by an exclusive criterion',
    description = '''Retrieves a list of plannings based on a single, exclusive filter.
    Only one query parameter can be provided at a time.'''
)
async def get_filtered_plannings_endpoint(
    request: Request,
    filters: PlanningFilterSchema = Depends(),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to search plannings by a single filter.
    '''
    message = f'User: {current_user}. Received request to filter plannings. Filters: company_id = {
        filters.company_id}, team_id = {filters.team_id}, service_id = {
        filters.service_id}, planned_route_id = {filters.planned_route_id}'
    logger.info(message)

    return await get_filtered_plannings_controller(
        db = db,
        filters = filters,
        request = request,
        current_user = current_user
    )

@router.get(
    '/daily',
    response_model = List[PlanningResponseSchema],
    status_code = status.HTTP_200_OK,
    summary = 'Get planning details for a date range',
    description = 'Retrieves all planning detail records that are active within a given date range.'
)
async def get_daily_plannings_endpoint(
    request: Request,
    start_date: date = Query(..., description = 'Start date of the range in YYYY-MM-DD format.'),
    end_date: date = Query(..., description = 'End date of the range in YYYY-MM-DD format.'),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to get plannings by date.
    '''
    message = f'User: {current_user}. Received request to get planning details for date range from {
            start_date} to {end_date}.'
    logger.info(message)
    return await get_daily_plannings_controller(
        db = db,
        start_date = start_date,
        end_date = end_date,
        request = request,
        current_user = current_user
    )

@router.get(
    '/monitor-filter',
    response_model = List[Dict[str, Any]],
    status_code = status.HTTP_200_OK,
    summary = 'Filter planning details for the Affiliation Monitor',
    description = '''Retrieves a list of planned route IDs and other details
                 based on complex filtering criteria for the Affiliation Monitor.'''
)
async def get_monitor_data_endpoint(
    request: Request,
    filters: PlanningMonitorFilterSchema = Depends(),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    '''
        Endpoint to get planned routes for the Affiliation Monitor report.
    '''
    return await get_monitor_data_controller(
        db = db,
        request = request,
        filters = filters,
        current_user = current_user
    )

@router.get(
    '/{planning_id}',
    response_model = PlanningResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Get a planning by ID',
    description = 'Retrieves a single planning record with its details by its unique ID.'
)
async def get_planning_by_id_endpoint(
    request: Request,
    planning_id: int = Path(..., gt = 0),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to retrieve a specific planning.
    '''
    message = f'User: {current_user}. Received request to get planning with ID: {planning_id}'
    logger.info(message)
    return await get_planning_by_id_controller(
        db = db,
        planning_id = planning_id,
        request = request,
        current_user = current_user
    )

@router.put(
    '/{planning_id}',
    response_model = PlanningResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Update a planning',
    description = 'Updates an existing planning record by its unique ID.'
)
async def update_planning_endpoint(
    request: Request,
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
    return await update_planning_controller(
        db = db,
        planning_id = planning_id,
        planning_data = planning_data,
        request = request,
        current_user = current_user
    )

@router.get(
    '/weekly/{week_number}',
    response_model = List[PlanningResponseSchema],
    status_code = status.HTTP_200_OK,
    summary = 'Get plannings for a specific week',
    description = 'Retrieves all planning records for a given week number.'
)
async def get_weekly_plannings_endpoint(
    request: Request,
    week_number: int = Path(..., ge = 1, le = 53),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to get plannings by week number.
    '''
    message = f'User: {current_user}. Received request to get weekly plannings for week {
        week_number}.'
    logger.info(message)
    return await get_weekly_plannings_controller(
        db = db,
        week_number = week_number,
        request = request,
        current_user = current_user
    )

@router.post(
    '/{planning_id}/details',
    response_model = PlanningDetailResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Create a new planning detail',
    description = 'Creates a new planning detail for an existing planning.'
)
async def create_planning_detail_endpoint(
    request: Request,
    detail_data: PlanningDetailBaseSchema,
    planning_id: int = Path(..., gt = 0),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to create a new planning detail.
    '''
    message = f'User: {current_user}. Received request to create planning detail for planning ID: {
            planning_id}'
    logger.info(message)

    detail_with_id = PlanningDetailCreateSchema(
        planning_id = planning_id, **detail_data.model_dump()
    )

    return await create_planning_detail_controller(
        db = db,
        detail_data = detail_with_id,
        request = request,
        current_user = current_user
    )

@router.delete(
    '/{planning_id}',
    status_code = status.HTTP_200_OK,
    summary = 'Delete a planning by ID',
    description = '''Deletes a planning record and all associated data by its ID,
                but only if its status is ACTIVE.'''
)
async def delete_planning_endpoint(
    request: Request,
    planning_id: int = Path(..., gt = 0),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to delete a specific planning.
    '''
    message = f'User: {current_user}. Received request to delete planning with ID: {planning_id}'
    logger.info(message)
    return await delete_planning_controller(
        db = db,
        planning_id = planning_id,
        request = request,
        current_user = current_user
    )

@router.patch(
    '/{planning_id}/details/{planning_detail_id}',
    response_model = PlanningDetailResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Update a planning detail',
    description = 'Updates a specific planning detail record with partial data.'
)
async def update_planning_detail_endpoint(
    request: Request,
    planning_id: int = Path(..., gt = 0),
    planning_detail_id: int = Path(..., gt = 0),
    detail_data: PlanningDetailUpdateSchema = ...,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):# pylint: disable=too-many-arguments, too-many-positional-arguments
    '''
        Endpoint to update a planning detail.
    '''
    message = f'User: {current_user}. Received request to update planning detai ID: {
        planning_detail_id} for planning ID: {planning_id}'
    logger.info(message)

    return await update_planning_detail_controller(
        db = db,
        planning_detail_id = planning_detail_id,
        update_data = detail_data,
        request = request,
        current_user = current_user
    )

@router.delete(
    '/{planning_id}/details/{planning_detail_id}',
    status_code = status.HTTP_200_OK,
    summary = 'Delete a planning detail',
    description = 'Deletes a specific planning detail record.'
)
async def delete_planning_detail_endpoint(
    request: Request,
    planning_id: int = Path(..., gt = 0),
    planning_detail_id: int = Path(..., gt = 0),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to delete a planning detail.
    '''
    message = f'User: {current_user}. Received request to delete planning detail ID:{
        planning_detail_id} and ID plan: {planning_id}'
    logger.info(message)
    return await delete_planning_detail_controller(
        db = db,
        planning_detail_id = planning_detail_id,
        request = request,
        current_user = current_user
    )

@router.post(
    '/bulk-upload',
    response_model = BulkUploadResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Bulk upload plannings from a CSV file',
    description = '''Processes a CSV file from the FILES microservice to create planning
                 and their associated details in a single, atomic operation.'''
)

# pylint: disable=too-many-arguments, too-many-positional-arguments
async def bulk_upload_planning_endpoint(
    request: Request,
    file_name: str = Query(..., description = 'Name of the CSV file to process.'),
    delimiter: Optional[str] = Query(
        ',', description = 'The delimiter used in the CSV file. Defaults to a comma (,).'
    ),
    db: Session = Depends(GET_DB_DEPENDENCY),
    auth_token: str = Header(..., alias = 'Authorization'),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to trigger a bulk upload of planning data from a CSV file.
    '''
    message = f'User: {current_user}. Received request for bulk upload from file: {file_name}'
    logger.info(message)
    return await bulk_upload_planning_controller(
        db = db,
        file_name = file_name,
        delimiter = delimiter,
        auth_token = auth_token,
        request = request,
        current_user = current_user
    )
