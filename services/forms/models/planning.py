'''
   Planning Models
'''
from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from services.db_connection import Base
from services.utils import get_current_time_gmt
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
                    default = PlanningStatus.ACTIVE,
                    nullable = False)
    created_at = Column(DateTime, nullable = False, default = get_current_time_gmt)

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
    date_of_day = Column(DateTime, nullable = False)
    created_at = Column(DateTime, nullable = False, default = get_current_time_gmt)

    planning = relationship('Planning', back_populates = 'details')
