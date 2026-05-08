'''
    Trade Models — Planning, Routes, Planned Points, and Attendances.

    The planning module is split into four entities so that a Plan groups
    a campaign over a date range, and each day of the campaign references a
    Planned Route which in turn lists Planned Points (POS visits) with
    sequence and workload metrics.
'''
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Date,
    ForeignKey,
    DateTime,
    Boolean,
    UniqueConstraint,
    Numeric
)
from sqlalchemy.orm import relationship

from services.db_connection import Base
from services.utils import get_current_time_gmt


# --- A.1. PLANNED ROUTE (master) ---
class PlannedRoute(Base):  # pylint: disable=too-few-public-methods
    '''
        Planned route master. Each route belongs to a company and holds the
        ordered list of POS visits (`planned_points`).
    '''
    __tablename__ = 't_trade_planned_routes'

    id = Column(Integer, primary_key = True, index = True)
    company_id = Column(Integer, nullable = False, index = True)

    route_name = Column(String(150), nullable = False)
    # `route_code` is unique per company so different companies can reuse codes.
    route_code = Column(String(50), nullable = False, index = True)
    description = Column(Text, nullable = True)

    # Audit field
    created_at = Column(DateTime, nullable = False, default = get_current_time_gmt)

    points = relationship(
        'PlannedPoint',
        back_populates = 'planned_route',
        cascade = 'all, delete-orphan',
        order_by = 'PlannedPoint.sequence'
    )

    __table_args__ = (
        UniqueConstraint('company_id', 'route_code', name = 'uc_planned_route_company_code'),
    )


# --- A.2. PLANNED POINT (detail of a route) ---
class PlannedPoint(Base):  # pylint: disable=too-few-public-methods
    '''
        Detail of a planned route. Defines the order of POS visits (`sequence`),
        their workload in minutes, ad-hoc flag and justification, plus the
        live workload tracking once the visit is executed.
    '''
    __tablename__ = 't_trade_planned_points'

    id = Column(Integer, primary_key = True, index = True)

    planned_route_id = Column(
        Integer,
        ForeignKey('t_trade_planned_routes.id', ondelete = 'CASCADE'),
        nullable = False,
        index = True
    )
    planned_route = relationship('PlannedRoute', back_populates = 'points')

    # Visit order in the route (1, 2, 3...). Ad-hoc points may also have one.
    sequence = Column(Integer, nullable = False)

    # Ad-hoc flag and justification text (when off-route).
    is_adhoc = Column(Boolean, default = False, nullable = False)
    justification = Column(Text, nullable = True)

    # Target POS for this stop.
    point_of_sale_id = Column(
        Integer,
        ForeignKey('t_points_of_sale.id', ondelete = 'RESTRICT'),
        nullable = False,
        index = True
    )
    point_of_sale = relationship('PointOfSale')

    # Workload metrics. `planned_workload_minutes` is the budgeted time for
    # the visit. `actual_workload_minutes` and `workload_difference_minutes`
    # are filled when the operator checks out.
    planned_workload_minutes = Column(Integer, nullable = False)
    actual_workload_minutes = Column(Integer, nullable = True)
    workload_difference_minutes = Column(Integer, nullable = True)

    status = Column(String(20), default = 'PENDING', nullable = False)
    comments = Column(Text, nullable = True)

    # Audit field
    created_at = Column(DateTime, nullable = False, default = get_current_time_gmt)

    __table_args__ = (
        UniqueConstraint(
            'planned_route_id', 'sequence',
            name = 'uc_planned_point_route_sequence'
        ),
    )


# --- A.3. TRADE PLANNING (campaign master) ---
class TradePlanning(Base):  # pylint: disable=too-few-public-methods
    '''
        Trade planning campaign master. Groups a set of route executions for
        a team during a date range. The day-by-day route assignment lives in
        `t_trade_planning_detail`.
    '''
    __tablename__ = 't_trade_planning'

    id = Column(Integer, primary_key = True, index = True)
    company_id = Column(Integer, nullable = False, index = True)

    planning_name = Column(String(150), nullable = False)
    description = Column(Text, nullable = True)

    # `team_id` comes from the frontend (external app). No FK on this side.
    team_id = Column(Integer, nullable = False, index = True)

    start_date = Column(Date, nullable = False)
    end_date = Column(Date, nullable = False)

    status = Column(String(20), default = 'DRAFT', nullable = False)

    created_at = Column(DateTime, nullable = False, default = get_current_time_gmt)

    details = relationship(
        'TradePlanningDetail',
        back_populates = 'planning',
        cascade = 'all, delete-orphan',
        order_by = 'TradePlanningDetail.date_of_day'
    )


# --- A.4. TRADE PLANNING DETAIL (planning x route x day) ---
class TradePlanningDetail(Base):  # pylint: disable=too-few-public-methods
    '''
        Per-day assignment of a planned route inside a campaign.
        One route per day within a planning entry.
    '''
    __tablename__ = 't_trade_planning_detail'

    id = Column(Integer, primary_key = True, index = True)

    planning_id = Column(
        Integer,
        ForeignKey('t_trade_planning.id', ondelete = 'CASCADE'),
        nullable = False,
        index = True
    )
    planning = relationship('TradePlanning', back_populates = 'details')

    planned_route_id = Column(
        Integer,
        ForeignKey('t_trade_planned_routes.id', ondelete = 'RESTRICT'),
        nullable = False,
        index = True
    )
    planned_route = relationship('PlannedRoute')

    date_of_day = Column(Date, nullable = False)

    created_at = Column(DateTime, nullable = False, default = get_current_time_gmt)

    __table_args__ = (
        UniqueConstraint(
            'planning_id', 'planned_route_id', 'date_of_day',
            name = 'uc_planning_detail_unique'
        ),
    )


# --- A.5. ATTENDANCE (visit at a planned point) ---
class Attendance(Base):  # pylint: disable=too-few-public-methods
    '''
        Records a real visit (check-in / check-out) at a Planned Point. The
        operator (`user_id`) and the team they belong to come from the
        frontend.
    '''
    __tablename__ = 't_trade_attendances'

    id = Column(Integer, primary_key = True, index = True)
    company_id = Column(Integer, nullable = False, index = True)
    user_id = Column(Integer, nullable = False, index = True)

    # Replaces the old `trade_planning_id`: now we point to the specific
    # planned point (route + sequence + POS) the operator is visiting.
    trade_planned_point_id = Column(
        Integer,
        ForeignKey('t_trade_planned_points.id', ondelete = 'CASCADE'),
        nullable = False,
        index = True
    )
    planned_point = relationship('PlannedPoint')

    # --- Check-In Data ---
    check_in_time = Column(DateTime, nullable = True)
    check_in_latitude = Column(Numeric(16, 14), nullable = True)
    check_in_longitude = Column(Numeric(16, 14), nullable = True)
    # Distance from POS in meters at check-in.
    check_in_distance_error = Column(Numeric(10, 2), nullable = True)

    # --- Check-Out Data ---
    check_out_time = Column(DateTime, nullable = True)
    check_out_latitude = Column(Numeric(16, 14), nullable = True)
    check_out_longitude = Column(Numeric(16, 14), nullable = True)
    check_out_distance_error = Column(Numeric(10, 2), nullable = True)

    # Effective duration in minutes (computed at check-out).
    duration_minutes = Column(Integer, nullable = True)

    created_at = Column(DateTime, nullable = False, default = get_current_time_gmt)
