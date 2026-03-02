'''
    Trade Schemas (Request/Response)
'''
from typing import List, Optional
from datetime import datetime
from fastapi import Query
from pydantic import BaseModel, Field
from schemas.common import BaseSchema
from schemas.pos import PointOfSaleNestedResponseSchema

# --- A.3. TRADE PLANNING SCHEMAS ---

class TradePlanningBaseSchema(BaseSchema):
    '''
        Base schema for Trade Planning fields.
    '''
    company_id: int = Field(
        ...,
        description = 'ID of the company that owns this planning record.'
    )
    planning_id: int = Field(
        ...,
        description = 'ID from the PLANNING microservice.'
    )
    user_id: int = Field(
        ...,
        description = 'ID of the user assigned to this plan (from frontend).'
    )
    point_of_sale_id: int = Field(
        ...,
        description = 'ID of the Point of Sale (from t_points_of_sale).'
    )
    planned_workload_minutes: int = Field(
        ...,
        ge = 0,
        description = 'Planned workload in minutes (Business Rule).'
    )
    status: Optional[str] = Field(
        'PENDING',
        max_length = 20,
        description = 'Status of this planning entry (e.g., PENDING, COMPLETED).'
    )
    comments: Optional[str] = Field(
        None,
        description = 'Optional comments for this planning entry.'
    )

class TradePlanningCreateSchema(TradePlanningBaseSchema):# pylint: disable=too-few-public-methods
    '''
        Schema for creating a new Trade Planning entry.
    '''
    # pass

class TradePlanningUpdateSchema(BaseSchema):
    '''
        Schema for updating an existing Trade Planning entry.
    '''
    # Only status and comments are updatable.
    # To change core data, delete and recreate.
    status: Optional[str] = Field(
        None,
        max_length = 20,
        description = 'New status for the planning entry.'
    )
    comments: Optional[str] = Field(
        None,
        description = 'Optional comments for this planning entry.'
    )
    planned_workload_minutes: Optional[int] = Field(
        None,
        ge = 0,
        description = 'Planned workload in minutes (Business Rule).'
    )

class TradePlanningResponseSchema(TradePlanningBaseSchema):
    '''
        Response schema for a Trade Planning entry.
    '''
    id: int
    planning_id: Optional[int]
    is_adhoc: bool
    justification: Optional[str]

    actual_workload_minutes: Optional[int]
    workload_difference_minutes: Optional[int]
    created_at: Optional[datetime]

    point_of_sale: Optional[PointOfSaleNestedResponseSchema] = None
    attendances: List[AttendanceResponseSchema] = []

class TradePlanningFilterSchema(BaseModel):
    '''
        Schema to encapsulate filtering parameters for Trade Planning entries.
    '''
    company_id: int = Query(..., description = 'Company ID (Mandatory for filtering).')
    planning_id: Optional[int] = Query(None, description = 'Filter by PLANNING microservice ID.')
    user_id: Optional[int] = Query(None, description = 'Filter by User ID.')
    point_of_sale_id: Optional[int] = Query(None, description = 'Filter by Point of Sale ID.')
    status: Optional[str] = Query(None, description = 'Filter by status (e.g., PENDING).')

    class Config:# pylint: disable=too-few-public-methods
        '''
        Pydantic config.
        '''
        arbitrary_types_allowed = True

class TradePlanningListResponseSchema(BaseSchema):
    '''
        Response schema for a paginated list of Trade Planning entries.
    '''
    items: List[TradePlanningResponseSchema]
    total: int

# --- Schema for Workload Calculation Endpoint (PATCH) ---
class TradePlanningWorkloadUpdateSchema(BaseSchema):
    '''
        Schema for the PATCH endpoint to calculate and update workload.
        Frontend provides the check-in and check-out times.
    '''
    check_in_time: datetime = Field(
        ...,
        description = 'Actual check-in time from LOCALIZATION (t_attendances).'
    )
    check_out_time: datetime = Field(
        ...,
        description = 'Actual check-out time from LOCALIZATION (t_attendances).'
    )

# --- A.4. AGENDA DE CAMPO SCHEMAS ---
class TradePlanningAdHocCreateSchema(BaseSchema):
    '''
    Schema to create an Ad-Hoc visit (User decides to visit a POS not in the plan).
    '''
    company_id: int = Field(..., description = 'Company ID.')
    point_of_sale_id: int = Field(..., description = 'POS ID to visit.')
    user_id: int = Field(..., description = 'User creating the visit.')
    comments: Optional[str] = Field(None, description = 'Reason for the Ad-Hoc visit.')

class TradePlanningJustificationSchema(BaseSchema):
    '''
    Schema to justify why a planned visit was not performed or completed.
    '''
    justification: str = Field(
        ...,
        min_length = 5,
        description = 'Reason for not visiting (e.g., "Store Closed").'
    )

# --- A.5. ATTENDANCE SCHEMAS ---

class AttendanceBaseSchema(BaseSchema):
    '''
        Base schema for Attendance fields.
    '''
    company_id: int = Field(..., description = 'Company ID.')
    user_id: int = Field(..., description = 'User ID performing the visit.')
    trade_planning_id: int = Field(..., description = 'ID of the associated planning entry.')

class AttendanceCreateSchema(AttendanceBaseSchema):
    '''
        Schema for registering a new Check-In.
    '''
    check_in_latitude: float = Field(..., ge = -90.0, le = 90.0)
    check_in_longitude: float = Field(..., ge = -180.0, le = 180.0)
    check_in_time: Optional[datetime] = Field(None, description = 'Optional timestamp.')

class AttendanceCheckOutSchema(BaseSchema):
    '''
        Schema for updating an attendance with Check-Out data.
    '''
    check_out_latitude: float = Field(..., ge = -90.0, le = 90.0)
    check_out_longitude: float = Field(..., ge = -180.0, le = 180.0)
    check_out_time: Optional[datetime] = Field(None, description = 'Optional timestamp.')

class AttendanceResponseSchema(AttendanceBaseSchema):
    '''
        Response schema for an Attendance record.
    '''
    id: int
    check_in_time: Optional[datetime]
    check_in_latitude: Optional[float]
    check_in_longitude: Optional[float]
    check_in_distance_error: Optional[float]

    check_out_time: Optional[datetime]
    check_out_latitude: Optional[float]
    check_out_longitude: Optional[float]
    check_out_distance_error: Optional[float]

    duration_minutes: Optional[int]
    created_at: Optional[datetime]
