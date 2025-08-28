'''
   Planning Models
'''
from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import text
from services.db_connection import Base
from schemas.planning import PlanningStatus

class Planning(Base): # pylint: disable=too-few-public-methods
    '''
        SQLAlchemy model for general planning records.
    '''
    __tablename__ = 't_plannings'

    id = Column(Integer, primary_key = True, index = True)
    company_id = Column(Integer, nullable = False, index = True)
    app_id = Column(Integer, nullable = False, index = True)
    planning_name = Column(String(255), nullable = False)
    description = Column(String(500), nullable=True)
    start_date = Column(Date, nullable = False)
    end_date = Column(Date, nullable = False)
    week_number = Column(Integer, nullable = False)
    status = Column(Enum(PlanningStatus),
                    default=PlanningStatus.CREATED,
                    nullable = False)
    created_at = Column(DateTime, nullable = False, server_default = text('now()'))

    details = relationship(
        'PlanningDetail',
        back_populates = 'planning',
        cascade = 'all, delete-orphan'
    )

class PlanningDetail(Base): # pylint: disable=too-few-public-methods
    '''
        SQLAlchemy model for details within a planning.
    '''
    __tablename__ = 't_planning_details'

    id = Column(Integer, primary_key = True, index = True)
    planning_id = Column(Integer,
                        ForeignKey('t_plannings.id', ondelete = 'CASCADE'),
                        nullable = False)
    team_id = Column(Integer, nullable = False, index = True)
    service_id = Column(Integer, nullable = False, index = True)
    planned_route_id = Column(Integer, nullable = False, index = True)
    created_at = Column(DateTime, nullable = False, server_default = text('now()'))

    planning = relationship('Planning', back_populates = 'details')
    materials = relationship(
        'MaterialAssignment',
        back_populates = 'planning_detail',
        cascade = 'all, delete-orphan'
    )

class MaterialAssignment(Base): # pylint: disable=too-few-public-methods
    '''
        SQLAlchemy model for material assignments to a planning detail.
    '''
    __tablename__ = 't_material_assignments'

    id = Column(Integer, primary_key = True, index = True)
    planning_detail_id = Column(Integer,
                                ForeignKey('t_planning_details.id', ondelete = 'CASCADE'),
                                nullable = False)
    material_id = Column(Integer, nullable = False, index = True)
    quantity_assigned = Column(Integer, nullable = False)
    quantity_used = Column(Integer, nullable = True)
    quantity_returned = Column(Integer, nullable = True)
    created_at = Column(DateTime, nullable = False, server_default = text('now()'))

    planning_detail = relationship('PlanningDetail', back_populates = 'materials')
