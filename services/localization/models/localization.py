'''
    Database Models for Localization Microservice
'''
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import text
from services.db_connection import Base
from schemas.localization import PlannedRouteStatusEnum

class PlannedRoute(Base):# pylint: disable=too-few-public-methods
    '''
        SQLAlchemy model for a planned route.
    '''
    __tablename__ = 't_planned_routes'

    id = Column(Integer, primary_key = True, index = True)
    route_name = Column(String(150), nullable = False)
    route_code = Column(String(50), nullable = False, unique = True, index = True)
    description = Column(String(500), nullable = True)
    user_id = Column(Integer, nullable = False, index = True)
    # Using text('now()') and server_default to fix Pylint error and ensure
    # the function is executed at the database level.
    created_at = Column(DateTime, nullable = False, server_default = text('now()'))

    status = Column(
        Enum(PlannedRouteStatusEnum),
        default = PlannedRouteStatusEnum.IN_CREATION,
        nullable = False
    )

    points = relationship(
        'PlannedPoint',
        back_populates = 'planned_route',
        cascade = 'all, delete-orphan'
    )
    t_executed_routes = relationship(
        'ExecutedRoute',
        back_populates = 'planned_route'
    )

class PlannedPoint(Base):# pylint: disable=too-few-public-methods
    '''
        SQLAlchemy model for a geographical point within a planned route.
    '''
    __tablename__ = 't_planned_points'

    id = Column(Integer, primary_key = True, index = True)
    planned_route_id = Column(Integer, ForeignKey('t_planned_routes.id'), nullable = False)
    point_name = Column(String(100), nullable = False)
    latitude = Column(Numeric(16, 14), nullable = False)
    longitude = Column(Numeric(16, 14), nullable = False)
    reference_data = Column(Text, nullable = True)

    planned_route = relationship('PlannedRoute', back_populates = 'points')
    t_attendances = relationship(
        'Attendance',
        back_populates = 'planned_point',
        cascade = 'all, delete-orphan'
    )

class ExecutedRoute(Base):# pylint: disable=too-few-public-methods
    '''
        SQLAlchemy model for a user's executed journey.
    '''
    __tablename__ = 't_executed_routes'

    id = Column(Integer, primary_key = True, index = True)
    user_id = Column(Integer, nullable = False, index = True)
    planned_route_id = Column(Integer, ForeignKey('t_planned_routes.id'), nullable = True)
    # Using text('now()') and server_default for consistency and Pylint compatibility.
    start_time = Column(DateTime, nullable = False, server_default = text('now()'))
    end_time = Column(DateTime, nullable = True)

    planned_route = relationship('PlannedRoute', back_populates = 't_executed_routes')
    points = relationship(
        'ExecutedPoint',
        back_populates = 'executed_route',
        cascade = 'all, delete-orphan'
    )

class ExecutedPoint(Base):# pylint: disable=too-few-public-methods
    '''
        SQLAlchemy model for a dynamically recorded geographical point.
    '''
    __tablename__ = 't_executed_points'

    id = Column(Integer, primary_key = True, index = True)
    executed_route_id = Column(Integer, ForeignKey('t_executed_routes.id'), nullable = False)
    latitude = Column(Numeric(16, 14), nullable = False)
    longitude = Column(Numeric(16, 14), nullable = False)
    timestamp = Column(DateTime, nullable = False, index = True)

    executed_route = relationship('ExecutedRoute', back_populates = 'points')

class Attendance(Base):# pylint: disable=too-few-public-methods
    '''
        SQLAlchemy model for attendance records at a planned point.
    '''
    __tablename__ = 't_attendances'

    id = Column(Integer, primary_key = True, index = True)
    user_id = Column(Integer, nullable = False, index = True)
    planned_point_id = Column(Integer, ForeignKey('t_planned_points.id'), nullable = False)
    check_in_time = Column(DateTime, nullable = True)
    check_out_time = Column(DateTime, nullable = True)

    planned_point = relationship('PlannedPoint', back_populates = 't_attendances')
