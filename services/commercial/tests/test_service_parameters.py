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
    values = load_parameters({'AMOUNT_DECIMALS': int, 'MARGIN_THIN_THRESHOLD': float,
                              'AFFINITY_ITEM_LEVEL': str})
    assert values == {'AMOUNT_DECIMALS': 2, 'MARGIN_THIN_THRESHOLD': 0.02,
                      'AFFINITY_ITEM_LEVEL': 'category'}
    assert isinstance(values['AMOUNT_DECIMALS'], int)


def test_the_two_delinquency_values_are_apart():
    '''
        The credit policy's «moroso desde» and the «moroso» band of the risk
        were one name in the .env: the second line won, so both read 30 and
        the «en observación» band never showed.
    '''
    values = load_parameters({'RECEIVABLES_DELINQUENT_DAYS': int,
                              'RECEIVABLES_DELINQUENT_RISK_DAYS': int})
    assert values == {'RECEIVABLES_DELINQUENT_DAYS': 1, 'RECEIVABLES_DELINQUENT_RISK_DAYS': 30}


def test_a_missing_value_stops_the_service():
    '''A code nobody seeded is not replaced by a number nobody chose.'''
    with pytest.raises(ValueError, match = 'NOT_SEEDED'):
        load_parameters({'NOT_SEEDED': int})


def test_a_whole_number_must_be_whole(monkeypatch: pytest.MonkeyPatch):
    '''2.5 days is refused where the module counts whole days.'''
    monkeypatch.setitem(utils._SERVICE_PARAMETERS, 'HALF', Decimal('2.5')) # pylint: disable=protected-access
    with pytest.raises(ValueError, match = 'whole number'):
        load_parameters({'HALF': int})


def test_a_list_comes_back_as_strings(monkeypatch: pytest.MonkeyPatch):
    '''A LIST of the document arrives as a list, each item a string.'''
    monkeypatch.setitem(utils._SERVICE_PARAMETERS, 'ACCOUNTS', ['1.1.01', '1.1.02']) # pylint: disable=protected-access
    assert load_parameters({'ACCOUNTS': list}) == {'ACCOUNTS': ['1.1.01', '1.1.02']}


def test_the_table_is_read_page_by_page(monkeypatch: pytest.MonkeyPatch):
    '''Every page of the scan is read, and the items come back by code.'''
    pages = [{'Items': [{'code': 'A', 'value': 1}], 'LastEvaluatedKey': {'code': 'A'}},
             {'Items': [{'code': 'B', 'value': 'x'}]}]

    class _Table:  # pylint: disable=too-few-public-methods
        '''A table that answers two pages.'''

        def scan(
            self,
            **kwargs: dict
        ) -> dict:
            '''The second page when asked to continue, the first otherwise.'''
            return pages[1] if kwargs else pages[0]

    class _Resource:  # pylint: disable=too-few-public-methods
        '''The DynamoDB resource, with that table.'''

        def Table(  # pylint: disable=invalid-name
            self,
            name: str  # pylint: disable=unused-argument
        ) -> _Table:
            '''The table.'''
            return _Table()

    monkeypatch.setattr(utils.boto3, 'resource', lambda service: _Resource())
    assert utils._read_service_parameters() == {'A': 1, 'B': 'x'}  # pylint: disable=protected-access
