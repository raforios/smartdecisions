'''
    Business Logic for Trade.
'''
from datetime import datetime
from typing import Any, Dict, List, Tuple
from sqlalchemy.orm import Session, joinedload
from services.exceptions import InvalidInputError
from services.crud import (
    create_record,
    delete_record,
    get_record,
    update_record
)
from services.logger_config import custom_logger as logger
from services.utils import (
    handle_service_errors,
    audit_event,
    sqlalchemy_object_as_dict
)
from models.trade import (
    TradePlanning
)
from schemas.trade import (
    TradePlanningAdHocCreateSchema,
    TradePlanningCreateSchema,
    TradePlanningFilterSchema,
    TradePlanningJustificationSchema,
    TradePlanningUpdateSchema,
    TradePlanningWorkloadUpdateSchema,
)

# --- A.3. TRADE PLANNING SERVICES ---

@handle_service_errors('TRADE')
@audit_event('TRADE', 'TradePlanning', 'CREATE')
async def create_trade_planning_service(
    db: Session,
    planning_data: TradePlanningCreateSchema
) -> Tuple[TradePlanning, Dict[str, Any]]:
    '''
        Creates a new Trade Planning entry.
    '''
    message = f'Attempting to create Trade Planning for planning_id: {planning_data.planning_id}'
    logger.info(message)

    db_planning = create_record(
        db = db,
        model = TradePlanning,
        create_data = planning_data
    )

    db.commit()
    db.refresh(db_planning)

    auditable_data = {
        'new_values': sqlalchemy_object_as_dict(db_planning),
        'company_id': db_planning.company_id,
        'user_id': db_planning.user_id
    }

    return db_planning, auditable_data

@handle_service_errors('TRADE')
async def get_trade_planning_by_id_service(
    db: Session,
    planning_id: int
) -> TradePlanning:
    '''
        Retrieves a specific Trade Planning entry by its ID,
        eager loading the Point of Sale info.
    '''
    message = f'Attempting to retrieve Trade Planning ID: {planning_id}'
    logger.info(message)

    eager_load_options = [
        joinedload(TradePlanning.point_of_sale)
    ]

    db_planning = get_record(
        db = db,
        model = TradePlanning,
        record_id = planning_id,
        eager_load_options = eager_load_options
    )

    return db_planning


@handle_service_errors('TRADE')
async def get_trade_planning_list_service(
    db: Session,
    filters: TradePlanningFilterSchema,
    skip: int = 0,
    limit: int = 100
) -> Tuple[List[TradePlanning], int]:
    '''
        Retrieves a paginated list of Trade Planning entries based on filters.
    '''
    message = f'Attempting to retrieve Trade Planning list with filters: {filters}'
    logger.info(message)

    query = db.query(TradePlanning).options(
        joinedload(TradePlanning.point_of_sale)
    )

    query = query.filter(TradePlanning.company_id == filters.company_id)

    if filters.planning_id:
        query = query.filter(TradePlanning.planning_id == filters.planning_id)
    if filters.user_id:
        query = query.filter(TradePlanning.user_id == filters.user_id)
    if filters.point_of_sale_id:
        query = query.filter(TradePlanning.point_of_sale_id == filters.point_of_sale_id)
    if filters.status:
        query = query.filter(TradePlanning.status == filters.status)

    total_count = query.count()
    records = query.order_by(TradePlanning.id.desc()).offset(skip).limit(limit).all()

    return records, total_count


@handle_service_errors('TRADE')
@audit_event('TRADE', 'TradePlanning', 'UPDATE')
async def update_trade_planning_service(
    db: Session,
    planning_id: int,
    update_data: TradePlanningUpdateSchema
) -> Tuple[TradePlanning, Dict[str, Any]]:
    '''
        Updates a Trade Planning entry (e.g., status or comments).
    '''
    message = f'Attempting to update Trade Planning ID: {planning_id}'
    logger.info(message)

    db_planning = get_record(db, TradePlanning, planning_id)
    old_values = sqlalchemy_object_as_dict(db_planning)

    db_planning = update_record(db, db_planning, update_data)

    db.commit()
    db.refresh(db_planning)

    auditable_data = {
        'old_values': old_values,
        'new_values': sqlalchemy_object_as_dict(db_planning),
        'company_id': db_planning.company_id,
        'user_id': db_planning.user_id
    }

    return db_planning, auditable_data

@handle_service_errors('TRADE')
@audit_event('TRADE', 'TradePlanning', 'DELETE')
async def delete_trade_planning_service(
    db: Session,
    planning_id: int
) -> Tuple[int, Dict[str, Any]]:
    '''
        Deletes a Trade Planning entry.
    '''
    message = f'Attempting to delete Trade Planning ID: {planning_id}'
    logger.info(message)

    db_planning = get_record(db, TradePlanning, planning_id)
    old_values = sqlalchemy_object_as_dict(db_planning)

    company_id_audit = db_planning.company_id
    user_id_audit = db_planning.user_id

    delete_record(
        db = db,
        model = TradePlanning,
        record_id = planning_id
    )

    db.commit()

    auditable_data = {
        'old_values': old_values,
        'new_values': None,
        'company_id': company_id_audit,
        'user_id': user_id_audit
    }

    return planning_id, auditable_data

@handle_service_errors('TRADE')
@audit_event('TRADE', 'TradePlanning', 'WORKLOAD_CALCULATION')
async def update_trade_planning_workload_service(
    db: Session,
    planning_id: int,
    workload_data: TradePlanningWorkloadUpdateSchema
) -> Tuple[TradePlanning, Dict[str, Any]]:
    '''
        Calculates and updates the actual workload based on check-in/out times.
    '''
    message = f'Calculating workload for Trade Planning ID: {planning_id}'
    logger.info(message)

    if workload_data.check_out_time <= workload_data.check_in_time:
        raise InvalidInputError(
            detail='Check-out time must be after check-in time.'
        )

    db_planning = get_record(db, TradePlanning, planning_id)
    old_values = sqlalchemy_object_as_dict(db_planning)
    
    for key, value in old_values.items():
        if isinstance(value, datetime) and value.tzinfo is not None:
            # Limpieza: Hacemos la fecha naive para que el validador remoto la acepte.
            old_values[key] = value.replace(tzinfo = None).isoformat()
        elif key == 'point_of_sale':
            del old_values[key] # Eliminamos la relación si fue cargada

    duration_delta = workload_data.check_out_time - workload_data.check_in_time
    actual_minutes = int(duration_delta.total_seconds() // 60)
    planned_minutes = db_planning.planned_workload_minutes
    difference_minutes = actual_minutes - planned_minutes

    db_planning.actual_workload_minutes = actual_minutes
    db_planning.workload_difference_minutes = difference_minutes
    db_planning.status = 'COMPLETED'

    db.add(db_planning)
    db.commit()
    db.refresh(db_planning)

    if hasattr(db_planning, 'point_of_sale'):
        delattr(db_planning, 'point_of_sale')

    # 3. Generar NEW_VALUES (para incrustar el cálculo)
    # El decorador leerá db_planning (limpio) para generar el new_values base.
    # Aquí creamos el diccionario final que queremos que sea el new_values.
    new_values_final = sqlalchemy_object_as_dict(db_planning)

    # Limpieza NEW_VALUES: Fechas
    for key, value in new_values_final.items():
        if isinstance(value, datetime) and value.tzinfo is not None:
            new_values_final[key] = value.replace(tzinfo=None).isoformat()
            
    # Incrustar el campo extra 'calculation_input' dentro de new_values_final
    new_values_final['calculation_input'] = {
        # Limpiamos las fechas de entrada por seguridad.
        'check_in': workload_data.check_in_time.replace(tzinfo=None).isoformat(),
        'check_out': workload_data.check_out_time.replace(tzinfo=None).isoformat()
    }
    
    # 4. Devolver el diccionario completo. El decorador usará new_values_final
    # como new_values, ya que sobrescribe el new_values ORM con la clave del auditable_data
    # si está presente.
    auditable_data = {
        'old_values': old_values,
        'new_values': new_values_final, 
        'company_id': db_planning.company_id,
        'user_id': db_planning.user_id
    }

    return db_planning, auditable_data

# --- A.4. AGENDA DE CAMPO SERVICES ---
@handle_service_errors('TRADE')
@audit_event('TRADE', 'TradePlanning', 'CREATE_ADHOC')
async def create_adhoc_planning_service(
    db: Session,
    adhoc_data: TradePlanningAdHocCreateSchema
) -> Tuple[TradePlanning, Dict[str, Any]]:
    '''
        Creates an Ad-Hoc planning entry (Fuera de Ruta).
    '''
    message = f'Creating Ad-Hoc visit for User: {adhoc_data.user_id} at POS: {
        adhoc_data.point_of_sale_id}'
    logger.info(message)

    # 1. Verificar si ya tiene una visita PENDIENTE o COMPLETADA hoy para este PDV
    # (Regla de negocio: Evitar duplicados el mismo día aunque sea Ad-Hoc)

    existing_plan = db.query(TradePlanning).filter(
        TradePlanning.point_of_sale_id == adhoc_data.point_of_sale_id,
        TradePlanning.user_id == adhoc_data.user_id,
        TradePlanning.status.in_(['PENDING', 'IN_PROGRESS'])
    ).first()

    if existing_plan:
        raise InvalidInputError(
            detail=f'User already has an active visit for POS {adhoc_data.point_of_sale_id}.'
        )

    # 2. Crear el registro
    db_planning = TradePlanning(
        company_id = adhoc_data.company_id,
        planning_id = None,
        user_id = adhoc_data.user_id,
        point_of_sale_id = adhoc_data.point_of_sale_id,
        planned_workload_minutes = 0,
        is_adhoc = True,
        status = 'PENDING',
        comments = adhoc_data.comments
    )

    db.add(db_planning)
    db.commit()
    db.refresh(db_planning)

    auditable_data = {
        'new_values': sqlalchemy_object_as_dict(db_planning),
        'company_id': db_planning.company_id,
        'user_id': db_planning.user_id
    }

    return db_planning, auditable_data


@handle_service_errors('TRADE')
@audit_event('TRADE', 'TradePlanning', 'JUSTIFY')
async def justify_planning_absence_service(
    db: Session,
    planning_id: int,
    justification_data: TradePlanningJustificationSchema
) -> Tuple[TradePlanning, Dict[str, Any]]:
    '''
        Cancels/Closes a planned visit with a justification.
    '''
    message = f'Justifying absence for Planning ID: {planning_id}'
    logger.info(message)

    db_planning = get_record(db, TradePlanning, planning_id)
    old_values = sqlalchemy_object_as_dict(db_planning)

    if db_planning.status == 'COMPLETED':
        raise InvalidInputError('Cannot justify a completed visit.')

    # Actualizar estado y justificación
    db_planning.status = 'NO_VISIT' # O 'CANCELLED' según tu enumerador
    db_planning.justification = justification_data.justification

    db.add(db_planning)
    db.commit()
    db.refresh(db_planning)

    auditable_data = {
        'old_values': old_values,
        'new_values': sqlalchemy_object_as_dict(db_planning),
        'justification': justification_data.justification,
        'company_id': db_planning.company_id,
        'user_id': db_planning.user_id
    }

    return db_planning, auditable_data
