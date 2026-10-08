'''
    Controller-level tests for the ingest endpoints.

    The engine tests exercise parsing and validation; these check the layer
    above, where the DTOs are assembled into the HTTP response — the layer that
    broke in production when the engines started returning models.
'''
import asyncio
from datetime import date, timedelta
from importlib import import_module
from unittest.mock import patch

import pandas as pd
import pytest

from fastapi import HTTPException

from schemas.ingest import (
    IngestError,
    SALES_COLUMNS,
    TemplateInfo,
    IngestResponse,
    ObjectivesResponse,
    TEMPLATE_COLUMNS
)
from services import ingest_utils
from services.ingest_files import read_file
from controllers import common
from controllers import ingest as controllers
from controllers import objectives as objectives_controller


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

    # FILES hands back rows, not bytes: the double answers at that level, and
    # through the same reader, so a blank cell arrives as a null exactly as it
    # would from the real service.
    with patch.object(controllers, 'read_stored_frame',
                      lambda *args, **kwargs: read_file(_template_file(), 'ventas.csv')), \
         patch.object(common, 'upload_bytes', lambda **kwargs: kwargs['file_key']), \
         patch.object(controllers, 'find_dataset_by_fingerprint', lambda **kwargs: None), \
         patch.object(common, 'sync_master', lambda **kwargs: kwargs['frame']), \
         patch.object(controllers, 'delete_stored_file', lambda *args: None), \
         patch.object(controllers, 'persist_dataset', _persist), \
         patch.object(common, 'persist_dataset', _persist):
        yield persisted


def test_ingest_from_s3_returns_a_full_response(stored):
    '''A template-shaped file ingests and comes back summarized.'''
    response = asyncio.run(controllers.ingest_excel_from_s3_controller(
        dynamodb_resource = None,
        file_key = 'ingest/raw/test.csv',
        file_name = 'ventas.csv',
        current_user = 'tester@bearsoft.com.bo',
        auth_token = 'Bearer t',
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


def test_the_multipart_upload_also_feeds_the_client_master():
    '''
        The other upload door has to do everything the S3 one does.

        It had no test at all, and that is how an assignment to a frozen
        dataclass —`result.accepted = ...`— got written on this path alone: the
        suite stayed green and the endpoint would have raised
        FrozenInstanceError on the first real upload.
    '''
    synced: list = []

    def _sync(**kwargs):
        synced.append(kwargs['owner_email'])
        return kwargs['frame']

    def _persist(
        dynamodb_resource, # pylint: disable=unused-argument
        payload
    ):
        return {**payload, 'dataset_id': 'ds-multipart',
                'created_at': '2026-02-15T10:00:00Z'}

    with patch.object(common, 'upload_bytes', lambda **kwargs: kwargs['file_key']), \
         patch.object(controllers, 'find_dataset_by_fingerprint', lambda **kwargs: None), \
         patch.object(common, 'sync_master', _sync), \
         patch.object(controllers, 'persist_dataset', _persist):
        response = asyncio.run(controllers.ingest_excel_controller(
            dynamodb_resource = None,
            file_bytes = _template_file(),
            filename = 'ventas.csv',
            current_user = 'tester@bearsoft.com.bo',
            auth_token = 'Bearer t',
            request = None
        ))

    assert isinstance(response, IngestResponse)
    assert response.status == 'validated'
    assert response.summary.valid_rows == 30
    # The owner of the load is the caller, never anything read off the file.
    assert synced == ['tester@bearsoft.com.bo']


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

    with patch.object(controllers, 'read_stored_frame',
                      lambda *args, **kwargs: read_file(_template_file(), 'ventas.csv')), \
         patch.object(controllers, 'delete_stored_file', lambda *args: None), \
         patch.object(controllers, 'find_dataset_by_fingerprint',
                      lambda **kwargs: already), \
         patch.object(controllers, 'persist_dataset',
                      lambda **kwargs: written.append(kwargs) or already):
        response = asyncio.run(controllers.ingest_excel_from_s3_controller(
            dynamodb_resource = None,
            file_key = 'ingest/raw/otra-vez.csv',
            file_name = 'ventas.csv',
            current_user = 'yo@miempresa.com',
            auth_token = 'Bearer t',
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


def test_the_objectives_upload_returns_a_full_response():
    '''
        The objectives endpoint, end to end through its controller.

        It exists for the reason the multipart test above exists: a route or
        controller can name something the schema no longer has, and only
        running the layer catches it. It also pins the two behaviours that
        make the contract worth having — a month is kept as a month, and the
        client an objective names is created even though nobody billed them.
    '''
    created: list = []

    def _sync(**kwargs):
        created.append(kwargs['frame'])
        return kwargs['frame']

    rows = pd.DataFrame([
        {'Cliente': 'Tienda 1', 'Periodo': '2026-01', 'Objetivo': 15000.0},
        {'Cliente': 'Prospecto Nuevo', 'Periodo': '2026-01', 'Objetivo': 5000.0}
    ])

    with patch.object(objectives_controller, 'get_owned_dataset',
                      lambda **kwargs: {'dataset_id': 'test-dataset-id',
                                        'owner_email': 'tester@bearsoft.com.bo'}), \
         patch.object(objectives_controller, 'load_sales_frame',
                      lambda *args, **kwargs: _template_rows().rename(
                          columns = {'Cliente': 'pos_id'})), \
         patch.object(common, 'sync_master', _sync), \
         patch.object(common, 'upload_bytes', lambda **kwargs: kwargs['file_key']), \
         patch.object(common, 'attach_to_dataset', lambda **kwargs: None):
        response = asyncio.run(objectives_controller.ingest_objectives_controller(
            dynamodb_resource = None,
            dataset_id = 'test-dataset-id',
            file_bytes = rows.to_csv(index = False).encode('utf-8'),
            filename = 'objetivos.csv',
            current_user = 'tester@bearsoft.com.bo',
            auth_token = 'Bearer t',
            request = None
        ))

    assert isinstance(response, ObjectivesResponse)
    assert response.status == 'validated'
    assert response.summary.valid_rows == 2
    assert response.summary.target_amount == 20000.0
    assert response.summary.periods_count == 1
    # The prospect is reported, kept, and handed to the master.
    assert response.summary.unmatched_rows == 1
    assert 'Prospecto Nuevo' in set(created[0]['pos_id'])
    assert response.objectives_s3_key


def test_the_template_info_controller_returns_its_model():
    '''
        The contract the client downloads, described from the contract itself.
        If a column is added and this drifts, the client fills in a template
        the validator then rejects.
    '''
    response = asyncio.run(controllers.get_template_info_controller(
        base_path = None, request = None, current_user = 'tester@bearsoft.com.bo'
    ))

    assert isinstance(response, TemplateInfo)
    assert response.download_url.endswith('/ventas')
    assert set(response.required_columns) <= {
        column.canonical for column in SALES_COLUMNS
    }


def test_the_template_download_controller_serves_the_stored_file():
    '''
        The one documented direct-S3 read in the product: a static file FILES
        cannot hand back as a file. It has to reach the caller as bytes.
    '''
    with patch.object(controllers, 'download_template_bytes',
                      lambda key: f'contenido de {key}'.encode()):
        content = asyncio.run(controllers.download_template_controller(
            contract = 'ventas', request = None,
            current_user = 'tester@bearsoft.com.bo'
        ))

    assert b'ventas' in content


def test_the_rejected_download_controller_serves_the_set_aside_rows():
    '''
        The rows the client has to fix. They are downloaded as a CSV, which
        is the only artefact of the product that carries Spanish reasons.
    '''
    with patch.object(controllers, 'get_owned_dataset',
                      lambda **kwargs: {'dataset_id': 'd', 'owner_email': 'o',
                                        'rejected_s3_key': 'ingest/rejected/d.csv'}), \
         patch.object(controllers, 'read_stored_frame',
                      lambda *args, **kwargs: pd.DataFrame([{'Fecha': '2026-01-05',
                                                             'rule_codes': 'x=Y'}])):
        content = asyncio.run(controllers.download_rejected_controller(
            dynamodb_resource = None, dataset_id = 'd', request = None,
            current_user = 'tester@bearsoft.com.bo', auth_token = 'Bearer t'
        ))

    assert content.startswith(b'Fecha')


def test_a_dataset_with_nothing_rejected_answers_a_code_and_not_a_sentence():
    '''
        It used to answer a Spanish sentence, which the backend has no
        business writing: the wording belongs to whoever draws the screen,
        and a phrase cannot be translated or branched on.
    '''
    with patch.object(controllers, 'get_owned_dataset',
                      lambda **kwargs: {'dataset_id': 'd', 'owner_email': 'o'}):
        with pytest.raises(HTTPException) as refused:
            asyncio.run(controllers.download_rejected_controller(
                dynamodb_resource = None, dataset_id = 'd', request = None,
                current_user = 'tester@bearsoft.com.bo', auth_token = 'Bearer t'
            ))

    assert refused.value.detail == IngestError.NO_REJECTED_ROWS.value


@pytest.mark.parametrize('controller_name,filename,rows,expected', [
    ('ingest_collections_controller', 'cobros.csv',
     'Nro Factura,Fecha Cobro,Monto Cobrado\nF-0000,2026-01-20,25.5\n', 1),
    ('ingest_stock_controller', 'stock.csv',
     'Fecha,Producto,Existencia\n2026-01-20,Producto 0,40\n', 1),
    ('ingest_visits_controller', 'visitas.csv',
     'Fecha,Vendedor,Cliente,Hora\n2026-01-20,Ana,Tienda 0,09:30\n', 1),
])
def test_every_companion_upload_controller_returns_its_model(
    controller_name,
    filename,
    rows,
    expected
):
    '''
        The three file doors, each through its own controller.

        They had no test at all. They are seven-line adapters, which is
        exactly why nobody wrote one — and exactly how an adapter that names
        a field its schema no longer has reaches production.
    '''
    module = import_module(f'controllers.{controller_name.split("_")[1]}')
    controller = getattr(module, controller_name)

    with patch.object(module, 'get_owned_dataset',
                      lambda **kwargs: {'dataset_id': 'test-dataset-id',
                                        'owner_email': 'tester@bearsoft.com.bo'}), \
         patch.object(module, 'load_sales_frame',
                      lambda *args, **kwargs: _normalized_sales()), \
         patch.object(common, 'sync_master', lambda **kwargs: kwargs['frame']), \
         patch.object(common, 'upload_bytes', lambda **kwargs: kwargs['file_key']), \
         patch.object(common, 'attach_to_dataset', lambda **kwargs: None):
        response = asyncio.run(controller(
            dynamodb_resource = None,
            dataset_id = 'test-dataset-id',
            file_bytes = rows.encode('utf-8'),
            filename = filename,
            current_user = 'tester@bearsoft.com.bo',
            auth_token = 'Bearer t',
            request = None
        ))

    assert response.dataset_id == 'test-dataset-id'
    assert response.summary.valid_rows == expected
    assert response.status == 'validated'


def _normalized_sales() -> pd.DataFrame:
    '''
        The sales frame a companion is married against, canonical already.

        Returns:
            pd.DataFrame: Rows with the invoice, client and product a
                companion file can refer to.
    '''
    frame = pd.DataFrame(_template_rows()).rename(columns = {
        'Fecha': 'date', 'Nro Factura': 'order_id', 'Cliente': 'pos_name',
        'Producto': 'product_name', 'Cantidad': 'quantity',
        'Precio Unitario': 'unit_price', 'Vendedor': 'seller'
    })
    frame = pd.DataFrame(frame)
    frame['date'] = pd.to_datetime(frame['date'])
    frame['pos_id'] = frame['pos_name']
    frame['product_id'] = frame['product_name']
    frame['total_amount'] = frame['quantity'] * frame['unit_price']
    frame['seller'] = 'Ana'
    return frame
