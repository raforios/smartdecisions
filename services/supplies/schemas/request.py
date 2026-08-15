'''
    Pydantic schemas for supply requests (REQUESTER and WAREHOUSE_MANAGER flows).
'''
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from schemas.enums import RequestStatusEnum


class _Base(BaseModel):
    '''
        Shared base config so SQLAlchemy objects can be serialized.
    '''
    model_config = ConfigDict(from_attributes = True)


# --------------------------------------------------------------------------- #
# Create                                                                      #
# --------------------------------------------------------------------------- #
class RequestDetailCreateSchema(BaseModel):
    '''
        Single line of a new supply request.
    '''
    item_id: int = Field(..., gt = 0)
    requested_qty: Decimal = Field(..., gt = 0)


class RequestCreateSchema(BaseModel):
    '''
        Payload to create a supply request (flow 1: REQUESTER).

        The requester identity fields are printed on the SOLICITUD and ENTREGA
        forms that get signed on paper, so they are captured with the request
        instead of being derived from the login address.
    '''
    requester_name: str = Field(..., min_length = 3, max_length = 200)
    requester_position: str = Field(..., min_length = 2, max_length = 200)
    requester_unit: str = Field(..., min_length = 2, max_length = 200)
    notes: Optional[str] = Field(None, max_length = 1000)
    details: List[RequestDetailCreateSchema] = Field(..., min_length = 1)


# --------------------------------------------------------------------------- #
# State transitions                                                           #
# --------------------------------------------------------------------------- #
class RequestTransitionSchema(BaseModel):
    '''
        Payload for state transitions that may carry a textual reason
        (rejection, cancellation).
    '''
    reason: Optional[str] = Field(None, max_length = 500)


class RequestDeliverDetailSchema(BaseModel):
    '''
        Quantity actually delivered for a line. Allows partial deliveries
        without breaking the requested totals.
    '''
    item_id: int = Field(..., gt = 0)
    delivered_qty: Decimal = Field(..., gt = 0)


class RequestDeliverSchema(BaseModel):
    '''
        Payload to mark a request as DELIVERED. If `details` is omitted, the
        service will deliver the originally requested quantities.
    '''
    details: Optional[List[RequestDeliverDetailSchema]] = None
    notes: Optional[str] = Field(None, max_length = 500)


# --------------------------------------------------------------------------- #
# Filters                                                                     #
# --------------------------------------------------------------------------- #
class RequestFilterSchema(BaseModel):
    '''
        Query filters supported by GET /requests.
    '''
    status: Optional[RequestStatusEnum] = None
    requester_email: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    skip: int = Field(0, ge = 0)
    limit: int = Field(100, ge = 1, le = 500)


# --------------------------------------------------------------------------- #
# Response shapes                                                             #
# --------------------------------------------------------------------------- #
class RequestDetailResponseSchema(_Base):
    '''
        Line of a request as returned by the API. The item identity travels
        with the line so the printable forms do not need a second round-trip.
    '''
    id: int
    item_id: int
    item_code: Optional[str] = None
    item_name: Optional[str] = None
    unit: Optional[str] = None
    requested_qty: Decimal
    delivered_qty: Decimal


class RequestStatusHistorySchema(_Base):
    '''
        Single status transition entry.
    '''
    id: int
    from_status: Optional[RequestStatusEnum]
    to_status: RequestStatusEnum
    changed_by: str
    changed_at: datetime
    reason: Optional[str]


class RequestResponseSchema(_Base):
    '''
        Request header (without details) for list views.
    '''
    id: int
    code: str
    requester_email: str
    requester_name: Optional[str]
    requester_position: Optional[str]
    requester_unit: Optional[str]
    status: RequestStatusEnum
    notes: Optional[str]
    requested_at: datetime
    processed_at: Optional[datetime]
    processed_by: Optional[str]
    delivered_at: Optional[datetime]
    delivered_by: Optional[str]
    closed_at: Optional[datetime]


class RequestDetailedResponseSchema(RequestResponseSchema):
    '''
        Request with details and status history, for the /requests/{id} view.
    '''
    details: List[RequestDetailResponseSchema]
    status_history: List[RequestStatusHistorySchema]
