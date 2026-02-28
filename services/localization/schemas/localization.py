'''
    Localization Schemas (Request/Response)
'''
from typing import List, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict

class PlannedRouteStatusEnum(str, Enum):
    '''
        Enum for the status of a planned route.
    '''
    ACTIVE = 'ACTIVE'
    INACTIVE = 'INACTIVE'
    IN_CREATION = 'IN CREATION'

class LocalizationBaseSchema(BaseModel):
    '''
        Base schema with `from_attributes=True` enabled to handle
        ORM objects like those from SQLAlchemy.
    '''
    model_config = ConfigDict(from_attributes=True)

class PointBase(BaseModel):
    '''
        Base schema for a geographical point.
    '''
    latitude: float = Field(
        ..., ge = -90.0, le = 90.0,
        description = 'The latitude of the geographical point.'
    )
    longitude: float = Field(
        ..., ge = -180.0, le = 180.0,
        description = 'The longitude of the geographical point.'
    )

class PlannedPointSchema(PointBase, LocalizationBaseSchema):
    '''
        Schema for a point in a planned route.
    '''
    point_name: str = Field(
        ..., max_length = 100,
        description = 'Name of the planned point, e.g., "Office A".'
    )
    secuencial: int = Field(
        ..., gt = 0,
        description = 'The sequential order of the planned point in the route.'
    )
    reference_data: Optional[str] = Field(
        None, max_length = 255,
        description = 'Additional reference data or notes for the point.'
    )

class PlannedPointResponseSchema(PlannedPointSchema, LocalizationBaseSchema):
    '''
        Response schema for a planned point, including the database ID.
    '''
    id: int
    created_at: datetime
    planned_route_id: int

class PlannedPointCreateSchema(PointBase):
    '''
        Schema for adding a new point to a planned route.
    '''
    point_name: str = Field(
        ..., max_length = 100,
        description = 'Name of the planned point, e.g., "Office A".'
    )
    secuencial: int = Field(
        ..., gt = 0,
        description = 'The sequential order of the planned point in the route.'
    )
    reference_data: Optional[str] = Field(
        None, max_length = 255,
        description = 'Additional reference data or notes for the point.'
    )

class PlannedPointUpdateSchema(BaseModel):
    '''
        Schema para actualizar un punto planificado.
    '''
    secuencial: Optional[int] = Field(
        None,
        description = 'The sequential order of the planned point in the route.'
    )
    point_name: Optional[str] = Field(
        None,
        description = 'Name of the planned point, e.g., "Office A".'
    )
    reference_data: Optional[str] = Field(
        None,
        description = 'Additional reference data or notes for the point.'
    )
class PlannedRouteCreateSchema(BaseModel):
    '''
        Schema for creating a planned route.
    '''
    route_name: str = Field(
        ..., max_length = 150,
        description = 'Name of the planned route.'
    )
    route_code: str = Field(
        ..., max_length = 50,
        description = 'Unique code for the planned route.'
    )
    description: Optional[str] = Field(
        None, max_length = 500,
        description = 'Description of the route.'
    )
    company_id: int = Field(
        ...,
        description = 'ID of the company creating the route.'
    )
    app_id: int = Field(
        ...,
        description = 'ID of the application that uses the service.'
    )
    city_id: int = Field(
        ...,
        description = 'ID of the city associated with the planned route.'
    )
    points: List[PlannedPointSchema] = Field(
        ...,
        description = 'A list of geographical points for the route.'
    )

class PlannedRouteResponseSchema(PlannedRouteCreateSchema, LocalizationBaseSchema):
    '''
        Response schema for a planned route, including the database ID.
    '''
    id: int
    created_at: datetime
    points: List[PlannedPointResponseSchema]

class PlannedRouteUpdateSchema(BaseModel):
    '''
        Schema for updating specific fields of a planned route.
        All fields are optional for partial updates.
    '''
    route_name: Optional[str] = Field(
        None, max_length = 150,
        description = 'Updated name of the planned route.'
    )
    route_code: Optional[str] = Field(
        None, max_length = 50,
        description = 'Updated unique code for the planned route.'
    )
    description: Optional[str] = Field(
        None, max_length = 500,
        description = 'Updated description of the route.'
    )
    city_id: Optional[int] = Field(
        None,
        description = 'Updated ID of the city associated with the planned route.'
    )

class PlannedRouteListResponseSchema(LocalizationBaseSchema):
    '''
        Response schema for a list of planned routes. This is the missing class
        used by the list and filter endpoints.
    '''
    id: int
    route_name: str
    route_code: str
    description: Optional[str]
    company_id: int
    app_id: int
    city_id: int
    created_at: datetime
    status: PlannedRouteStatusEnum
    points: List[PlannedPointResponseSchema]

class PlannedRouteUpdateStatusSchema(BaseModel):
    '''
        Schema for updating a planned route's status.
    '''
    status: PlannedRouteStatusEnum = Field(
        ...,
        description = 'New status for the planned route.'
    )

class ExecutedRouteCreateSchema(BaseModel):
    '''
        Schema for creating a new executed route instance.
    '''
    user_id: int = Field(
        ...,
        description = 'ID of the user for this executed route.'
    )
    service_id: int = Field(
        ...,
        description = 'ID of the service associated with this executed route.'
    )
    start_time: datetime = Field(
        ...,
        description = 'Date Time recived from frontend app.'
    )
    planned_route_id: Optional[int] = Field(
        None,
        description = 'ID of the planned route to which this executed route corresponds.'
    )
    start_latitude: float = Field(
        ..., ge = -90.0, le = 90.0,
        description = 'The latitude of the executed start point.'
    )
    start_longitude: float = Field(
        ..., ge = -180.0, le = 180.0,
        description = 'The longitude of the executed start point.'
    )
    max_distance_start_point: float = Field(
        ..., gt = 0,
        description = 'The maximum allowed distance (in meters) from the start point.'
    )

class ExecutedRouteResponseSchema(ExecutedRouteCreateSchema, LocalizationBaseSchema):
    '''
        Response schema for a created executed route, including the database ID.
    '''
    id: int
    start_time: datetime
    end_time: Optional[datetime]
    start_latitude: float
    start_longitude: float
    max_distance_start_point: float
    end_latitude: Optional[float] = None
    end_longitude: Optional[float] = None
    max_distance_end_point: Optional[float] = None

class ExecutedRouteUpdateSchema(BaseModel):
    '''
        Schema for updating an executed route's end time.
    '''
    end_time: datetime = Field(
        ...,
        description = 'Timestamp when the executed route was finished.'
    )
    end_latitude: float = Field(
        ..., ge = -90.0, le = 90.0,
        description = 'The latitude of the executed end point.'
    )
    end_longitude: float = Field(
        ..., ge = -180.0, le = 180.0,
        description = 'The longitude of the executed end point.'
    )
    max_distance_end_point: float = Field(
        ..., gt = 0,
        description = 'The maximum allowed distance (in meters) from the end point.'
    )

class ExecutedPointCreateSchema(PointBase):
    '''
        Schema for a point in an executed route, sent from a mobile device.
    '''
    executed_route_id: int = Field(
        ...,
        description = 'ID of the executed route this point belongs to.'
    )
    timestamp: datetime = Field(
        ...,
        description = 'Timestamp when the point was registered.'
    )

class ExecutedPointResponseSchema(ExecutedPointCreateSchema, LocalizationBaseSchema):
    '''
        Response schema for an executed point, including the database ID.
    '''
    id: int

class ExecutedRouteComparisonSchema(BaseModel):
    '''
        Schema for a single executed route for comparison purposes.
    '''
    id: int
    user_id: int
    service_id: int
    start_time: datetime
    end_time: Optional[datetime]
    points: List[ExecutedPointResponseSchema]

class PlannedRouteComparisonSchema(BaseModel):
    '''
        Schema for a planned route in the comparison response.
    '''
    id: int
    route_name: str
    points: List[PlannedPointSchema] # Reutilizamos el esquema existente

class RouteComparisonFullResponseSchema(BaseModel):
    '''
        Response schema for the full route comparison endpoint.
    '''
    planned_route: PlannedRouteComparisonSchema
    executed_routes: List[ExecutedRouteComparisonSchema]

class PointsVisitedResponseSchema(BaseModel):
    '''
        Response schema for the points visited statistics endpoint.
    '''
    user_id: int
    total_points_visited: int
    points_details: List[dict] # Use dict for flexible point details

class RouteComparisonSchema(LocalizationBaseSchema):
    '''
        Schema for a single route comparison result.
    '''
    planned_route_id: int
    planned_route_name: str
    executed_route_id: Optional[int]
    match_percentage: float = Field(
        ..., ge = 0.0, le = 100.0,
        description='Percentage of the executed route that matches the planned one.'
    )
    points_visited_count: int

class RouteComparisonsResponseSchema(LocalizationBaseSchema):
    '''
        Response schema for the route comparisons endpoint.
    '''
    comparisons: List[RouteComparisonSchema]

class PlannedRouteFilterRequestSchema(BaseModel):
    '''
        Schema to filter planned routes via a POST request body.
    '''
    planned_route_ids: Optional[List[int]] = Field(None,
                                description='List of planned route IDs to filter.')
    route_code: Optional[str] = Field(None, description='Unique code of the planned route.')
    route_name: Optional[str] = Field(None, description='Name of the planned route.')
    route_status: Optional[PlannedRouteStatusEnum] = Field(None,
                            description='Status of the planned route.')
    company_id: Optional[int] = Field(None, description='ID of the company who owns the route.')
    city_id: Optional[int] = Field(None,
                            description='ID of the city associated with the planned route.')


class PlannedRouteBulkCreateSchema(BaseModel):
    '''
        Schema for creating a planned route via bulk upload.
        This schema maps to the CSV format.
    '''
    route_name: str = Field(..., max_length = 150)
    route_code: str = Field(..., max_length = 50)
    description: Optional[str] = Field(None, max_length = 1000)
    company_id: int
    app_id: int
    city_id: int
    point_name: str = Field(..., max_length = 100)
    secuencial: int = Field(..., gt = 0)
    latitude: float = Field(..., ge = -90.0, le = 90.0)
    longitude: float = Field(..., ge = -180.0, le = 180.0)
    reference_data: Optional[str] = Field(None, max_length = 255)

class BulkUploadResponseSchema(BaseModel):
    '''
        Response schema for the bulk upload endpoint.
    '''
    message: str
    routes_created: int
    points_created: int

class LastKnownLocationResponseSchema(BaseModel):
    '''
        Response schema for the last known location of a single user.
    '''
    user_id: int = Field(..., description = 'ID of the user being tracked.')
    service_id: int = Field(..., description = 'ID of the service associated.')
    last_latitude: float = Field(..., description = 'The last reported latitude.')
    last_longitude: float = Field(..., description = 'The last reported longitude.')
    last_timestamp: datetime = Field(..., description = 'Timestamp of the last reported location.')

class GroupLastKnownLocationsResponseSchema(BaseModel):
    '''
        Response schema for a list of last known locations for multiple users.
    '''
    locations: List[LastKnownLocationResponseSchema]

# --- ATTENDANCE SEARCH SCHEMAS (Integration with TRADE) ---
