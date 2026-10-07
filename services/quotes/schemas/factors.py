'''
    Pydantic V2 DTOs for the fluctuating factors.

    The exchange rate was the first one, and it taught the shape: a figure
    that moves on its own, that nobody on the team decides, and that changes
    what a report means. Fuel is the next one, and there will be others —
    a tariff, a minimum wage, an index.

    So they are NOT environment variables. A number that changes every week
    and that the client reads off an invoice cannot live in a file only the
    deployment can touch: it lives in a table, it is loaded by hand or by API,
    and it carries the day it was true.

    A factor is a figure and whether it counts, nothing more. Both things
    move, and both keep their history: a report of March has to be
    reproducible in September.
'''
from datetime import date
from enum import Enum
from pydantic import BaseModel, Field


class FactorError(str, Enum):
    '''
        Why a factor request could not be served.
    '''
    FACTOR_NOT_FOUND = 'FACTOR_NOT_FOUND'
    NO_VALUE_FOR_DATE = 'NO_VALUE_FOR_DATE'
    EMPTY_LOAD = 'EMPTY_LOAD'


class FactorStatus(str, Enum):
    """
        Whether a factor counts.

        A factor is born ACTIVE and stays that way until somebody turns it
        off. Turning it off is how a factor stops affecting results without
        being deleted: the readings it already has, and the history of what
        it weighed, stay exactly where they are — a report from the month it
        was active still has to be reproducible.
    """
    ACTIVE = 'ACTIVE'
    INACTIVE = 'INACTIVE'


class FactorDefinitionSchema(BaseModel):
    '''
        What a fluctuating factor is, before any value of it.
    '''
    code: str = Field(..., min_length = 1, max_length = 40,
                      description = 'Stable identifier, e.g. DIESEL.')
    name: str = Field(..., min_length = 1, max_length = 150)
    unit: str = Field(..., min_length = 1, max_length = 40,
                      description = 'What the value is measured in, e.g. Bs/litro.')
    source: str | None = Field(
        None, max_length = 255,
        description = 'Where the value comes from, so a reader can check it.'
    )
    status: FactorStatus = Field(
        FactorStatus.ACTIVE,
        description = 'Born ACTIVE. Only the active ones are taken into account; '
                      'an inactive one keeps its readings and simply stops counting.'
    )
    effective_from: date | None = Field(
        None,
        description = 'The day this status starts to apply. '
                      'Today when left out. It exists because a client loading '
                      'a year of history needs the factor to have counted during '
                      'that year: without it, declaring it today would leave '
                      'every past period with no status, and a report of March '
                      'could never be reproduced.'
    )


class FactorValueSchema(BaseModel):
    '''
        What a factor was worth on a day.
    '''
    factor_date: date
    value: float = Field(..., description = 'The figure, in the factor\'s unit.')


class FactorValuesLoadSchema(BaseModel):
    '''
        Values pushed by hand from a screen, or by an ERP.

        A load is idempotent by day: sending the same day again corrects it
        instead of adding a second truth for it.
    '''
    values: list[FactorValueSchema] = Field(..., min_length = 1)


class FactorResponseSchema(FactorDefinitionSchema):
    '''
        A factor as it is stored, with its latest reading.
    '''
    latest_date: str | None = None
    latest_value: float | None = None
    updated_at: str


class FactorSeriesResponseSchema(BaseModel):
    '''
        The series of one factor over a window.
    '''
    code: str
    unit: str
    values: list[FactorValueSchema]


class FactorStateSchema(BaseModel):
    """
        What a factor was, on one day.

        Both things about a factor move: the reading and whether it counted.
        A report of March has to be computed with March's, not with today's —
        otherwise turning a factor off in September silently rewrites every
        figure produced before it.

        `active` false does not mean the factor is gone: it means that on that
        day it was not counting, and the value it had is still there for the
        periods when it was.
    """
    code: str
    unit: str
    active: bool
    value: float | None = Field(
        None, description = 'The reading in force that day. None when nothing '
                            'had been loaded yet.'
    )
    as_of: str = Field(..., description = 'The day this state refers to.')


class FactorListResponseSchema(BaseModel):
    '''
        Every factor the account declared.
    '''
    factors: list[FactorResponseSchema]
    total: int = Field(..., ge = 0)


class TransportCostSchema(BaseModel):
    """
        What it costs to take a delivery over a distance, on a day.

        Local distribution only — the cost of getting the goods to the client.
        Import freight is another matter and is not this.

        The chain is deliberately shown whole and not just its total: a number
        a manager cannot take apart is a number they cannot argue with. Every
        figure is the one in force ON THAT DAY, so the cost of a route run in
        March is computed with March's fuel, not with today's.

        The vehicle comes back. A delivery route ends at the last client and
        returns empty, so the fuel is spent over twice the distance the route
        draws — the official cost models price a loaded kilometre above an
        average one for exactly this reason.
    """
    distance_km: float = Field(..., ge = 0, description = 'The route, one way.')
    round_trip_km: float = Field(
        ..., ge = 0,
        description = 'What the vehicle actually covers: the route and the empty '
                      'return. This is what the fuel is spent on.'
    )
    kilometres_per_litre: float = Field(
        ..., gt = 0,
        description = 'The fleet\'s ESTIMATED AVERAGE, measured on local delivery '
                      'and not taken from any manufacturer sheet — the fleet is '
                      'mixed and urban delivery consumes about twice what road '
                      'transport does. It is a factor like any other, so it is '
                      'entered, dated, and sharpened as the estimate improves.'
    )
    price_per_litre: float = Field(..., ge = 0, description = 'The fuel price factor.')
    litres: float = Field(..., ge = 0, description = 'round_trip_km / efficiency.')
    cost: float = Field(..., ge = 0, description = 'litres x price.')
    units: float | None = Field(
        None, gt = 0,
        description = 'Units carried, when the caller knows them. Given, the '
                      'answer also says what the trip costs per unit, which is '
                      'the figure that reaches the margin.'
    )
    cost_per_unit: float | None = Field(None, ge = 0)
    as_of: str = Field(..., description = 'The day every figure was read for.')
