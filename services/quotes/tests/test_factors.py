'''
    Tests for the fluctuating factors.

    What they defend is the reason the module exists: a figure that moves on
    its own does NOT live in the `.env`. It is loaded by hand or by API, it
    carries the day it was true, and it only counts while it is ACTIVE —
    which is how fuel enters the product without disturbing a single report.
'''
from datetime import date

import pytest

from schemas.factors import (
    FactorDefinitionSchema,
    FactorError,
    FactorStatus,
    FactorValueSchema
)
from services import factors
from services.exceptions import ResourceNotFoundError

OWNER = 'yo@miempresa.com'
OTHER = 'otra@empresa.com'

DIESEL = FactorDefinitionSchema(
    code = 'DIESEL', name = 'Precio del diésel', unit = 'Bs/litro',
    source = 'Factura de la estación'
)


def _load(
    factor_store,
    readings: list
) -> dict:
    '''
        Loads readings of the diesel factor.

        Args:
            factor_store: The resource.
            readings (list): Tuples of date and value.

        Returns:
            dict: The factor after the load.
    '''
    return factors.load_values(factor_store, OWNER, 'DIESEL', [
        FactorValueSchema(factor_date = when, value = value) for when, value in readings
    ])


def test_loading_the_same_day_twice_corrects_it(factor_store):
    '''
        Idempotent by day: a correction is not a second truth for that day.
    '''
    factors.declare_factor(factor_store, OWNER, DIESEL)
    _load(factor_store, [('2026-09-20', 3.72)])
    factor = _load(factor_store, [('2026-09-20', 3.85)])

    series = factors.read_series(factor_store, OWNER, 'DIESEL')
    assert len(series.values) == 1
    assert series.values[0].value == 3.85
    assert factor['latest_value'] == 3.85


def test_the_value_in_force_is_the_last_one_not_after_that_day(factor_store):
    '''
        A factor is not read every day — fuel changes when it changes.

        So the reading in force on a Wednesday is Monday's, exactly as a
        published rate governs until the next one replaces it.
    '''
    factors.declare_factor(factor_store, OWNER, DIESEL)
    _load(factor_store, [('2026-09-14', 3.60), ('2026-09-21', 3.85)])

    assert factors.value_on(factor_store, OWNER, 'DIESEL', date(2026, 9, 23)) == 3.85
    assert factors.value_on(factor_store, OWNER, 'DIESEL', date(2026, 9, 18)) == 3.60

    with pytest.raises(ResourceNotFoundError) as missing:
        factors.value_on(factor_store, OWNER, 'DIESEL', date(2026, 9, 1))
    assert missing.value.detail == FactorError.NO_VALUE_FOR_DATE.value


def test_redeclaring_keeps_the_readings(factor_store):
    '''
        Correcting what a factor IS must not erase what it was worth.
    '''
    factors.declare_factor(factor_store, OWNER, DIESEL)
    _load(factor_store, [('2026-09-21', 3.85)])

    factors.declare_factor(
        factor_store, OWNER, DIESEL.model_copy(update = {'name': 'Diésel subvencionado'})
    )

    series = factors.read_series(factor_store, OWNER, 'DIESEL')
    assert [value.value for value in series.values] == [3.85]


def test_a_factor_of_another_account_does_not_exist(factor_store):
    '''Isolation: a foreign factor answers exactly like a missing one.'''
    factors.declare_factor(factor_store, OTHER, DIESEL)

    with pytest.raises(ResourceNotFoundError) as missing:
        factors.get_factor(factor_store, OWNER, 'DIESEL')
    assert missing.value.detail == FactorError.FACTOR_NOT_FOUND.value


def test_the_series_comes_back_in_order_and_bounded(factor_store):
    '''A window asks for a window.'''
    factors.declare_factor(factor_store, OWNER, DIESEL)
    _load(factor_store, [('2026-09-21', 3.85), ('2026-09-07', 3.50), ('2026-09-14', 3.60)])

    series = factors.read_series(factor_store, OWNER, 'DIESEL',
                                 start = date(2026, 9, 10), end = date(2026, 9, 21))
    assert [value.value for value in series.values] == [3.60, 3.85]
    assert series.unit == 'Bs/litro'


def test_a_factor_is_born_active(factor_store):
    '''
        Nobody has to remember to turn a new factor on.
    '''
    stored = factors.declare_factor(factor_store, OWNER, DIESEL)
    assert stored['status'] == FactorStatus.ACTIVE.value


def test_only_the_active_ones_are_taken_into_account(factor_store):
    '''
        Turning a factor off is how it stops affecting results without being
        deleted — and `active_factors_on` is the one door anything that
        computes goes through, so nobody has to remember to check the flag.
    '''
    factors.declare_factor(factor_store, OWNER, DIESEL)
    factors.declare_factor(factor_store, OWNER, FactorDefinitionSchema(
        code = 'ARANCEL', name = 'Arancel de importación', unit = '%'
    ))
    factors.declare_factor(
        factor_store, OWNER, DIESEL.model_copy(update = {'status': FactorStatus.INACTIVE})
    )

    today = date.today()
    assert [factor.code for factor in
            factors.active_factors_on(factor_store, OWNER, today)] == ['ARANCEL']
    # It is not gone: the screen still shows it, to be turned back on.
    assert factors.list_factors(factor_store, OWNER).total == 2


def test_turning_a_factor_off_keeps_everything_it_had(factor_store):
    '''
        An inactive factor stops counting; it does not stop having happened.
        A report of a month when it counted still has to be reproducible.
    '''
    factors.declare_factor(factor_store, OWNER, DIESEL)
    _load(factor_store, [('2026-09-21', 3.85)])

    factors.declare_factor(
        factor_store, OWNER, DIESEL.model_copy(update = {'status': FactorStatus.INACTIVE})
    )

    assert [value.value for value in
            factors.read_series(factor_store, OWNER, 'DIESEL').values] == [3.85]
    # And when it was turned off is itself dated, for the same reason.
    switches = factors.read_series(factor_store, OWNER, 'DIESEL', series = factors.SERIES_STATUS)
    assert [value.value for value in switches.values][-1] == 0.0


def test_the_value_of_a_period_survives_being_turned_off_and_on_again(factor_store):
    """
        The whole point of dating the three series.

        A factor can hold one value in March, be turned off in June and hold
        another in September. A report of March has to be computed with
        March's value; the months it was off count nothing;
        and September uses September's. Reading today's state instead would
        let a switch flipped in September rewrite every figure produced before
        it.
    """
    # Declared as having counted since January: the client is loading a year
    # of history, not deciding today.
    factors.declare_factor(factor_store, OWNER, DIESEL.model_copy(update = {
        'effective_from': date(2026, 1, 1)
    }))
    _load(factor_store, [('2026-03-10', 3.40), ('2026-09-10', 4.10)])

    march = factors.state_on(factor_store, OWNER, 'DIESEL', date(2026, 3, 20))
    assert march.value == 3.40 and march.active is True

    september = factors.state_on(factor_store, OWNER, 'DIESEL', date(2026, 9, 20))
    assert september.value == 4.10
    # Turning it off today must not touch what March was.
    factors.declare_factor(
        factor_store, OWNER, DIESEL.model_copy(update = {'status': FactorStatus.INACTIVE})
    )
    assert factors.state_on(factor_store, OWNER, 'DIESEL', date(2026, 3, 20)).value == 3.40
    assert factors.state_on(factor_store, OWNER, 'DIESEL', date(2026, 3, 20)).active is True
    assert factors.state_on(factor_store, OWNER, 'DIESEL', date.today()).active is False


def test_a_factor_counts_nothing_before_it_existed(factor_store):
    """
        Something that did not exist did not count, so a report of a period
        before the factor was declared is not quietly changed by declaring it.
    """
    factors.declare_factor(factor_store, OWNER, DIESEL)

    assert factors.state_on(factor_store, OWNER, 'DIESEL', date(2025, 1, 1)).active is False
    assert factors.active_factors_on(factor_store, OWNER, date(2025, 1, 1)) == []


RENDIMIENTO = FactorDefinitionSchema(
    code = 'RENDIMIENTO', name = 'Rendimiento promedio de la flota',
    unit = 'km/litro', source = 'Promedio estimado por la operación'
)


def _fleet(factor_store) -> None:
    '''
        Declares the two factors a delivery is costed with, effective from
        January, and loads one reading of each.

        Args:
            factor_store: The resource.
    '''
    for definition, reading in ((DIESEL, 20.0), (RENDIMIENTO, 10.0)):
        factors.declare_factor(factor_store, OWNER, definition.model_copy(
            update = {'effective_from': date(2026, 1, 1)}
        ))
        factors.load_values(factor_store, OWNER, definition.code, [
            FactorValueSchema(factor_date = date(2026, 1, 1), value = reading)
        ])


def test_the_cost_counts_the_empty_return(factor_store):
    '''
        The vehicle comes back.

        A route of 100 km at 10 km/l and 20 Bs/l is not 200 Bs: the van ends
        at the last client and drives home empty, so the fuel is spent over
        200 km. Charging only the outward leg would halve a cost the operation
        really pays.
    '''
    _fleet(factor_store)

    costed = factors.transport_cost(factor_store, OWNER, (100.0, None), date(2026, 3, 15))

    assert costed.distance_km == 100.0
    assert costed.round_trip_km == 200.0
    assert costed.litres == 20.0
    assert costed.cost == 400.0


def test_the_cost_per_unit_is_what_reaches_the_margin(factor_store):
    '''
        Divided by what was carried, the trip stops being a total and becomes
        a cost the margin of each unit can absorb.
    '''
    _fleet(factor_store)

    costed = factors.transport_cost(factor_store, OWNER, (100.0, 1000.0), date(2026, 3, 15))

    assert costed.cost_per_unit == 0.4


def test_a_route_is_costed_with_the_fuel_of_its_own_day(factor_store):
    '''
        The pump moving in September must not make a route run in March
        cheaper or dearer than it was.
    '''
    _fleet(factor_store)
    factors.load_values(factor_store, OWNER, 'DIESEL', [
        FactorValueSchema(factor_date = date(2026, 9, 1), value = 25.0)
    ])

    march = factors.transport_cost(factor_store, OWNER, (100.0, None), date(2026, 3, 15))
    september = factors.transport_cost(factor_store, OWNER, (100.0, None), date(2026, 9, 15))

    assert march.cost == 400.0
    assert september.cost == 500.0


def test_a_missing_factor_refuses_instead_of_inventing_a_cost(factor_store):
    '''
        A cost invented from a price nobody loaded is worse than no cost: it
        travels into the margin and nothing says it was a guess.
    '''
    _fleet(factor_store)
    factors.declare_factor(
        factor_store, OWNER, RENDIMIENTO.model_copy(update = {'status': FactorStatus.INACTIVE})
    )

    with pytest.raises(ResourceNotFoundError) as refused:
        factors.transport_cost(factor_store, OWNER, (100.0, None), date.today())
    assert refused.value.detail == FactorError.NO_VALUE_FOR_DATE.value
