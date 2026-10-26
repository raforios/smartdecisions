'''
    Tests for the business values read from the service's parameters table
    (the SERVICE PARAMETERS block of `services/utils.py`).

    The table was seeded in moto from `docs/parametros.md` before the modules
    were imported (tests/conftest.py); here the reading itself is tested.
'''
from decimal import Decimal

import pytest

from services import utils
from services.utils import load_parameters


def test_the_values_come_typed_from_the_table():
    '''A NUMBER stored as Decimal comes back as the type the module reads.'''
    values = load_parameters({'RATE_DECIMALS': int, 'FIXED_REGIME_RATE': float,
                              'PARALLEL_CURRENCY': str})
    assert values == {'RATE_DECIMALS': 4, 'FIXED_REGIME_RATE': 6.86,
                      'PARALLEL_CURRENCY': 'USDT'}


def test_a_missing_value_stops_the_service():
    '''A code nobody seeded is not replaced by a number nobody chose.'''
    with pytest.raises(ValueError, match = 'NOT_SEEDED'):
        load_parameters({'NOT_SEEDED': int})


def test_a_whole_number_must_be_whole(monkeypatch: pytest.MonkeyPatch):
    '''2.5 days is refused where the module counts whole days.'''
    monkeypatch.setitem(utils._SERVICE_PARAMETERS, 'HALF', Decimal('2.5')) # pylint: disable=protected-access
    with pytest.raises(ValueError, match = 'whole number'):
        load_parameters({'HALF': int})
