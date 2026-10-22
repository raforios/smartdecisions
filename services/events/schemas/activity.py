'''
    Recent activity of the platform: what the ADMIN's dashboard reads (ADMIN only).
'''
from pydantic import BaseModel, Field


class ActivityQuerySchema(BaseModel):
    '''
        Which services and how far back. The services are named by the caller:
        EVENTS records every product, its clients' included, and only the
        caller knows which ones its dashboard covers.
    '''
    microservices: str = Field(..., min_length = 1, max_length = 500,
                               description = 'Comma-separated service names, e.g. FINANCE,QUOTES.')
    hours: int = Field(12, ge = 1, le = 24, description = 'How many hours back.')


class HourBucket(BaseModel):
    '''
        The calls of one hour: answered well, and failed.
    '''
    hour: str = Field(..., description = 'Hour start, YYYY-MM-DDTHH in the service time zone.')
    ok: int = Field(..., description = 'Calls answered below 400.')
    errors: int = Field(..., description = 'Calls answered with 400 or more.')


class ServiceActivity(BaseModel):
    '''
        One service over the period.
    '''
    microservice: str
    total: int
    ok: int = Field(..., description = 'Answered below 400.')
    client_errors: int = Field(..., description = 'Answered 4xx.')
    server_errors: int = Field(..., description = 'Answered 5xx.')
    avg_response_ms: int | None = Field(None, description = 'Mean response time, when recorded.')
    buckets: list[HourBucket]


class RecentCall(BaseModel):
    '''
        One failed call, without its bodies.
    '''
    timestamp: str
    microservice: str
    method: str | None = None
    endpoint: str | None = None
    status_code: int
    user_id: str | None = Field(None, description = "The client's end user, when it sends one.")
    user_app: str | None = Field(None, description = 'Who called: the authenticated user.')
    response_time_ms: int | None = None


class RecentChange(BaseModel):
    '''
        One audited change, without its values.
    '''
    timestamp: str
    microservice: str
    entity_name: str | None = None
    entity_id: str | None = None
    action: str | None = None
    user_id: str | None = None


class ActivityResponseSchema(BaseModel):
    '''
        The period, each service, and what deserves a look first.
    '''
    since: str = Field(..., description = 'Start of the period.')
    hours: int
    services: list[ServiceActivity]
    latest_errors: list[RecentCall] = Field(..., description = 'Newest first.')
    latest_changes: list[RecentChange] = Field(..., description = 'Newest first.')
