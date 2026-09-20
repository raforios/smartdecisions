'''
    Controller-level tests for the ingest endpoints.

    The engine tests exercise parsing and validation; these check the layer
    above, where the DTOs are assembled into the HTTP response — the layer that
    broke in production when the engines started returning models.
'''
import asyncio
from datetime import date, timedelta
from io import BytesIO
from unittest.mock import patch

import pandas as pd
import pytest

from fastapi import HTTPException

from schemas.ingest import (
    COLLECTIONS_SHEET,
    IngestError,
    IngestResponse,
    SALES_SHEET,
    STOCK_SHEET,
    TEMPLATE_COLUMNS,
    VISITS_SHEET
)
from services import ingest_utils
from controllers import common
from controllers import ingest as controllers


def _template_rows() -> pd.DataFrame:
    '''
        Builds sales rows with the published template headers.

        Returns:
            pd.DataFrame: Thirty lines over fifteen invoices.
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
    return pd.DataFrame(rows, columns = headers)


def _template_file() -> bytes:
    '''
        Builds a CSV with the published template headers.

        Returns:
            bytes: File content as the browser would upload it.
    '''
    return _template_rows().to_csv(index = False).encode('utf-8')


def _full_workbook() -> bytes:
    '''
        Builds the four-sheet workbook the client downloads and returns filled.

        Returns:
            bytes: An .xlsx with sales, payments, a stock snapshot and visits.
    '''
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine = 'openpyxl') as writer:
        _template_rows().to_excel(writer, sheet_name = SALES_SHEET, index = False)
        pd.DataFrame([
            {'Nro Factura': 'F-0000', 'Fecha Cobro': '2026-02-10', 'Monto Cobrado': 20.0},
            {'Nro Factura': 'F-0001', 'Fecha Cobro': '2026-02-12', 'Monto Cobrado': 51.0}
        ]).to_excel(writer, sheet_name = COLLECTIONS_SHEET, index = False)
        pd.DataFrame([
            {'Fecha': '2026-02-15', 'Producto': 'Producto 0', 'Existencia': 40},
            {'Fecha': '2026-02-15', 'Producto': 'Producto 1', 'Existencia': 12}
        ]).to_excel(writer, sheet_name = STOCK_SHEET, index = False)
        pd.DataFrame([
            {'Fecha': '2026-01-05', 'Hora': '09:10', 'Vendedor': 'Mario',
             'Cliente': 'Tienda 0', 'Resultado': 'VENTA'},
            {'Fecha': '2026-01-05', 'Hora': '10:40', 'Vendedor': 'Mario',
             'Cliente': 'Tienda 1', 'Resultado': 'SIN_VENTA'},
            {'Fecha': '2026-01-05', 'Hora': '11:20', 'Vendedor': 'Mario',
             'Cliente': 'Tienda 2'}
        ]).to_excel(writer, sheet_name = VISITS_SHEET, index = False)
    return buffer.getvalue()


@pytest.fixture(name = 'stored')
def _stored():
    '''
        Replaces S3 and DynamoDB with in-memory doubles.

        Returns:
            dict: The item the controller persisted, for assertions.
    '''
    persisted: dict = {}

    def _persist(
        dynamodb_resource, # pylint: disable=unused-argument
        payload
    ):
        persisted.update(payload)
        persisted.setdefault('dataset_id', 'test-dataset-id')
        persisted.setdefault('created_at', '2026-01-05T10:00:00Z')
        return persisted

    with patch.object(controllers, 'download_bytes', lambda _: _template_file()), \
         patch.object(controllers, 'upload_bytes', lambda **kwargs: kwargs['file_key']), \
         patch.object(controllers, 'find_dataset_by_fingerprint', lambda **kwargs: None), \
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
    # The content fingerprint is what makes a re-upload recognisable later.
    assert stored['file_fingerprint']
    assert response.already_stored is False
    # A plain sales file carries no companion sheets and says so by absence.
    assert response.collections is None
    assert response.stock is None
    assert response.visits is None


def test_the_s3_upload_loads_the_payments_and_stock_sheets_too():
    '''
        The portal uploads through the pre-signed S3 path, so that path has to
        read the workbook's companion sheets: one load feeds every module. It
        used to skip them, and receivables showed every invoice as open.
    '''
    attached: dict = {}

    def _persist(
        dynamodb_resource, # pylint: disable=unused-argument
        payload
    ):
        return {**payload, 'dataset_id': 'ds-full', 'created_at': '2026-02-15T10:00:00Z'}

    def _attach(
        dynamodb_resource, # pylint: disable=unused-argument
        dataset_id, # pylint: disable=unused-argument
        payload
    ):
        attached.update(payload)

    # The companion loads are stored through controllers/common.py, so the
    # S3 and DynamoDB doubles go there as well as on the sales controller.
    with patch.object(controllers, 'download_bytes', lambda _: _full_workbook()), \
         patch.object(controllers, 'upload_bytes', lambda **kwargs: kwargs['file_key']), \
         patch.object(common, 'upload_bytes', lambda **kwargs: kwargs['file_key']), \
         patch.object(controllers, 'find_dataset_by_fingerprint', lambda **kwargs: None), \
         patch.object(controllers, 'persist_dataset', _persist), \
         patch.object(common, 'attach_to_dataset', _attach):
        response = asyncio.run(controllers.ingest_excel_from_s3_controller(
            dynamodb_resource = None,
            file_key = 'ingest/raw/plantilla.xlsx',
            file_name = 'plantilla.xlsx',
            current_user = 'tester@bearsoft.com.bo',
            request = None
        ))

    assert response.status == 'validated'
    assert response.summary.valid_rows == 30
    assert response.collections is not None
    assert response.collections.valid_rows == 2
    assert response.stock is not None
    assert response.stock.valid_rows == 2
    assert response.stock.products == 2
    assert response.visits is not None
    assert response.visits.valid_rows == 3
    assert response.visits.with_outcome == 2
    # The sales fixture has no seller column, so nobody is unknown there.
    assert response.visits.unknown_sellers == 0
    # Every load hangs off the dataset, where the analysis services read it.
    assert attached['collections_s3_key'].startswith('ingest/collections/')
    assert attached['stock_s3_key'].startswith('ingest/stock/')
    assert attached['visits_s3_key'].startswith('ingest/visits/')


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

    def __init__(
        self,
        items
    ):
        self._items = items

    def scan(
        self,
        **kwargs
    ):
        '''Returns the rows whose owner matches the filter.'''
        expression = kwargs['FilterExpression'].get_expression()
        attribute, expected = expression['values']
        return {'Items': [item for item in self._items
                          if item.get(attribute.name) == expected]}


class _ListResource: # pylint: disable=too-few-public-methods
    '''Stands in for the DynamoDB resource.'''

    def __init__(
        self,
        items
    ):
        self._items = items

    def Table( # pylint: disable=invalid-name
        self,
        _name
    ):
        '''Mirrors the boto3 resource API.'''
        return _ListTable(self._items)


def _dataset_row(
    owner: str,
    dataset_id: str,
    created_at: str
) -> dict:
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


def test_uploading_the_same_file_twice_does_not_duplicate_it():
    '''
        The same content from the same owner is the same dataset.

        Before this, every upload minted a new identifier, a new copy in S3 and
        a new history row — forty-six accumulated from a single file — and
        nothing told the user they already had it. Now the existing dataset
        comes back, flagged, and nothing is written.
    '''
    already = _dataset('yo@miempresa.com')
    written = []

    with patch.object(controllers, 'download_bytes', lambda _: b'las mismas ventas'), \
         patch.object(controllers, 'find_dataset_by_fingerprint',
                      lambda **kwargs: already), \
         patch.object(controllers, 'persist_dataset',
                      lambda **kwargs: written.append(kwargs) or already):
        response = asyncio.run(controllers.ingest_excel_from_s3_controller(
            dynamodb_resource = None,
            file_key = 'ingest/raw/otra-vez.csv',
            file_name = 'ventas.csv',
            current_user = 'yo@miempresa.com',
            request = None
        ))

    assert response.already_stored is True
    assert response.dataset_id == already['dataset_id']
    # Nothing was written: no second row, no second copy in S3.
    assert not written


def test_the_fingerprint_is_the_content_and_not_the_name():
    '''
        The same figures renamed are the same dataset; a corrected file is a
        different one even under the same name.
    '''
    same = ingest_utils.content_fingerprint(b'fila1,fila2')
    assert same == ingest_utils.content_fingerprint(b'fila1,fila2')
    assert same != ingest_utils.content_fingerprint(b'fila1,fila2,fila3')
