'''
    Business logic services for the Planning microservice.
'''
from typing import Any, Dict, List, Optional
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from services.crud import (
    create_record,
    delete_record,
    get_record,
    update_record
)
from services.exceptions import (
    RegisterNotFoundError,
    InvalidInputError
)
from services.logger_config import custom_logger as logger

from models.planning import (
    Planning, PlanningDetail,
    MaterialAssignment
)
from schemas.planning import (
    MaterialAssignmentSchema,
    MaterialAssignmentUpdateSchema,
    PlanningCreateSchema,
    PlanningDetailCreateSchema,
    PlanningStatus,
    PlanningUpdateSchema
)

def get_plannings_by_week(
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

def get_plannings_by_date(
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
            detail=f'No plannings found for date {planning_date}.'
        )
    return plannings

def create_planning_with_details(
    db: Session,
    planning_data: PlanningCreateSchema
) -> Planning:
    '''
        Creates a planning record and its nested details and materials
        in a transactional block.
    '''
    try:
        if planning_data.start_date > planning_data.end_date:
            raise InvalidInputError(detail='`start_date` cannot be after `end_date`')

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
                    extra_fields={'planning_id': db_planning.id},
                    exclude_relations=['materials']
                )

                for material_data in detail_data.materials:
                    create_record(
                        db,
                        MaterialAssignment,
                        material_data,
                        extra_fields={'planning_detail_id': db_detail.id}
                    )

        db.commit()
        db.refresh(db_planning)
        return db_planning
    except (IntegrityError, SQLAlchemyError, InvalidInputError, RegisterNotFoundError) as e:
        db.rollback()
        error_msg = f'Failed to create planning {planning_data.planning_name}: {e}'
        logger.error(error_msg, exc_info = True)
        raise e
    except Exception as e:
        db.rollback()
        error_msg = f'Unexpected error creating planning: {e}'
        logger.critical(error_msg, exc_info = True)
        raise RuntimeError('An unexpected internal error occurred.') from e

def update_planning_with_details(
    db: Session,
    planning_id: int,
    planning_data: PlanningUpdateSchema
) -> Planning:
    '''
        Updates a planning record in a transactional block.
        Note: This function does not handle updates for details or materials.
    '''
    try:
        db_planning = get_record(db, Planning, planning_id)

        if (planning_data.start_date and planning_data.end_date and
                planning_data.start_date > planning_data.end_date):
            raise InvalidInputError(detail='`start_date` cannot be after `end_date`')

        db_planning = update_record(db, db_planning, planning_data)

        db.commit()
        db.refresh(db_planning)
        return db_planning
    except (IntegrityError, SQLAlchemyError, InvalidInputError, RegisterNotFoundError) as e:
        db.rollback()
        error_msg = f'Failed to update planning {planning_id}: {e}'
        logger.error(error_msg, exc_info = True)
        raise e
    except Exception as e:
        db.rollback()
        error_msg = f'Unexpected error updating planning: {e}'
        logger.critical(error_msg, exc_info = True)
        raise RuntimeError('An unexpected internal error occurred.') from e

def create_planning_detail(
    db: Session,
    detail_data: PlanningDetailCreateSchema
) -> PlanningDetail:
    '''
        Creates a new planning detail record for an existing planning.
    '''
    message = f'Creating planning detail for planning ID: {detail_data.planning_id}'
    logger.info(message)
    try:
        db_detail = create_record(db, PlanningDetail, detail_data)
        db.commit()
        db.refresh(db_detail)
        return db_detail
    except (IntegrityError, SQLAlchemyError, RegisterNotFoundError) as e:
        db.rollback()
        error_msg = f'Failed to create planning detail: {e}'
        logger.error(error_msg, exc_info = True)
        raise e
    except Exception as e:
        db.rollback()
        error_msg = f'Unexpected error creating planning detail: {e}'
        logger.critical(error_msg, exc_info = True)
        raise RuntimeError('An unexpected internal error occurred.') from e

def delete_planning_by_id(
    db: Session,
    planning_id: int
) -> dict:
    '''
        Deletes a planning and its associated details only if its status is 'CREATED'.
    '''
    message = f'Attempting to delete planning with ID: {planning_id}'
    logger.info(message)
    try:
        db_planning = get_record(db, Planning, planning_id)

        if db_planning.status != PlanningStatus.CREATED:
            raise InvalidInputError(
                detail = f'''Cannot delete planning with status {db_planning.status}.
                        Only CREATED plannings can be deleted.'''
            )

        delete_record(db, Planning, planning_id)
        db.commit()
        return {'message': f'Planning {planning_id} deleted successfully.'}
    except (IntegrityError, SQLAlchemyError, InvalidInputError, RegisterNotFoundError) as e:
        db.rollback()
        error_msg = f'Failed to delete planning {planning_id}: {e}'
        logger.error(error_msg, exc_info = True)
        raise e
    except Exception as e:
        db.rollback()
        error_msg = f'Unexpected error deleting planning: {e}'
        logger.critical(error_msg, exc_info = True)
        raise RuntimeError('An unexpected internal error occurred.') from e

def get_materials_by_detail_id(
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

def assign_material_to_planning_detail(
    db: Session,
    planning_detail_id: int,
    material_data: MaterialAssignmentSchema
) -> MaterialAssignment:
    '''
        Assigns a material to a planning detail.
    '''
    message = f'''Assigning material {material_data.material_id} to planning detail
            {planning_detail_id}'''
    logger.info(message)
    try:
        db_material = create_record(
            db,
            MaterialAssignment,
            material_data,
            extra_fields={'planning_detail_id': planning_detail_id}
        )
        db.commit()
        db.refresh(db_material)
        return db_material
    except (IntegrityError, SQLAlchemyError, RegisterNotFoundError) as e:
        db.rollback()
        error_msg = f'Failed to assign material to planning detail {planning_detail_id}: {e}'
        logger.error(error_msg, exc_info = True)
        raise e
    except Exception as e:
        db.rollback()
        error_msg = f'Unexpected error assigning material to planning detail: {e}'
        logger.critical(error_msg, exc_info = True)
        raise RuntimeError('An unexpected internal error occurred.') from e

def update_material_quantities(
    db: Session,
    material_assignment_id: int,
    update_data: MaterialAssignmentUpdateSchema
) -> MaterialAssignment:
    '''
        Updates material quantities, calculating `quantity_used` based on `quantity_assigned`
        and `quantity_returned`.
    '''
    message = f'Updating material quantities for material assignment ID: {material_assignment_id}'
    logger.info(message)
    try:
        db_material = get_record(db, MaterialAssignment, material_assignment_id)

        update_dict = update_data.model_dump(exclude_unset=True)
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
        return db_material
    except (IntegrityError, SQLAlchemyError, RegisterNotFoundError, InvalidInputError) as e:
        db.rollback()
        error_msg = f'Failed to update material {material_assignment_id}: {e}'
        logger.error(error_msg, exc_info = True)
        raise e
    except Exception as e:
        db.rollback()
        error_msg = f'Unexpected error updating material: {e}'
        logger.critical(error_msg, exc_info = True)
        raise RuntimeError('An unexpected internal error occurred.') from e

def delete_material_by_id(
    db: Session,
    material_assignment_id: int
) -> dict:
    '''
        Deletes a material assignment by its ID.
    '''
    message = f'Attempting to delete material with ID: {material_assignment_id}'
    logger.info(message)
    try:
        delete_record(db, MaterialAssignment, material_assignment_id)
        db.commit()
        return {'message': f'Material assignment {material_assignment_id} deleted successfully.'}
    except (IntegrityError, SQLAlchemyError, RegisterNotFoundError) as e:
        db.rollback()
        error_msg = f'Failed to delete material {material_assignment_id}: {e}'
        logger.error(error_msg, exc_info = True)
        raise e
    except Exception as e:
        db.rollback()
        error_msg = f'Unexpected error deleting material: {e}'
        logger.critical(error_msg, exc_info = True)
        raise RuntimeError('An unexpected internal error occurred.') from e

def get_filtered_plannings(
    db: Session,
    company_id: Optional[int] = None,
    team_id: Optional[int] = None,
    service_id: Optional[int] = None,
    planned_route_id: Optional[int] = None,
) -> List[Planning]:
    '''
        Retrieves a list of plannings based on a single, exclusive filter criterion.
    '''
    # Check that only one filter is provided
    provided_filters = [
        company_id, team_id, service_id, planned_route_id
    ]
    if sum(1 for f in provided_filters if f is not None) > 1:
        raise InvalidInputError(
            detail = 'Only one filter can be provided at a time.'
        )

    # Build the query
    query = db.query(Planning)

    if company_id:
        query = query.filter(Planning.company_id == company_id)
    if team_id:
        # Filter by team_id which is in PlanningDetail model, so we must join
        query = query.join(Planning.details).filter(PlanningDetail.team_id == team_id)
    if service_id:
        # Filter by service_id
        query = query.join(Planning.details).filter(PlanningDetail.service_id == service_id)
    if planned_route_id:
        # Filter by planned_route_id
        query = query.join(Planning.details).filter(
            PlanningDetail.planned_route_id == planned_route_id
        )

    plannings = query.all()

    if not plannings:
        raise RegisterNotFoundError(detail = 'No plannings found for the specified filter.')

    return plannings

def delete_planning_detail_by_id(
    db: Session,
    planning_detail_id: int
) -> dict:
    '''
        Deletes a planning detail by its ID.
    '''
    message = f'Attempting to delete planning detail with ID: {planning_detail_id}'
    logger.info(message)
    try:
        delete_record(db, PlanningDetail, planning_detail_id)
        db.commit()
        return {'message': f'Planning detail {planning_detail_id} deleted successfully.'}
    except (IntegrityError, SQLAlchemyError, RegisterNotFoundError) as e:
        db.rollback()
        error_msg = f'Failed to delete planning detail {planning_detail_id}: {e}'
        logger.error(error_msg, exc_info = True)
        raise e
    except Exception as e:
        db.rollback()
        error_msg = f'Unexpected error deleting planning detail: {e}'
        logger.critical(error_msg, exc_info = True)
        raise RuntimeError('An unexpected internal error occurred.') from e

def update_planning_detail(
    db: Session,
    planning_detail_id: int,
    update_data: Dict[str, Any]
) -> PlanningDetail:
    '''
        Updates a planning detail record with the provided data.
    '''
    try:
        db_detail = db.query(PlanningDetail).filter(
            PlanningDetail.id == planning_detail_id
        ).first()

        if not db_detail:
            raise RegisterNotFoundError(
                detail=f"Planning detail with ID {planning_detail_id} not found."
            )

        # Update fields with provided data
        for field, value in update_data.items():
            if value is not None:
                setattr(db_detail, field, value)

        db.commit()
        db.refresh(db_detail)
        return db_detail
    except (SQLAlchemyError, RegisterNotFoundError) as e:
        db.rollback()
        error_msg = f'Failed to update planning detail {planning_detail_id}: {e}'
        logger.error(error_msg, exc_info = True)
        raise e
    except Exception as e:
        db.rollback()
        error_msg = f'Unexpected error updating planning detail: {e}'
        logger.critical(error_msg, exc_info = True)
        raise RuntimeError('An unexpected internal error occurred.') from e
