'''
    Business logic services for the Planning Microservice.
'''
from typing import Any, List, Tuple, Dict
from datetime import date
from pydantic import BaseModel
from sqlalchemy import and_, extract, or_
from sqlalchemy.orm import Session, contains_eager, joinedload
from services.crud import (
    create_record,
    delete_record,
    get_record,
    update_record
)
from services.exceptions import (
    RegisterAlreadyExistsError,
    RegisterNotFoundError,
    InvalidInputError
)
from services.logger_config import custom_logger as logger
from services.utils import (
    _handle_files_service,
    handle_service_errors,
    audit_event,
    perform_bulk_upload,
    sqlalchemy_object_as_dict
)
from models.planning import (
    Planning, PlanningDetail,
    MaterialAssignment
)
from schemas.planning import (
    MaterialAssignmentSchema,
    MaterialAssignmentUpdateSchema,
    PlanningBulkCreateSchema,
    PlanningCreateSchema,
    PlanningDetailCreateSchema,
    PlanningDetailUpdateSchema,
    PlanningFilterSchema,
    PlanningMonitorFilterSchema,
    PlanningStatus,
    PlanningUpdateSchema
)

def _process_planning_csv_data(
    rows: List[Dict[str, Any]],
    bulk_schema: BaseModel
) -> Dict[str, Any]:
    '''
        Processes CSV data and groups it by planning name for insertion.
    '''
    plannings_to_create = {}
    for row in rows:
        try:
            row_data = bulk_schema(**row)
            planning_key = (
                row_data.planning_name,
                row_data.company_id,
                row_data.app_id
            )
            if planning_key not in plannings_to_create:
                plannings_to_create[planning_key] = {
                    'planning_data': row_data.model_dump(
                        exclude = {
                            'team_id',
                            'service_id',
                            'planned_route_id',
                            'date_of_day'
                        }),
                    'details_data': []
                }
            plannings_to_create[planning_key]['details_data'].append(
                row_data.model_dump(
                    exclude = {
                        'company_id',
                        'app_id',
                        'planning_name',
                        'description',
                        'start_date',
                        'end_date',
                        'week_number'
                    })
            )
        except (ValueError, TypeError) as e:
            raise InvalidInputError(
                detail = f'Invalid data format in row: {row}. Error: {e}'
            ) from e
    return plannings_to_create

async def _perform_atomic_db_insertion_for_planning(
    db: Session,
    plannings_to_create: Dict[str, Any],
    file_name: str,
    auth_token: str
) -> Dict[str, int]:
    '''
        Performs atomic database insertion for plannings and details.
    '''
    plannings_created = 0
    details_created = 0
    with db.begin_nested():
        for planning_key, data in plannings_to_create.items():
            if db.query(Planning).filter_by(
                planning_name = data['planning_data']['planning_name'],
                company_id = data['planning_data']['company_id']
            ).first():
                await _handle_files_service(
                    action = 'delete',
                    file_name = file_name,
                    auth_token = auth_token
                )
                raise RegisterAlreadyExistsError(
                    detail = f'Planning with name {planning_key[0]} already exists for company ID {
                        planning_key[1]}.'
                )

            planning = Planning(**data['planning_data'])
            db.add(planning)
            db.flush()
            details = [
                PlanningDetail(planning_id = planning.id, **detail)
                for detail in data['details_data']
            ]
            db.add_all(details)
            plannings_created += 1
            details_created += len(details)

    return {'plannings_created': plannings_created, 'details_created': details_created}

@handle_service_errors('PLANNING')
async def get_plannings_by_week(
    db: Session,
    week_number: int
) -> List[Planning]:
    '''
        Retrieves all plannings for a specific week number.
    '''
    message = f'Fetching plannings for week number {week_number}.'
    logger.info(message)
    plannings = db.query(Planning).filter(Planning.week_number == week_number).all()
    if not plannings:
        raise RegisterNotFoundError(
            detail = f'No plannings found for week number {week_number}.'
        )
    return plannings

@handle_service_errors('PLANNING')
async def get_plannings_by_date(
    db: Session,
    planning_date: date
) -> List[Planning]:
    '''
        Retrieves all plannings that are active on a specific date.
    '''
    message = f'Fetching plannings for date {planning_date}.'
    logger.info(message)
    plannings = db.query(Planning).filter(
        Planning.start_date <= planning_date,
        Planning.end_date >= planning_date
    ).all()
    if not plannings:
        raise RegisterNotFoundError(
            detail = f'No plannings found for date {planning_date}.'
        )
    return plannings

@handle_service_errors('PLANNING')
async def get_planning_details_in_date_range(
    db: Session,
    start_date: date,
    end_date: date
) -> List[Planning]:
    '''
        Retrieves all planning details that fall within a given date range,
        eager-loading the parent planning record.
    '''
    message = f'Fetching planning details for date range from {start_date} to {end_date}.'
    logger.info(message)

    # Use a JOIN to filter on the PlanningDetail table
    plannings = db.query(Planning).join(
        Planning.details
    ).filter(
        # Filter the joined details based on the date range
        PlanningDetail.date_of_day.between(start_date, end_date)
    ).options(
        # Use contains_eager to tell SQLAlchemy that the details are already loaded
        # and that the relationship should be populated with the filtered results.
        contains_eager(Planning.details)
    ).distinct().all()

    if not plannings:
        raise RegisterNotFoundError(
            detail = f'No plannings found with details for the date range {
                start_date} to {end_date}.'
        )

    return plannings

@handle_service_errors('PLANNING')
@audit_event('PLANNING', 'Planning', 'CREATE')
async def create_planning_with_details(
    db: Session,
    planning_data: PlanningCreateSchema
) -> Planning:
    '''
        Creates a planning record and its nested details and materials
        in a transactional block.
    '''
    if planning_data.start_date > planning_data.end_date:
        raise InvalidInputError(detail = '`start_date` cannot be after `end_date`')

    # 1. Create the main Planning record.
    planning_dict = planning_data.model_dump(exclude = {'details'})
    db_planning = Planning(**planning_dict)
    db.add(db_planning)
    db.flush()

    # 2. Iterate through planning details and materials to create nested records.
    if planning_data.details:
        for detail_data in planning_data.details:
            db_detail = create_record(
                db,
                PlanningDetail,
                detail_data,
                extra_fields = {'planning_id': db_planning.id},
                exclude_relations = ['materials']
            )

            for material_data in detail_data.materials:
                create_record(
                    db,
                    MaterialAssignment,
                    material_data,
                    extra_fields = {'planning_detail_id': db_detail.id}
                )

    db.commit()
    db.refresh(db_planning)
    return db_planning

@handle_service_errors('PLANNING')
@audit_event('PLANNING', 'Planning', 'UPDATE')
async def update_planning_with_details(
    db: Session,
    planning_id: int,
    planning_data: PlanningUpdateSchema
) -> Tuple[Planning, Dict]:
    '''
        Updates a planning record in a transactional block.
        Note: This function does not handle updates for details or materials.
    '''
    db_planning = get_record(db, Planning, planning_id)

    if (planning_data.start_date and planning_data.end_date and
            planning_data.start_date > planning_data.end_date):
        raise InvalidInputError(detail = '`start_date` cannot be after `end_date`')

    old_values = sqlalchemy_object_as_dict(db_planning)

    db_planning = update_record(db, db_planning, planning_data)

    db.commit()
    db.refresh(db_planning)

    auditable_data = {
        'old_values': old_values,
        'new_values': sqlalchemy_object_as_dict(db_planning)
    }

    return db_planning, auditable_data

@handle_service_errors('PLANNING')
@audit_event('PLANNING', 'PlanningDetail', 'CREATE')
async def create_planning_detail(
    db: Session,
    detail_data: PlanningDetailCreateSchema
) -> PlanningDetail:
    '''
        Creates a new planning detail record for an existing planning.
    '''
    message = f'Creating planning detail for planning ID: {detail_data.planning_id}'
    logger.info(message)
    db_detail = create_record(db, PlanningDetail, detail_data)
    db.commit()
    db.refresh(db_detail)
    return db_detail

@handle_service_errors('PLANNING')
@audit_event('PLANNING', 'Planning', 'DELETE')
async def delete_planning_by_id(
    db: Session,
    planning_id: int
) -> Tuple[int, Dict]:
    '''
        Deletes a planning and its associated details only if its status is 'ACTIVE'.
    '''
    message = f'Attempting to delete planning with ID: {planning_id}'
    logger.info(message)
    db_planning = get_record(db, Planning, planning_id)

    if db_planning.status != PlanningStatus.ACTIVE:
        raise InvalidInputError(
            detail = f'Cannot delete planning with status {
                db_planning.status}. Only ACTIVE plannings can be deleted.'
        )

    old_values = sqlalchemy_object_as_dict(db_planning)

    delete_record(db, Planning, planning_id)
    db.commit()

    auditable_data = {
        'old_values': old_values,
        'new_values': None
    }

    return planning_id, auditable_data

@handle_service_errors('PLANNING')
async def get_materials_by_detail_id(
    db: Session,
    planning_detail_id: int
) -> List[MaterialAssignment]:
    '''
        Retrieves all material assignments for a specific planning detail.
    '''
    message = f'Fetching materials for planning detail ID: {planning_detail_id}'
    logger.info(message)
    materials = db.query(MaterialAssignment).filter(
        MaterialAssignment.planning_detail_id == planning_detail_id
    ).all()
    if not materials:
        raise RegisterNotFoundError(
            detail = f'No materials found for planning detail ID {planning_detail_id}.'
        )
    return materials

@handle_service_errors('PLANNING')
@audit_event('PLANNING', 'MaterialAssignment', 'CREATE')
async def assign_material_to_planning_detail(
    db: Session,
    planning_detail_id: int,
    material_data: MaterialAssignmentSchema
) -> MaterialAssignment:
    '''
        Assigns a material to a planning detail.
    '''
    message = f'Assigning material {material_data.material_id} to planning detail {
        planning_detail_id}'
    logger.info(message)
    db_material = create_record(
        db,
        MaterialAssignment,
        material_data,
        extra_fields={'planning_detail_id': planning_detail_id}
    )
    db.commit()
    db.refresh(db_material)
    return db_material

@handle_service_errors('PLANNING')
@audit_event('PLANNING', 'MaterialAssignment', 'UPDATE')
async def update_material_quantities(
    db: Session,
    material_assignment_id: int,
    update_data: MaterialAssignmentUpdateSchema
) -> Tuple[MaterialAssignment, Dict]:
    '''
        Updates material quantities, calculating `quantity_used` based on `quantity_assigned`
        and `quantity_returned`.
    '''
    message = f'Updating material quantities for material assignment ID: {material_assignment_id}'
    logger.info(message)
    db_material = get_record(db, MaterialAssignment, material_assignment_id)

    old_values = sqlalchemy_object_as_dict(db_material)

    update_dict = update_data.model_dump(exclude_unset = True)
    quantity_returned = update_dict.get('quantity_returned')

    if quantity_returned is not None:
        if db_material.quantity_assigned < quantity_returned:
            raise InvalidInputError(
                detail='Quantity returned cannot be greater than quantity assigned.'
            )
        # Calculate quantity_used
        update_dict['quantity_used'] = db_material.quantity_assigned - quantity_returned

    # Update the record using the generic crud function
    db_material = update_record(db, db_material, MaterialAssignmentUpdateSchema(**update_dict))

    db.commit()
    db.refresh(db_material)

    auditable_data = {
        'old_values': old_values,
        'new_values': sqlalchemy_object_as_dict(db_material)
    }

    return db_material, auditable_data

@handle_service_errors('PLANNING')
@audit_event('PLANNING', 'MaterialAssignment', 'DELETE')
async def delete_material_by_id(
    db: Session,
    material_assignment_id: int
) -> Tuple[int, Dict]:
    '''
        Deletes a material assignment by its ID.
    '''
    message = f'Attempting to delete material with ID: {material_assignment_id}'
    logger.info(message)
    db_material = get_record(db, MaterialAssignment, material_assignment_id)

    old_values = sqlalchemy_object_as_dict(db_material)

    delete_record(db, MaterialAssignment, material_assignment_id)
    db.commit()

    auditable_data = {
        'old_values': old_values,
        'new_values': None
    }

    return material_assignment_id, auditable_data

@handle_service_errors('PLANNING')
@audit_event('PLANNING', 'PlanningDetail', 'DELETE')
async def delete_planning_detail_by_id(
    db: Session,
    planning_detail_id: int
) -> Tuple[int, Dict]:
    '''
        Deletes a planning detail by its ID.
    '''
    message = f'Attempting to delete planning detail with ID: {planning_detail_id}'
    logger.info(message)
    db_detail = get_record(db, PlanningDetail, planning_detail_id)

    old_values = sqlalchemy_object_as_dict(db_detail)

    delete_record(db, PlanningDetail, planning_detail_id)
    db.commit()

    auditable_data = {
        'old_values': old_values,
        'new_values': None
    }
    return planning_detail_id, auditable_data

@handle_service_errors('PLANNING')
@audit_event('PLANNING', 'PlanningDetail', 'UPDATE')
async def update_planning_detail(
    db: Session,
    planning_detail_id: int,
    update_data: PlanningDetailUpdateSchema
) -> Tuple[PlanningDetail, Dict]:
    '''
        Updates a planning detail record with the provided data.
    '''
    db_detail = db.query(PlanningDetail).filter(
        PlanningDetail.id == planning_detail_id
    ).first()

    if not db_detail:
        raise RegisterNotFoundError(
            detail = f'Planning detail with ID {planning_detail_id} not found.'
        )

    old_values = sqlalchemy_object_as_dict(db_detail)

    # Update fields with provided data
    for field, value in update_data.model_dump(exclude_unset = True).items():
        if value is not None:
            setattr(db_detail, field, value)

    db.commit()
    db.refresh(db_detail)

    auditable_data = {
        'old_values': old_values,
        'new_values': sqlalchemy_object_as_dict(db_detail)
    }
    return db_detail, auditable_data

@handle_service_errors('PLANNING')
async def get_filtered_plannings(
    db: Session,
    filters: PlanningFilterSchema
) -> List[Planning]:
    '''
        Retrieves a list of plannings based on a single, exclusive filter criterion.
    '''
    if all(value is None for value in filters.model_dump().values()):
        raise InvalidInputError(
            'At least one filter criterion must be provided to perform a search.'
        )

    # Build the query
    query = db.query(Planning)

    # Apply mandatory filters based on the presence of the fields in the schema
    if filters.company_id is not None:
        query = query.filter(Planning.company_id == filters.company_id)

    if filters.start_date is not None and filters.end_date is not None:
        query = query.filter(
            Planning.start_date >= filters.start_date,
            Planning.end_date <= filters.end_date
        )
    elif filters.start_date is not None:
        query = query.filter(Planning.start_date >= filters.start_date)

    # Apply optional filters from PlanningDetail, performing a JOIN if necessary
    # The join is only performed once if any of the following filters are present
    join_needed = any([
        filters.team_id is not None,
        filters.service_id is not None,
        filters.planned_route_id is not None,
        filters.date_of_day is not None
    ])

    if join_needed:
        query = query.join(Planning.details)
        query = query.options(contains_eager(Planning.details))

        if filters.team_id is not None:
            query = query.filter(PlanningDetail.team_id == filters.team_id)

        if filters.service_id is not None:
            query = query.filter(PlanningDetail.service_id == filters.service_id)

        if filters.planned_route_id is not None:
            query = query.filter(PlanningDetail.planned_route_id == filters.planned_route_id)

        if filters.date_of_day is not None:
            query = query.filter(PlanningDetail.date_of_day == filters.date_of_day)
    else:
        # Si no hay filtros de detalle, solo carga los detalles normalmente
        query = query.options(joinedload(Planning.details))

    plannings = query.all()

    if not plannings:
        raise RegisterNotFoundError(detail = 'No plannings found for the specified filter.')

    return plannings

async def bulk_create_planning(
    db: Session,
    file_name: str,
    delimiter: str,
    auth_token: str,
) -> Dict[str, Any]:
    '''
        Service function to handle the bulk upload of planning data.
        It uses a generic utility to process the file and insert data.
    '''
    logger.info('Starting bulk upload process...')

    result = await perform_bulk_upload(
        db = db,
        file_name = file_name,
        auth_token = auth_token,
        bulk_schema = PlanningBulkCreateSchema,
        processor_func = _process_planning_csv_data,
        inserter_func = _perform_atomic_db_insertion_for_planning,
        delimiter = delimiter
    )

    return result

def _get_months_from_period(period: str) -> List[int]:
    '''
        Helper function to get a list of month numbers from a period string.
        Handles quarterly, month names (in Spanish), and month numbers.
    '''
    period = period.upper().strip()
    result = []

    period_map = {
        'Q1': [1, 2, 3],
        'Q2': [4, 5, 6],
        'Q3': [7, 8, 9],
        'Q4': [10, 11, 12],
        'ENERO': 1,
        'FEBRERO': 2,
        'MARZO': 3,
        'ABRIL': 4,
        'MAYO': 5,
        'JUNIO': 6,
        'JULIO': 7,
        'AGOSTO': 8,
        'SEPTIEMBRE': 9,
        'OCTUBRE': 10,
        'NOVIEMBRE': 11,
        'DICIEMBRE': 12
    }

    # Busca el periodo en el mapa
    if period in period_map:
        months = period_map[period]
        if isinstance(months, list):
            result = months
        else:
            result = [months]
    elif period.isdigit() and 1 <= int(period) <= 12:
        result = [int(period)]

    return result

@handle_service_errors('PLANNING-SERVICE')
async def get_planned_route_ids_for_monitor_service(
    db: Session,
    filters: PlanningMonitorFilterSchema
) -> List[Dict[str, Any]]:
    '''
        Fetches planned route IDs based on a complex set of filtering criteria.
        This is a service layer function.
    '''
    # Comienza la consulta desde PlanningDetail
    query = db.query(PlanningDetail).join(
        Planning, PlanningDetail.planning_id == Planning.id
    )

    # Lista para las condiciones del filtro
    conditions = []

    # --- Aplica filtros obligatorios ---
    conditions.append(Planning.company_id == filters.company_id)
    conditions.append(PlanningDetail.service_id == filters.service_id)

    # --- Aplica el filtro de año (year) y periodo (period) ---
    # El 'year' se filtra en el año de la fecha de inicio o de fin del planning.
    if  filters.year:
        conditions.append(
            or_(
                extract('year', Planning.start_date) == filters.year,
                extract('year', Planning.end_date) == filters.year
            )
        )

    if filters.period:
        months = _get_months_from_period(filters.period)
        if months:
            conditions.append(extract('month', Planning.start_date).in_(months))

    # --- Aplica los filtros opcionales de jerarquía ---
    if filters.team_ids:
        # Prioridad 1: Usa team_ids si se proporciona
        conditions.append(PlanningDetail.team_id.in_(filters.team_ids))
    elif filters.user_ids:
        # Prioridad 2: Si no hay team_ids, se usarían user_ids, pero no
        # hay relación directa aquí. El servicio no puede continuar con este filtro
        # sin el mapeo a teams. Se registra una advertencia y se ignora.
        logger.warning(
            'Received user_ids but cannot filter directly. '
            'This requires an external service to map users to teams.'
        )

    # Ejecuta la consulta con todas las condiciones
    filtered_details = query.filter(and_(*conditions)).all()

    # Construye el formato de respuesta final
    result = []
    for detail in filtered_details:
        result.append({
            'planned_route_id': detail.planned_route_id,
            'team_id': detail.team_id,
            'service_id': detail.service_id
        })

    return result
