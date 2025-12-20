'''
    Planning Schemas (Request/Response)
'''
from typing import List, Optional
from datetime import date, datetime
from enum import Enum
from fastapi import Query
from pydantic import BaseModel, Field, ConfigDict

class PlanningStatus(str, Enum):
    '''
        Enum to define the possible states of a planning.
    '''
    ACTIVE = 'ACTIVE'
    INACTIVE = 'INACTIVE'

class PlanningBaseSchema(BaseModel):
    '''
        Base schema with `from_attributes=True` enabled to handle
        ORM objects from SQLAlchemy.
    '''
    model_config = ConfigDict(from_attributes = True)

class PlanningDetailBaseSchema(BaseModel):
    '''
        Base schema for planning details.
    '''
    team_id: int = Field(
        ...,
        description = 'ID of the assigned team or group.'
    )
    service_id: int = Field(
        ...,
        description = 'ID of the service to which the schedule corresponds.'
    )
    planned_route_id: int = Field(
        ...,
        description = 'ID of the planned route from the Localization microservice.'
    )
    date_of_day: datetime = Field(
        ...,
        description = 'Date assigned for the detail.'
    )


class PlanningDetailCreateSchema(PlanningDetailBaseSchema):
    '''
        Schema for creating a planning detail record.
    '''
    planning_id: int = Field(
        ...,
        description = 'ID of the parent planning record.'
    )

class PlanningDetailUpdateSchema(PlanningDetailBaseSchema):
    '''
        Schema for updating a planning detail record.
    '''
    team_id: Optional[int] = Field(
        None,
        description = 'ID of the assigned team or group.'
    )
    service_id: Optional[int] = Field(
        None,
        description = 'ID of the service to which the schedule corresponds.'
    )
    planned_route_id: Optional[int] = Field(
        None,
        description = 'ID of the planned route from the Localization microservice.'
    )
    date_of_day: datetime = Field(
        None,
        description = 'Date assigned for the detail.'
    )

class PlanningCreateSchema(BaseModel):
    '''
        Schema for creating a new planning record.
    '''
    company_id: int = Field(
        ...,
        description = 'ID of the company creating the route.'
    )
    app_id: int = Field(
        ...,
        description = 'ID of the application that uses the service.'
    )
    planning_name: str = Field(
        ..., max_length = 255,
        description = 'Name of the planning.'
    )
    description: Optional[str] = Field(
        None, max_length = 500,
        description = 'A detailed description of the planning.'
    )
    start_date: date = Field(
        ...,
        description = 'Start date of the planning.'
    )
    end_date: date = Field(
        ...,
        description = 'End date of the planning.'
    )
    week_number: int = Field(
        ..., ge = 1, le = 53,
        description = 'The week number for the planning.'
    )
    status: PlanningStatus = Field(
        PlanningStatus.ACTIVE,
        description = 'Current status of the planning.'
    )
    details: List[PlanningDetailBaseSchema] = Field(
        default_factory = list,
        description = 'List of details for the planning.'
    )

class PlanningUpdateSchema(BaseModel):
    '''
        Schema for updating an existing planning record.
    '''
    planning_name: Optional[str] = Field(
        None, max_length = 255,
        description = 'Name of the planning.'
    )
    description: Optional[str] = Field(
        None, max_length = 500,
        description = 'A detailed description of the planning.'
    )
    start_date: Optional[date] = Field(
        None,
        description = 'Start date of the planning.'
    )
    end_date: Optional[date] = Field(
        None,
        description = 'End date of the planning.'
    )
    week_number: Optional[int] = Field(
        None, ge = 1, le = 53,
        description = 'The week number for the planning.'
    )
    status: Optional[PlanningStatus] = Field(
        None,
        description = 'Current status of the planning.'
    )

class PlanningResponseSchema(PlanningBaseSchema, PlanningCreateSchema):
    '''
        Response schema for a planning, including its database ID and creation timestamp.
    '''
    id: int = Field(
        ...,
        description = 'Unique identifier for the planning record.'
    )
    created_at: datetime = Field(
        ...,
        description = 'Timestamp when the planning was created.'
    )

class PlanningDetailResponseSchema(PlanningBaseSchema, PlanningDetailBaseSchema):
    '''
        Response schema for planning details, including its database ID and creation timestamp.
    '''
    id: int = Field(
        ...,
        description = 'Unique identifier for the planning detail record.'
    )
    created_at: datetime = Field(
        ...,
        description = 'Timestamp when the detail was created.'
    )

class PlanningFilterSchema(BaseModel):
    '''
        Schema to encapsulate filtering parameters for plannings.
    '''
    company_id: Optional[int] = Query(None, description = 'Company ID.')
    start_date: Optional[date] = Query(None, description = 'Start date of the planning.')
    end_date: Optional[date] = Query(None, description = 'End date of the planning.')
    team_id: Optional[int] = Query(None, description = 'Team ID.')
    service_id: Optional[int] = Query(None, description = 'Service ID.')
    planned_route_id: Optional[int] = Query(None,
                                    description = 'Planned Route ID.')
    date_of_day: Optional[date] = Query(None,
                                description = 'Date of the day assigned for the detail.')

    class Config:# pylint: disable=too-few-public-methods
        '''
            This setting allows the class to be instantiated without arguments in
            the @router.get() decorator.
        '''
        arbitrary_types_allowed = True

class PlanningBulkCreateSchema(BaseModel):
    '''
        Schema for creating planning records via bulk upload.
        This schema maps to the CSV format.
    '''
    company_id: int
    app_id: int
    planning_name: str
    description: str
    start_date: date
    end_date: date
    week_number: int
    team_id: int
    service_id: int
    planned_route_id: int
    date_of_day: date

class BulkUploadResponseSchema(BaseModel):
    '''
        Response schema for the bulk upload endpoint.
    '''
    message: str
    plannings_created: int
    details_created: int

class PlanningMonitorFilterSchema(BaseModel):
    '''
        Schema to encapsulate filtering parameters for the Affiliation Monitor.
    '''
    company_id: Optional[int] = Field(None, description = 'Company ID.')
    service_id: Optional[int] = Field(None, description = 'Service ID.')
    year: Optional[int] = Field(None, description = 'Year to filter.')
    period: Optional[str] = Field(None, description = 'Period to filter (e.g., Q1, January, 1).')
    team_ids: Optional[List[int]] = Field(None, description = 'List of team IDs.')
    user_ids: Optional[List[int]] = Field(None, description = 'List of user IDs.')

    class Config: # pylint: disable=too-few-public-methods
        '''
            This setting allows the class to be instantiated without arguments in
            the @router.get() decorator.
        '''
        arbitrary_types_allowed = True
