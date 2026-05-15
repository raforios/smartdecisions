'''
    Trade Schemas — Planning, Routes, Planned Points, and Attendances.
'''
from datetime import date, datetime
from typing import List, Optional
from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field

from schemas.common import BaseSchema


# ====================================================================
# PLANNED POINT (detail of a route)
# ====================================================================
class PlannedPointBaseSchema(BaseSchema):
    '''
        Shared fields for a planned point on a route.
    '''
    sequence: int = Field(
        ...,
        ge = 1,
        description = 'Visit order in the route (1, 2, 3...).'
    )
    point_of_sale_id: int = Field(
        ...,
        description = 'POS identifier for this stop.'
    )
    planned_workload_minutes: int = Field(
        ...,
        ge = 0,
        description = 'Budgeted time in minutes for this visit.'
    )
    is_adhoc: bool = Field(
        False,
        description = 'True when the visit is off-route (ad-hoc).'
    )
    justification: Optional[str] = Field(
        None,
        description = 'Justification text when the point is ad-hoc or skipped.'
    )
    status: Optional[str] = Field(
        'PENDING',
        max_length = 20,
        description = 'Lifecycle status of this planned visit.'
    )
    comments: Optional[str] = Field(
        None,
        description = 'Operator comments captured during execution.'
    )


class PlannedPointCreateSchema(PlannedPointBaseSchema):
    '''
        Schema to create a planned point inline with its parent route.
    '''


class PlannedPointUpdateSchema(BaseSchema):
    '''
        Update schema. All fields optional. Includes execution metrics.
    '''
    sequence: Optional[int] = Field(None, ge = 1)
    point_of_sale_id: Optional[int] = None
    planned_workload_minutes: Optional[int] = Field(None, ge = 0)
    actual_workload_minutes: Optional[int] = Field(None, ge = 0)
    workload_difference_minutes: Optional[int] = None
    is_adhoc: Optional[bool] = None
    justification: Optional[str] = None
    status: Optional[str] = Field(None, max_length = 20)
    comments: Optional[str] = None


class PlannedPointResponseSchema(PlannedPointBaseSchema):
    '''
        Response schema for a planned point.
    '''
    id: int
    planned_route_id: int
    actual_workload_minutes: Optional[int] = None
    workload_difference_minutes: Optional[int] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes = True)


# ====================================================================
# PLANNED ROUTE (master)
# ====================================================================
class PlannedRouteBaseSchema(BaseSchema):
    '''
        Shared fields for a planned route master record.
    '''
    route_name: str = Field(..., max_length = 150)
    route_code: str = Field(..., max_length = 50)
    description: Optional[str] = None


class PlannedRouteCreateSchema(PlannedRouteBaseSchema):
    '''
        Schema for creating a planned route together with its points.
    '''
    company_id: int = Field(..., description = 'Owner company.')
    points: List[PlannedPointCreateSchema] = Field(
        default_factory = list,
        description = 'Optional initial points for the route.'
    )


class PlannedRouteUpdateSchema(BaseSchema):
    '''
        Schema for updating a planned route. Points are managed via their
        own endpoints to keep this update focused on the master record.
    '''
    route_name: Optional[str] = Field(None, max_length = 150)
    route_code: Optional[str] = Field(None, max_length = 50)
    description: Optional[str] = None


class PlannedRouteResponseSchema(PlannedRouteBaseSchema):
    '''
        Response schema for a planned route, including its points.
    '''
    id: int
    company_id: int
    points: List[PlannedPointResponseSchema] = []
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes = True)


class PlannedRouteListResponseSchema(BaseSchema):
    '''
        Paginated list of planned routes.
    '''
    items: List[PlannedRouteResponseSchema]
    total: int


class PlannedRouteFilterSchema(BaseModel):
    '''
        Filter schema for the planned routes list endpoint.
    '''
    company_id: int = Query(..., description = 'Company ID (mandatory).')
    route_code: Optional[str] = Query(None, description = 'Filter by exact route_code.')
    route_name: Optional[str] = Query(None, description = 'Filter by name (partial match).')

    model_config = ConfigDict(arbitrary_types_allowed = True)


# ====================================================================
# TRADE PLANNING DETAIL (route x day)
# ====================================================================
class TradePlanningDetailBaseSchema(BaseSchema):
    '''
        Shared fields for a planning detail row.
    '''
    planned_route_id: int = Field(..., description = 'Planned route to execute that day.')
    date_of_day: date = Field(..., description = 'Specific date the route is run.')


class TradePlanningDetailCreateSchema(TradePlanningDetailBaseSchema):
    '''
        Schema for creating a planning detail row inline with its parent.
    '''


class TradePlanningDetailResponseSchema(TradePlanningDetailBaseSchema):
    '''
        Response schema for a planning detail row.
    '''
    id: int
    planning_id: int
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes = True)


# ====================================================================
# TRADE PLANNING (campaign master)
# ====================================================================
class TradePlanningBaseSchema(BaseSchema):
    '''
        Shared fields for a planning campaign.
    '''
    planning_name: str = Field(..., max_length = 150)
    description: Optional[str] = None
    team_id: int = Field(..., description = 'Team identifier from the frontend.')
    start_date: date
    end_date: date
    status: Optional[str] = Field('DRAFT', max_length = 20)


class TradePlanningCreateSchema(TradePlanningBaseSchema):
    '''
        Schema for creating a planning campaign with optional inline details.
    '''
    company_id: int = Field(..., description = 'Owner company.')
    details: List[TradePlanningDetailCreateSchema] = Field(
        default_factory = list,
        description = 'Optional inline detail rows (route per day).'
    )


class TradePlanningUpdateSchema(BaseSchema):
    '''
        Update schema for a planning campaign.
    '''
    planning_name: Optional[str] = Field(None, max_length = 150)
    description: Optional[str] = None
    team_id: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[str] = Field(None, max_length = 20)


class TradePlanningResponseSchema(TradePlanningBaseSchema):
    '''
        Response schema for a planning campaign.
    '''
    id: int
    company_id: int
    details: List[TradePlanningDetailResponseSchema] = []
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes = True)


class TradePlanningListResponseSchema(BaseSchema):
    '''
        Paginated list of planning campaigns.
    '''
    items: List[TradePlanningResponseSchema]
    total: int


class TradePlanningFilterSchema(BaseModel):
    '''
        Filter schema for the planning list endpoint.
    '''
    company_id: int = Query(..., description = 'Company ID (mandatory).')
    team_id: Optional[int] = Query(None, description = 'Filter by team.')
    status: Optional[str] = Query(None, description = 'Filter by status.')
    date_from: Optional[date] = Query(None, description = 'Lower bound for end_date.')
    date_to: Optional[date] = Query(None, description = 'Upper bound for start_date.')

    model_config = ConfigDict(arbitrary_types_allowed = True)


# ====================================================================
# BULK SCHEMAS (CSV ingestion)
# ====================================================================
class PlannedRouteBulkItemSchema(BaseSchema):
    '''
        Single CSV row for the planned routes bulk upload. Each row produces
        either a new route (when route_code is unseen) or appends a point to
        an existing route within the same company.
    '''
    company_id: int
    route_code: str = Field(..., max_length = 50)
    route_name: str = Field(..., max_length = 150)
    route_description: Optional[str] = None

    sequence: int = Field(..., ge = 1)
    point_of_sale_id: int
    planned_workload_minutes: int = Field(..., ge = 0)
    is_adhoc: bool = False
    justification: Optional[str] = None
    point_status: Optional[str] = Field('PENDING', max_length = 20)
    point_comments: Optional[str] = None


class TradePlanningBulkItemSchema(BaseSchema):
    '''
        Single CSV row for the planning campaigns bulk upload. Each row maps
        a planning campaign (uniqueness by company + planning_name + team)
        plus its day-by-day route assignment.
    '''
    company_id: int
    planning_name: str = Field(..., max_length = 150)
    description: Optional[str] = None
    team_id: int
    start_date: date
    end_date: date
    status: Optional[str] = Field('DRAFT', max_length = 20)

    # Detail row
    planned_route_code: str = Field(..., max_length = 50)
    date_of_day: date


# ====================================================================
# ATTENDANCE
# ====================================================================
class AttendanceCheckInSchema(BaseSchema):
    '''
        Payload for the check-in endpoint.
    '''
    company_id: int
    user_id: int
    trade_planned_point_id: int = Field(
        ...,
        description = 'Planned point being visited.'
    )
    check_in_latitude: float
    check_in_longitude: float


class AttendanceCheckOutSchema(BaseSchema):
    '''
        Payload for the check-out endpoint.
    '''
    check_out_latitude: float
    check_out_longitude: float
    comments: Optional[str] = None


class AttendanceResponseSchema(BaseSchema):
    '''
        Response schema for an attendance row.
    '''
    id: int
    company_id: int
    user_id: int
    trade_planned_point_id: int
    check_in_time: Optional[datetime] = None
    check_in_latitude: Optional[float] = None
    check_in_longitude: Optional[float] = None
    check_in_distance_error: Optional[float] = None
    check_out_time: Optional[datetime] = None
    check_out_latitude: Optional[float] = None
    check_out_longitude: Optional[float] = None
    check_out_distance_error: Optional[float] = None
    duration_minutes: Optional[int] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes = True)


class AttendanceLookupFilterSchema(BaseModel):
    '''
        Filter schema for the attendances lookup endpoint. Returns the list
        of attendances matching `pos_id` and/or `user_id` inside a company,
        optionally bound by a date range applied to `check_in_time`.
        - Without dates: every attendance is returned.
        - With both dates: results are restricted to the inclusive range.
        - With only `date_from`: results equal or later than that date.
        - With only `date_to`: results equal or earlier than that date.
    '''
    company_id: int = Query(..., description = 'Company ID (mandatory).')
    pos_id: Optional[int] = Query(
        None,
        description = 'POS ID. Returns attendances whose planned point targets this POS.'
    )
    user_id: Optional[int] = Query(
        None,
        description = 'Operator user ID. Returns attendances owned by this user.'
    )
    date_from: Optional[date] = Query(
        None,
        description = 'Lower bound (inclusive) for the attendance check-in date.'
    )
    date_to: Optional[date] = Query(
        None,
        description = 'Upper bound (inclusive) for the attendance check-in date.'
    )

    model_config = ConfigDict(arbitrary_types_allowed = True)


class AttendanceListResponseSchema(BaseSchema):
    '''
        Paginated list of attendances.
    '''
    items: List[AttendanceResponseSchema]
    total: int
