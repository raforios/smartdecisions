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

from schemas.ingest import IngestResponse, TEMPLATE_COLUMNS
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
