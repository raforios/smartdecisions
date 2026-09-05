'''
    Controller-level tests for the ingest endpoints.

    The engine tests exercise parsing and validation; these check the layer
    above, where the DTOs are assembled into the HTTP response — the layer that
    broke in production when the engines started returning models.
'''
import asyncio
from datetime import date, timedelta
from unittest.mock import patch

import pandas as pd
import pytest

from fastapi import HTTPException

from schemas.ingest import IngestError, IngestResponse, TEMPLATE_COLUMNS
from controllers import ingest as controllers


def _template_file() -> bytes:
    '''
        Builds a CSV with the published template headers.

        Returns:
            bytes: File content as the browser would upload it.
    '''
    headers = [column.header for column in TEMPLATE_COLUMNS]
    start = date(2026, 1, 5)
    rows = []
    for index in range(30):
        values = dict.fromkeys(headers, '')
        values['Fecha'] = (start + timedelta(days = index)).isoformat()
        values['Nro Factura'] = f'F-{index // 2:04d}'
        values['Cliente'] = f'Tienda {index % 5}'
        values['Producto'] = f'Producto {index % 4}'
        values['Cantidad'] = 3
        values['Precio Unitario'] = 8.5
        rows.append(values)
    return pd.DataFrame(rows, columns = headers).to_csv(index = False).encode('utf-8')


@pytest.fixture(name = 'stored')
def _stored():
    '''
        Replaces S3 and DynamoDB with in-memory doubles.

        Returns:
            dict: The item the controller persisted, for assertions.
    '''
    persisted: dict = {}

    def _persist(dynamodb_resource, payload):  # pylint: disable=unused-argument
        persisted.update(payload)
        persisted.setdefault('dataset_id', 'test-dataset-id')
        persisted.setdefault('created_at', '2026-01-05T10:00:00Z')
        return persisted

    with patch.object(controllers, 'download_bytes', lambda _: _template_file()), \
         patch.object(controllers, 'upload_bytes', lambda **kwargs: kwargs['file_key']), \
         patch.object(controllers, 'persist_dataset', _persist):
        yield persisted


def test_ingest_from_s3_returns_a_full_response(stored):
    '''A template-shaped file ingests and comes back summarized.'''
    response = asyncio.run(controllers.ingest_excel_from_s3_controller(
        dynamodb_resource = None,
        file_key = 'ingest/raw/test.csv',
        file_name = 'ventas.csv',
        current_user = 'tester@bearsoft.com.bo',
        request = None
    ))

    assert isinstance(response, IngestResponse)
    assert response.status == 'validated'
    assert response.summary.total_rows == 30
    assert response.summary.valid_rows == 30
    assert response.summary.unique_points_of_sale == 5
    assert not response.issues
    assert stored['file_s3_key']


def _dataset(owner: str) -> dict:
    '''
        A stored dataset record as DynamoDB returns it.

        Args:
            owner (str): Email stamped as the owner.

        Returns:
            dict: The record, with the fields the status response reads.
    '''
    return {
        'dataset_id': 'ds-001',
        'id': 'ds-001',
        'status': 'READY',
        'owner_email': owner,
        'file_s3_key': 'ingest/ds-001.xlsx',
        'total_rows': 100,
        'valid_rows': 98,
        'error_rows': 2,
        'created_at': '2026-08-10T12:36:39-04:00',
    }


def test_a_dataset_of_another_client_is_not_readable():
    '''
        The owner is stamped on every dataset and must be checked on every read.

        Without this, an authenticated user of one client who knows — or guesses
        — an identifier reads another client's sales data. It is the difference
        between storing data and being multi-tenant, and no test covered it while
        the hole was open.
    '''
    with patch('services.ingest_utils.get_dataset_by_id',
               lambda **kwargs: _dataset('otra@empresa.com')):
        with pytest.raises(HTTPException) as failure:
            asyncio.run(controllers.get_dataset_status_controller(
                dynamodb_resource = None,
                dataset_id = 'ds-001',
                request = None,
                current_user = 'yo@miempresa.com'
            ))

    assert failure.value.status_code == 404
    assert IngestError.DATASET_NOT_FOUND.value in str(failure.value.detail)


def test_a_missing_dataset_answers_the_same_as_a_foreign_one():
    '''
        Both cases answer 404 with the same code on purpose.

        Telling them apart would let a caller confirm which identifiers exist,
        which is a map of the customer base.
    '''
    with patch('services.ingest_utils.get_dataset_by_id', lambda **kwargs: None):
        with pytest.raises(HTTPException) as failure:
            asyncio.run(controllers.get_dataset_status_controller(
                dynamodb_resource = None,
                dataset_id = 'no-existe',
                request = None,
                current_user = 'yo@miempresa.com'
            ))

    assert failure.value.status_code == 404
    assert IngestError.DATASET_NOT_FOUND.value in str(failure.value.detail)


def test_the_owner_reads_their_own_dataset():
    '''The guard must not get in the way of whoever actually owns the data.'''
    with patch('services.ingest_utils.get_dataset_by_id',
               lambda **kwargs: _dataset('yo@miempresa.com')):
        response = asyncio.run(controllers.get_dataset_status_controller(
            dynamodb_resource = None,
            dataset_id = 'ds-001',
            request = None,
            current_user = 'yo@miempresa.com'
        ))

    assert response.dataset_id == 'ds-001'
    assert response.owner_email == 'yo@miempresa.com'
    assert response.summary.total_rows == 100


class _ListTable: # pylint: disable=too-few-public-methods
    '''A DynamoDB table that applies the owner filter of a scan.'''

    def __init__(self, items):
        self._items = items

    def scan(self, **kwargs):
        '''Returns the rows whose owner matches the filter.'''
        expression = kwargs['FilterExpression'].get_expression()
        attribute, expected = expression['values']
        return {'Items': [item for item in self._items
                          if item.get(attribute.name) == expected]}


class _ListResource: # pylint: disable=too-few-public-methods
    '''Stands in for the DynamoDB resource.'''

    def __init__(self, items):
        self._items = items

    def Table(self, _name): # pylint: disable=invalid-name
        '''Mirrors the boto3 resource API.'''
        return _ListTable(self._items)


def _dataset_row(owner: str, dataset_id: str, created_at: str) -> dict:
    '''
        A stored dataset row.

        Args:
            owner (str): Owner email.
            dataset_id (str): Identifier.
            created_at (str): ISO timestamp.

        Returns:
            dict: The record as DynamoDB holds it.
    '''
    return {
        'dataset_id': dataset_id, 'id': dataset_id, 'status': 'validated',
        'owner_email': owner, 'total_rows': 100, 'valid_rows': 98,
        'error_rows': 2, 'unique_points_of_sale': 8, 'unique_products': 12,
        'created_at': created_at,
    }


def test_the_history_only_lists_your_own_uploads():
    '''
        The screen that shows "your last upload" must never show somebody
        else's. The owner is part of the query, so a foreign row cannot reach
        the response even if the caller asks for everything.
    '''
    resource = _ListResource([
        _dataset_row('yo@miempresa.com', 'ds-1', '2026-09-01T10:00:00-04:00'),
        _dataset_row('otra@empresa.com', 'ds-2', '2026-09-02T10:00:00-04:00'),
    ])

    response = asyncio.run(controllers.list_datasets_controller(
        dynamodb_resource = resource, request = None,
        current_user = 'yo@miempresa.com', limit = 20
    ))

    assert response.count == 1
    assert [row.dataset_id for row in response.datasets] == ['ds-1']


def test_the_history_comes_back_newest_first():
    '''
        The panel reads the first row as "your last upload", so the order is
        part of the contract and not a detail of how DynamoDB happened to scan.
    '''
    resource = _ListResource([
        _dataset_row('yo@miempresa.com', 'viejo', '2026-08-01T10:00:00-04:00'),
        _dataset_row('yo@miempresa.com', 'nuevo', '2026-09-03T21:30:00-04:00'),
        _dataset_row('yo@miempresa.com', 'medio', '2026-08-20T10:00:00-04:00'),
    ])

    response = asyncio.run(controllers.list_datasets_controller(
        dynamodb_resource = resource, request = None,
        current_user = 'yo@miempresa.com', limit = 20
    ))

    assert [row.dataset_id for row in response.datasets] == ['nuevo', 'medio', 'viejo']


def test_the_history_respects_the_limit():
    '''The panel asks for one row; it must not pay for forty.'''
    resource = _ListResource([
        _dataset_row('yo@miempresa.com', f'ds-{index}', f'2026-08-{index:02d}T10:00:00-04:00')
        for index in range(1, 11)
    ])

    response = asyncio.run(controllers.list_datasets_controller(
        dynamodb_resource = resource, request = None,
        current_user = 'yo@miempresa.com', limit = 1
    ))

    assert response.count == 1
    assert response.datasets[0].dataset_id == 'ds-10'
