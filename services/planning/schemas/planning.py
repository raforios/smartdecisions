# `schemas/planning.py`

'''
    Pydantic schemas for Planning microservice.
'''
from typing import Optional
from datetime import date, datetime
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict

class PlanningStatus(str, Enum):
    '''
        Enum to define the possible states of a planning.
    '''
    CREATED = 'created'
    IN_PROGRESS = 'in_progress'
    FINISHED = 'finished'

class PlanningBaseSchema(BaseModel):
    '''
        Base schema with `from_attributes=True` enabled to handle
        ORM objects from SQLAlchemy.
    '''
    model_config = ConfigDict(from_attributes=True)

class PlanningCreateSchema(BaseModel):
    '''
        Schema for creating a new planning record.
    '''
    user_id: int = Field(
        ...,
        description = 'ID of the user creating the planning.'
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
        PlanningStatus.CREATED,
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

class PlanningDetailBase(BaseModel):
    '''
        Base schema for planning details.
    '''
    team_id: int = Field(
        ...,
        description = 'ID of the assigned team or group.'
    )
    planned_route_id: int = Field(
        ...,
        description = 'ID of the planned route from the Localization microservice.'
    )

class PlanningDetailCreateSchema(PlanningDetailBase):
    '''
        Schema for creating a planning detail record.
    '''
    planning_id: int = Field(
        ...,
        description = 'ID of the parent planning record.'
    )

class PlanningDetailResponseSchema(PlanningBaseSchema, PlanningDetailBase):
    '''
        Response schema for planning details.
    '''
    id: int = Field(
        ...,
        description = 'Unique identifier for the planning detail record.'
    )
    created_at: datetime = Field(
        ...,
        description = 'Timestamp when the detail was created.'
    )

class MaterialAssignmentSchema(BaseModel):
    '''
        Schema for assigning materials to a planning.
    '''
    planning_detail_id: int = Field(
        ...,
        description = 'ID of the planning detail this material is assigned to.'
    )
    material_id: int = Field(
        ...,
        description = 'ID of the material being assigned.'
    )
    quantity_assigned: float = Field(
        ..., gt = 0,
        description = 'Quantity of the material assigned.'
    )
    quantity_used: Optional[float] = Field(
        None, gt = 0,
        description = 'Quantity of the material used during the activity.'
    )
    quantity_returned: Optional[float] = Field(
        None, gt = 0,
        description = 'Quantity of the material returned after the activity.'
    )
