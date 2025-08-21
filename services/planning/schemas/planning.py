'''
    Pydantic schemas for Planning microservice.
'''
from typing import List, Optional
from datetime import date, datetime
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict

class PlanningStatus(str, Enum):
    '''
        Enum to define the possible states of a planning.
    '''
    CREATED = 'CREATED'
    IN_PROGRESS = 'IN_PROGRESS'
    FINISHED = 'FINISHED'

class PlanningBaseSchema(BaseModel):
    '''
        Base schema with `from_attributes=True` enabled to handle
        ORM objects from SQLAlchemy.
    '''
    model_config = ConfigDict(from_attributes=True)

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

class MaterialAssignmentSchema(BaseModel):
    '''
        Schema for assigning materials to a planning.
    '''
    material_id: int = Field(
        ...,
        description = 'ID of the material being assigned.'
    )
    quantity_assigned: int = Field(
        ..., gt = 0,
        description = 'Quantity of the material assigned.'
    )

class MaterialAssignmentResponseSchema(MaterialAssignmentSchema):
    '''
        Response schema for material assignments, including its database ID and creation timestamp.
    '''
    id: int = Field(
        ...,
        description = 'Unique identifier for the material assignment record.'
    )
    created_at: datetime = Field(
        ...,
        description = 'Timestamp when the material assignment was created.'
    )

class PlanningDetailWithMaterialsSchema(PlanningDetailBaseSchema):
    '''
        Schema for creating a planning detail with associated material assignments.
    '''
    materials: List[MaterialAssignmentSchema] = Field(
        ...,
        description = 'List of materials assigned to this detail.'
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
        ..., ge=1, le=53,
        description = 'The week number for the planning.'
    )
    status: PlanningStatus = Field(
        PlanningStatus.CREATED,
        description = 'Current status of the planning.'
    )
    details: Optional[List[PlanningDetailWithMaterialsSchema]] = Field(
        None,
        description = 'List of planning details, including team, route, and materials.'
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
    # Note: For updates, handling nested lists is complex.
    # For now, we'll keep the top-level fields for simplicity.
    # We will create a separate endpoint for updating details.

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

class MaterialAssignmentUpdateSchema(BaseModel):
    '''
        Schema for updating a material assignment.
    '''
    quantity_used: Optional[int] = Field(
        None,
        description = 'Quantity of the material used during the activity.'
    )
    quantity_returned: Optional[int] = Field(
        None,
        description = 'Quantity of the material returned after the activity.'
    )
class PlanningDetailResponseSchema(PlanningBaseSchema, PlanningDetailBaseSchema):
    '''
        Response schema for planning details, including its database ID and creation timestamp.
    '''
    id: int = Field(
        ...,
        description='Unique identifier for the planning detail record.'
    )
    created_at: datetime = Field(
        ...,
        description='Timestamp when the detail was created.'
    )

class PlanningFilterSchema(BaseModel):
    '''
        Schema to encapsulate filtering parameters for plannings.
    '''
    company_id: Optional[int] = None
    team_id: Optional[int] = None
    service_id: Optional[int] = None
    planned_route_id: Optional[int] = None
