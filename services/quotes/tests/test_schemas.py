'''
    Tests for the schemas and their rules. They import only the schemas, so
    they run in the GitHub CI too, with no .env.
'''
import pytest
from pydantic import ValidationError

from schemas.factors import (
    FactorDefinitionSchema,
    FactorStatus,
    FactorValuesLoadSchema,
    TransportCostSchema
)
from schemas.quotes import ExchangeRateHistory, QuotesError, SyncResult

FACTOR = {'code': 'DIESEL', 'name': 'Diésel', 'unit': 'Bs/litro'}
TRIP = {'distance_km': 10.0, 'round_trip_km': 20.0, 'kilometres_per_litre': 10.0,
        'price_per_litre': 3.74, 'litres': 2.0, 'cost': 7.48, 'as_of': '2026-10-26'}
SYNC = {'currency': 'USD', 'requested_days': 7, 'stored': 5, 'already_present': 2,
        'without_publication': 0}


def test_a_factor_is_born_active():
    '''Declared with no status, a factor counts from the start.'''
    assert FactorDefinitionSchema(**FACTOR).status is FactorStatus.ACTIVE


@pytest.mark.parametrize('field', ['code', 'name', 'unit'])
def test_a_factor_needs_a_code_a_name_and_a_unit(field: str):
    '''An empty code, name or unit is refused.'''
    with pytest.raises(ValidationError):
        FactorDefinitionSchema(**{**FACTOR, field: ''})


def test_a_load_of_values_is_never_empty():
    '''A load with no readings is refused before it reaches the service.'''
    with pytest.raises(ValidationError):
        FactorValuesLoadSchema(values = [])


@pytest.mark.parametrize('field', ['distance_km', 'price_per_litre', 'litres', 'cost'])
def test_a_transport_cost_is_never_negative(field: str):
    '''Distances, prices, litres and cost are zero or more.'''
    assert TransportCostSchema(**TRIP).cost == 7.48
    with pytest.raises(ValidationError):
        TransportCostSchema(**{**TRIP, field: -1})


def test_counts_are_never_negative():
    '''A history or a sync never reports a negative count.'''
    assert ExchangeRateHistory(currency = 'USD', days = 0).days == 0
    with pytest.raises(ValidationError):
        ExchangeRateHistory(currency = 'USD', days = -1)
    assert SyncResult(**SYNC).stored == 5
    with pytest.raises(ValidationError):
        SyncResult(**{**SYNC, 'stored': -1})


def test_the_error_codes_are_their_own_names():
    '''A code travels as its own name: the portal translates it by that key.'''
    assert all(code.value == code.name for code in QuotesError)
