'''
    Tests for the business values read from the service's own table (the
    SERVICE PARAMETERS block of `services/utils.py`), since 24-oct-2026.

    The table was seeded in moto from `docs/parametros.md` before any test
    (tests/conftest.py); here the reading itself is tested.
'''
from decimal import Decimal

import pytest

from services import utils
from services.report import DECIMAL_CODES, FINANCE_CODES, finance_parameters, report_settings
from services.utils import load_parameters


def test_the_report_reads_its_values_from_its_own_table():
    '''Numbers as float, lists as lists, text as text: what the report always read.'''
    values = finance_parameters(('COVERAGE_MONTHS', 'CASH_ACCOUNTS', 'SALES_GROUP'))
    assert values == {'COVERAGE_MONTHS': 3.0, 'SALES_GROUP': '4.1',
                      'CASH_ACCOUNTS': ['1.1.01', '1.1.02', '1.1.03', '1.1.04', '1.1.05']}


def test_every_code_the_report_reads_is_seeded():
    '''The report settles with no code missing, the decimals included.'''
    assert len(finance_parameters(FINANCE_CODES + DECIMAL_CODES)) == 16
    assert report_settings() is not None


def test_a_missing_value_stops_the_calculation():
    '''A code nobody seeded is not replaced by a number nobody chose.'''
    with pytest.raises(ValueError, match = 'NOT_SEEDED'):
        load_parameters({'NOT_SEEDED': int})


def test_a_whole_number_must_be_whole(monkeypatch: pytest.MonkeyPatch):
    '''2.5 months is refused where a module counts whole months.'''
    monkeypatch.setitem(utils._SERVICE_PARAMETERS, 'HALF', Decimal('2.5')) # pylint: disable=protected-access
    with pytest.raises(ValueError, match = 'whole number'):
        load_parameters({'HALF': int})


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
