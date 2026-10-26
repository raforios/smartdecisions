'''
    Tests for the business values read from the service's parameters table
    (the SERVICE PARAMETERS block of `services/utils.py`).
'''
import pytest

from services import utils


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
