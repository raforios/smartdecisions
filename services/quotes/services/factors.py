'''
    Fluctuating factors: figures that move on their own.

    The exchange rate was the first of them and it is served apart, because it
    has a publisher and a calendar of its own. This module holds the rest —
    fuel first — and the reason they are here and not in the `.env` is that
    the `.env` belongs to the deployment: a number the client reads off an
    invoice every week cannot need a release to change.

    So a factor is declared once, its values are loaded by hand from a screen
    or pushed by an ERP, and every value carries the day it was true. A load
    is idempotent by day: sending Monday again corrects Monday instead of
    leaving two truths for it.

    A factor is ONE figure —the price of a litre, the kilometres a litre
    gives— and whether it counts. What that figure then does belongs to
    whoever uses it: the cost of a local delivery is kilometres divided by
    the efficiency, times the price. That arithmetic is not a property of the
    factor, and an abstract "weight" on top of it meant nothing.
'''
from datetime import date as date_type

from boto3.resources.base import ServiceResource

from models.factors import FactorItem, FactorValueItem
from schemas.factors import (
    FactorDefinitionSchema,
    FactorStateSchema,
    TransportCostSchema,
    FactorStatus,
    FactorError,
    FactorListResponseSchema,
    FactorResponseSchema,
    FactorSeriesResponseSchema,
    FactorValueSchema
)
from services.crud import find_item_by_key, query_by_partition
from services.environment import load_and_validate_env_vars
from services.quotes_utils import to_dynamo
from services.exceptions import ResourceNotFoundError
from services.logger_config import custom_logger as logger
from services.utils import get_current_time_gmt

ENV_VARS = load_and_validate_env_vars({
    'FUEL_PRICE_FACTOR_CODE': str,
    'FUEL_EFFICIENCY_FACTOR_CODE': str,
    'DYNAMODB_TABLE_NAME_QUOTES_FACTORS': str,
    'DYNAMODB_TABLE_NAME_QUOTES_FACTOR_VALUES': str,
})
FACTORS_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_QUOTES_FACTORS']
FACTOR_VALUES_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_QUOTES_FACTOR_VALUES']
# Which declared factor plays each role in the transport cost. Named here and
# not written into the code because a fleet on gasoline, or one measuring in
# litres per 100 km, declares them under other codes.
FUEL_PRICE_CODE = ENV_VARS['FUEL_PRICE_FACTOR_CODE']
FUEL_EFFICIENCY_CODE = ENV_VARS['FUEL_EFFICIENCY_FACTOR_CODE']
# The vehicle comes back. A delivery route ends at the last client and returns
# empty, so the fuel is spent over both legs.
_RETURN_LEGS = 2


# The series a factor keeps. Both change over time and both have to survive
# the change: a report produced last month was computed with the reading and
# the status of last month, and without their history it cannot be reproduced
# or defended.
SERIES_VALUE = 'VALUE'
# Turning a factor off is a decision too, and it is dated for the same reason
# a reading is: a report of a month when the factor counted has to stay
# reproducible. Stored as 1 for ACTIVE and 0 for INACTIVE, so one series
# mechanism serves both.
SERIES_STATUS = 'STATUS'
_ACTIVE_FLAG = {FactorStatus.ACTIVE: 1.0, FactorStatus.INACTIVE: 0.0}


def _series_key(
    owner_email: str,
    code: str,
    series: str = SERIES_VALUE
) -> str:
    '''
        Partition of one series of one factor, so reading it is one query.

        Args:
            owner_email (str): Authenticated account.
            code (str): Factor identifier.
            series (str): Which series — the readings or the statuses.

        Returns:
            str: The composite partition value.
    '''
    return f'{owner_email}#{code}#{series}'


def to_factor_response(item: FactorItem) -> FactorResponseSchema:
    '''
        A stored factor as the API publishes it.

        Args:
            item (FactorItem): Item as DynamoDB returned it.

        Returns:
            FactorResponseSchema: The factor and its latest reading.
    '''
    return FactorResponseSchema(
        code = item['code'],
        name = item['name'],
        unit = item['unit'],
        source = item.get('source'),
        status = item.get('status', FactorStatus.ACTIVE.value),
        latest_date = item.get('latest_date'),
        latest_value = (
            float(item['latest_value']) if item.get('latest_value') is not None else None
        ),
        updated_at = item['updated_at']
    )


def declare_factor(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    definition: FactorDefinitionSchema
) -> FactorItem:
    '''
        Declares a factor, or corrects its definition.

        Redeclaring keeps the readings already loaded: what changes here is
        what the factor IS —its name, its unit, how much it is allowed to
        weigh— not what it was worth on any day.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.
            definition (FactorDefinitionSchema): The factor.

        Returns:
            FactorItem: The stored factor.
    '''
    now = get_current_time_gmt().isoformat()
    # When the status starts to apply. Today unless the client
    # is declaring something that was already true: loading a year of history
    # needs the factor to have counted during that year.
    effective = definition.effective_from.isoformat() if definition.effective_from else now
    stored = find_item_by_key(
        dynamodb_resource = dynamodb_resource,
        table_name = FACTORS_TABLE,
        key = {'owner_email': owner_email, 'code': definition.code}
    ) or {}
    item: FactorItem = {
        **stored,
        'owner_email': owner_email,
        **definition.model_dump(),
        'created_at': stored.get('created_at', now),
        'updated_at': now
    }
    # `effective_from` says WHEN a decision applies; it is not a property of
    # the factor, so it does not travel on the item.
    item.pop('effective_from', None)
    dynamodb_resource.Table(FACTORS_TABLE).put_item(Item = to_dynamo(item))

    # A report of a month when the factor
    # counted has to stay reproducible after it is turned off.
    was = stored.get('status')
    if was is None or was != definition.status.value:
        _record(dynamodb_resource,
                _series_key(owner_email, definition.code, SERIES_STATUS),
                _ACTIVE_FLAG[definition.status], effective)

    message = (f'Factor {definition.code} declared for {owner_email} '
               f'as {definition.status.value}.')
    logger.info(message)
    return item


def _record(
    dynamodb_resource: ServiceResource,
    partition: str,
    value: float,
    now: str
) -> None:
    '''
        Writes one dated figure of one series.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            partition (str): The series it belongs to, as `_series_key` builds it.
            value (float): The figure.
            now (str): When it was recorded; also when it takes effect.
    '''
    # The full moment and not the day: a decision taken twice in one morning
    # is two decisions, and the point of this series is that none is lost.
    # A reading loaded by the client keeps the plain day, which is all it
    # knows; both sort and compare the same because ISO text does.
    row: FactorValueItem = {
        'owner_code': partition,
        'factor_date': now,
        'value': value,
        'recorded_at': now
    }
    dynamodb_resource.Table(FACTOR_VALUES_TABLE).put_item(Item = to_dynamo(row))


def get_factor(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    code: str
) -> FactorItem:
    '''
        One factor of the account.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.
            code (str): Factor identifier.

        Returns:
            FactorItem: The stored factor.

        Raises:
            ResourceNotFoundError: FACTOR_NOT_FOUND, which is also the answer
                for a factor that belongs to somebody else.
    '''
    item = find_item_by_key(
        dynamodb_resource = dynamodb_resource,
        table_name = FACTORS_TABLE,
        key = {'owner_email': owner_email, 'code': code}
    )
    if not item:
        error_msg = f'Factor {code} not found for {owner_email}.'
        logger.warning(error_msg)
        raise ResourceNotFoundError(detail = FactorError.FACTOR_NOT_FOUND.value)
    return item


def list_factors(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    only_active: bool = False
) -> FactorListResponseSchema:
    '''
        The factors the account declared, with their latest reading.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.
            only_active (bool): Whether to leave out the ones turned off.

        Returns:
            FactorListResponseSchema: The factors.
    '''
    items = query_by_partition(
        dynamodb_resource = dynamodb_resource,
        table_name = FACTORS_TABLE,
        partition_key = 'owner_email',
        partition_value = owner_email
    )
    if only_active:
        items = [
            item for item in items
            if item.get('status', FactorStatus.ACTIVE.value) == FactorStatus.ACTIVE.value
        ]
    factors = [to_factor_response(item) for item in sorted(items, key = lambda f: f['code'])]
    return FactorListResponseSchema(factors = factors, total = len(factors))


def state_on(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    code: str,
    day: date_type
) -> FactorStateSchema:
    '''
        What a factor WAS on a day: its reading and whether it counted.

        Both move independently and a report has to be computed with those of
        ITS OWN period. A factor can hold one value in March, be turned off in
        June and hold another in September: the March figure keeps March's
        value and the September figure uses September's, and the months in
        between count nothing at all. Reading today's state instead would let
        a switch flipped in September rewrite every number produced before it.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.
            code (str): Factor identifier.
            day (date): The day being asked about.

        Returns:
            FactorStateSchema: The factor as it stood that day.
    '''
    factor = get_factor(dynamodb_resource, owner_email, code)
    return FactorStateSchema(
        code = code,
        unit = factor['unit'],
        active = _flag_on(dynamodb_resource, owner_email, code, day, SERIES_STATUS),
        value = _figure_on(dynamodb_resource, owner_email, code, day, SERIES_VALUE),
        as_of = day.isoformat()
    )


# pylint: disable=too-many-arguments, too-many-positional-arguments
def _figure_on(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    code: str,
    day: date_type,
    series: str
) -> float | None:
    '''
        The last figure of a series on or before a day, or None.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.
            code (str): Factor identifier.
            day (date): The day being asked about.
            series (str): Which series.

        Returns:
            float | None: The figure in force, or None when there is none.
    '''
    found = read_series(dynamodb_resource, owner_email, code, end = day, series = series)
    return found.values[-1].value if found.values else None


def _flag_on(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    code: str,
    day: date_type,
    series: str
) -> bool:
    '''
        Whether the flag of a series was on that day.

        No entry on or before the day means the factor did not exist yet, and
        something that did not exist did not count.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.
            code (str): Factor identifier.
            day (date): The day being asked about.
            series (str): Which series.

        Returns:
            bool: True when it was on.
    '''
    figure = _figure_on(dynamodb_resource, owner_email, code, day, series)
    return bool(figure)


def active_factors_on(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    day: date_type
) -> list[FactorStateSchema]:
    '''
        The factors a calculation for a given day is allowed to take into
        account, each with the value it had THAT day.

        The one door anything that computes goes through. Turning a factor off
        is enough to take it out of every result from then on, and it leaves
        every result produced before it exactly as it was.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.
            day (date): The day the calculation is about.

        Returns:
            list[FactorStateSchema]: The factors in force that day.
    '''
    declared = list_factors(dynamodb_resource, owner_email).factors
    states = [
        state_on(dynamodb_resource, owner_email, factor.code, day)
        for factor in declared
    ]
    return [state for state in states if state.active]


def load_values(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    code: str,
    values: list[FactorValueSchema]
) -> FactorItem:
    '''
        Loads readings of a factor, by hand or from an ERP.

        Idempotent by day: sending a day again corrects it instead of leaving
        two truths for it. The factor keeps its latest reading so a screen can
        show "fuel today" without walking the series.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.
            code (str): Factor identifier.
            values (list[FactorValueSchema]): The readings.

        Returns:
            FactorItem: The factor with its latest reading.
    '''
    factor = get_factor(dynamodb_resource, owner_email, code)
    now = get_current_time_gmt().isoformat()
    partition = _series_key(owner_email, code)

    table = dynamodb_resource.Table(FACTOR_VALUES_TABLE)
    with table.batch_writer() as batch:
        for reading in values:
            row: FactorValueItem = {
                'owner_code': partition,
                'factor_date': reading.factor_date.isoformat(),
                'value': reading.value,
                'recorded_at': now
            }
            batch.put_item(Item = to_dynamo(row))

    latest = max(values, key = lambda reading: reading.factor_date)
    if not factor.get('latest_date') or latest.factor_date.isoformat() >= factor['latest_date']:
        factor['latest_date'] = latest.factor_date.isoformat()
        factor['latest_value'] = latest.value
    factor['updated_at'] = now
    dynamodb_resource.Table(FACTORS_TABLE).put_item(Item = to_dynamo(factor))

    message = f'Factor {code} of {owner_email} received {len(values)} reading(s).'
    logger.info(message)
    return factor


# pylint: disable=too-many-arguments, too-many-positional-arguments
def read_series(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    code: str,
    start: date_type | None = None,
    end: date_type | None = None,
    series: str = SERIES_VALUE
) -> FactorSeriesResponseSchema:
    '''
        The readings of a factor over a window.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.
            code (str): Factor identifier.
            start (date | None): First day to include.
            end (date | None): Last day to include.
            series (str): Which series — the readings or the statuses.

        Returns:
            FactorSeriesResponseSchema: The series, oldest first.
    '''
    factor = get_factor(dynamodb_resource, owner_email, code)
    bounds = {}
    if start:
        bounds['from'] = start.isoformat()
    if end:
        # '~' sorts after every character an ISO stamp uses, so asking up to a
        # day includes everything decided DURING that day and not only at
        # midnight.
        bounds['to'] = f'{end.isoformat()}~'
    rows = query_by_partition(
        dynamodb_resource = dynamodb_resource,
        table_name = FACTOR_VALUES_TABLE,
        partition_key = 'owner_code',
        partition_value = _series_key(owner_email, code, series),
        sort_key = 'factor_date',
        sort_between = bounds or None
    )
    return FactorSeriesResponseSchema(
        code = code,
        unit = factor['unit'],
        values = [
            FactorValueSchema(factor_date = str(row['factor_date'])[:10],
                              value = float(row['value']))
            for row in sorted(rows, key = lambda row: row['factor_date'])
        ]
    )


def value_on(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    code: str,
    day: date_type,
    series: str = SERIES_VALUE
) -> float:
    '''
        What a factor was worth on a day, or on the last day before it.

        A factor is not read every day —fuel changes when it changes— so the
        reading in force is the latest one not after the day asked about,
        exactly as a published rate governs until the next one.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.
            code (str): Factor identifier.
            day (date): The day being asked about.
            series (str): Which series — the readings or the statuses.

        Returns:
            float: The value in force.

        Raises:
            ResourceNotFoundError: NO_VALUE_FOR_DATE when nothing was loaded
                on or before that day.
    '''
    found = read_series(dynamodb_resource, owner_email, code, end = day, series = series)
    if not found.values:
        error_msg = f'Factor {code} has no {series} on or before {day}.'
        logger.warning(error_msg)
        raise ResourceNotFoundError(detail = FactorError.NO_VALUE_FOR_DATE.value)
    return found.values[-1].value


def transport_cost(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    trip: tuple[float, float | None],
    day: date_type
) -> TransportCostSchema:
    '''
        What a local delivery over a distance cost on a day.

        Kilometres divided by what a litre gives, times what a litre cost:
        that is the whole chain, and it is answered whole rather than as a
        total, because a figure a manager cannot take apart is one they cannot
        argue with.

        The distance counted is the ROUND TRIP. A delivery route ends at the
        last client and the vehicle returns empty; charging only the outward
        leg would halve a cost the operation really pays, and it is the same
        reason official cost models price a loaded kilometre above an average
        one.

        Both factors are read AS OF the day asked about and both must be
        active then. A route run in March is costed with March's fuel: reading
        today's price would make a past route cheaper or dearer than it was
        every time the pump moves.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.
            trip (tuple[float, float | None]): Kilometres of the route ONE
                WAY, and the units carried when the caller knows them.
            day (date): The day the trip belongs to.

        Returns:
            TransportCostSchema: The chain and its total.

        Raises:
            ResourceNotFoundError: When either factor has no reading in force
                on that day, or was not active then. A cost invented from a
                missing price is worse than no cost.
    '''
    distance_km, units = trip
    price = _factor_in_force(dynamodb_resource, owner_email, FUEL_PRICE_CODE, day)
    efficiency = _factor_in_force(dynamodb_resource, owner_email, FUEL_EFFICIENCY_CODE, day)

    round_trip_km = distance_km * _RETURN_LEGS
    litres = round_trip_km / efficiency
    cost = litres * price
    message = (f'Transport of {distance_km:.1f} km on {day} ({round_trip_km:.1f} km '
               f'round trip): {litres:.1f} L at {price} = {cost:.2f}.')
    logger.info(message)

    return TransportCostSchema(
        distance_km = distance_km,
        round_trip_km = round_trip_km,
        kilometres_per_litre = efficiency,
        price_per_litre = price,
        litres = litres,
        cost = cost,
        units = units,
        cost_per_unit = (cost / units) if units else None,
        as_of = day.isoformat()
    )


def _factor_in_force(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    code: str,
    day: date_type
) -> float:
    '''
        The reading of a factor that was active on a day.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.
            code (str): Factor identifier.
            day (date): The day being asked about.

        Returns:
            float: The reading in force.

        Raises:
            ResourceNotFoundError: NO_VALUE_FOR_DATE when it had no reading
                that day or was not counting then.
    '''
    state = state_on(dynamodb_resource, owner_email, code, day)
    if not state.active or state.value is None:
        error_msg = f'Factor {code} was not in force on {day}.'
        logger.warning(error_msg)
        raise ResourceNotFoundError(detail = FactorError.NO_VALUE_FOR_DATE.value)
    return state.value
