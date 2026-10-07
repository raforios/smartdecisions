'''
    Tests for the API channel of the companion contracts.

    What they are really checking is that the ERP can push every day without
    the data going wrong: the same validator as the file judges the rows, a
    retry does not count a payment twice, and a stock push for today corrects
    today without touching last week.
'''
import asyncio
from typing import Any
from unittest.mock import patch

import pandas as pd
import pytest
from fastapi import HTTPException

from controllers import channels
from controllers import common
from controllers import stock as stock_controllers
from services.ingest_files import read_file
from schemas.channels import (
    CollectionRowSchema,
    SaleRowSchema,
    SalesPushSchema,
    CollectionsPushSchema,
    ObjectiveRowSchema,
    ObjectivesPushSchema,
    IngestFromS3CompanionRequest,
    LoadMode,
    StockPushSchema,
    StockRowSchema,
    VisitRowSchema,
    VisitsPushSchema
)

OWNER = 'tester@bearsoft.com.bo'
DATASET_ID = 'ds-channels'


def _sales() -> pd.DataFrame:
    '''
        The normalized sales frame a companion is married against.

        Returns:
            pd.DataFrame: Two invoices over two products and one client.
    '''
    return pd.DataFrame([
        {'order_id': 'F-0001', 'total_amount': 100.0, 'product_id': 'Producto 1',
         'product_name': 'Producto 1', 'pos_id': 'Tienda 1', 'pos_name': 'Tienda 1',
         'seller': 'Mario'},
        {'order_id': 'F-0002', 'total_amount': 200.0, 'product_id': 'Producto 2',
         'product_name': 'Producto 2', 'pos_id': 'Tienda 2', 'pos_name': 'Tienda 2',
         'seller': 'Mario'},
    ])


@pytest.fixture(name = 'world')
def world_fixture():
    '''
        An in-memory S3 and a dataset that remembers what was attached to it.

        Returns:
            dict: `dataset` and `objects`, for assertions.
    '''
    objects: dict[str, bytes] = {}
    dataset: dict[str, Any] = {
        'dataset_id': DATASET_ID, 'owner_email': OWNER, 'status': 'validated',
        'created_at': '2026-02-15T10:00:00Z',
        'file_s3_key': 'ingest/normalized/sales.csv'
    }

    def _upload(**kwargs) -> str:
        objects[kwargs['file_key']] = kwargs['data']
        return kwargs['file_key']

    def _read_frame(
        file_key: str,
        *args, # pylint: disable=unused-argument
        **kwargs # pylint: disable=unused-argument
    ) -> pd.DataFrame:
        return read_file(objects[str(file_key)], str(file_key))

    def _attach(
        dynamodb_resource, # pylint: disable=unused-argument
        dataset_id, # pylint: disable=unused-argument
        payload
    ):
        dataset.update(payload)
        return dataset

    with patch.object(channels, 'get_owned_dataset', lambda **kwargs: dataset), \
         patch.object(channels, 'load_sales_frame', lambda *args: _sales()), \
         patch.object(channels, 'read_stored_frame', _read_frame), \
         patch.object(common, 'read_stored_frame', _read_frame), \
         patch.object(common, 'upload_bytes', _upload), \
         patch.object(channels, 'attach_to_dataset', _attach), \
         patch.object(channels, 'sync_master', lambda **kwargs: kwargs['frame']), \
         patch.object(channels, 'delete_stored_file',
                      lambda file_key, auth_token: objects.pop(str(file_key), None)), \
         patch.object(common, 'attach_to_dataset', _attach):
        yield {'dataset': dataset, 'objects': objects}


def _stored_rows(world: dict) -> pd.DataFrame:
    '''
        What ended up stored for the companion of the last load.

        Args:
            world (dict): The fixture's state.

        Returns:
            pd.DataFrame: The stored rows.
    '''
    key = [name for name in world['dataset'] if name.endswith('_s3_key')
           and name != 'file_s3_key'][-1]
    return read_file(world['objects'][world['dataset'][key]], 'stored.csv')


def _payments(rows: list[dict[str, Any]]) -> CollectionsPushSchema:
    '''
        Builds a payments push.

        Args:
            rows (list[dict[str, Any]]): Row dictionaries.

        Returns:
            CollectionsPushSchema: The push payload.
    '''
    return CollectionsPushSchema(rows = [CollectionRowSchema(**row) for row in rows])


def _push_payments(push: CollectionsPushSchema) -> Any:
    '''
        Runs the payments push controller.

        Args:
            push (CollectionsPushSchema): The push payload.

        Returns:
            CollectionsResponse: What the endpoint answers.
    '''
    return asyncio.run(channels.push_collections_controller(
        dynamodb_resource = None,
        dataset_id = DATASET_ID,
        push = push,
        current_user = OWNER,
        auth_token = 'Bearer t',
        request = None
    ))


def test_the_erp_pushes_payments_without_uploading_a_workbook(world):
    '''The whole point of the channel: rows in, summary out.'''
    response = _push_payments(_payments([
        {'order_id': 'F-0001', 'payment_date': '2026-02-10', 'paid_amount': 40.0},
        {'order_id': 'F-0002', 'payment_date': '2026-02-11', 'paid_amount': 50.0},
    ]))

    assert response.summary.valid_rows == 2
    assert response.summary.matched_invoices == 2
    assert response.summary.collected_amount == 90.0
    assert len(_stored_rows(world)) == 2


def test_a_retry_does_not_count_a_payment_twice(world):
    '''
        The reason APPEND has a key at all.

        An ERP that times out and retries must not double the payment: the
        receivable would go quietly wrong and nobody would find it from the
        outside.
    '''
    rows = [{'order_id': 'F-0001', 'payment_date': '2026-02-10', 'paid_amount': 40.0}]
    _push_payments(_payments(rows))
    response = _push_payments(_payments(rows))

    assert len(_stored_rows(world)) == 1
    assert response.summary.collected_amount == 40.0


def test_a_second_push_adds_to_the_first(world):
    '''Pushing every day accumulates; that is what daily integration means.'''
    _push_payments(_payments([
        {'order_id': 'F-0001', 'payment_date': '2026-02-10', 'paid_amount': 40.0},
    ]))
    response = _push_payments(_payments([
        {'order_id': 'F-0002', 'payment_date': '2026-02-11', 'paid_amount': 50.0},
    ]))

    assert len(_stored_rows(world)) == 2
    # The summary describes everything stored, not just what was pushed.
    assert response.summary.collected_amount == 90.0
    assert response.summary.valid_rows == 2


def test_replace_makes_the_push_the_whole_load(world):
    '''REPLACE is the file behaviour, available to the API when it is wanted.'''
    _push_payments(_payments([
        {'order_id': 'F-0001', 'payment_date': '2026-02-10', 'paid_amount': 40.0},
    ]))
    _push_payments(CollectionsPushSchema(
        mode = LoadMode.REPLACE,
        rows = [CollectionRowSchema(order_id = 'F-0002',
                                    payment_date = '2026-02-11', paid_amount = 50.0)]
    ))

    stored = _stored_rows(world)
    assert len(stored) == 1
    assert stored.iloc[0]['order_id'] == 'F-0002'


def test_the_api_is_judged_by_the_same_contract_as_the_file(world): # pylint: disable=unused-argument
    '''
        A payment against an invoice the dataset does not know is reported
        with the same code the uploaded file produces, never dropped.
    '''
    response = _push_payments(_payments([
        {'order_id': 'F-9999', 'payment_date': '2026-02-10', 'paid_amount': 10.0},
    ]))

    assert [issue.rule_code.value for issue in response.issues] == ['UNKNOWN_INVOICE']


def test_a_stock_push_replaces_the_day_and_leaves_the_others(world):
    '''
        The snapshot key is product AND day.

        Correcting today must not erase last week, and re-sending today must
        not leave two figures for the same SKU on the same day.
    '''
    def _push(rows):
        return asyncio.run(channels.push_stock_controller(
            dynamodb_resource = None,
            dataset_id = DATASET_ID,
            push = StockPushSchema(rows = [StockRowSchema(**row) for row in rows]),
            current_user = OWNER,
            auth_token = 'Bearer t',
            request = None
        ))

    _push([{'snapshot_date': '2026-02-14', 'product_name': 'Producto 1', 'on_hand': 10}])
    _push([{'snapshot_date': '2026-02-15', 'product_name': 'Producto 1', 'on_hand': 7}])
    _push([{'snapshot_date': '2026-02-15', 'product_name': 'Producto 1', 'on_hand': 5}])

    stored = _stored_rows(world).sort_values('snapshot_date')
    assert len(stored) == 2
    assert list(stored['on_hand']) == [10, 5]


def test_the_stock_of_one_day_is_read_back_with_what_is_free(world):
    '''
        The route module opens its day from the file INGEST stored, so the
        day it asks for has to come back alone and with `on_hand - committed`
        as what a seller can still sell. A day never loaded is a code, not an
        empty day that would let the route sell from nothing.
    '''
    asyncio.run(channels.push_stock_controller(
        dynamodb_resource = None,
        dataset_id = DATASET_ID,
        push = StockPushSchema(rows = [
            StockRowSchema(snapshot_date = '2026-02-14', product_name = 'Producto 1',
                           on_hand = 10),
            StockRowSchema(snapshot_date = '2026-02-15', product_name = 'Producto 1',
                           on_hand = 7, committed = 2),
            StockRowSchema(snapshot_date = '2026-02-15', product_name = 'Producto 2',
                           on_hand = 4),
        ]),
        current_user = OWNER,
        auth_token = 'Bearer t',
        request = None
    ))

    def _read(day: str) -> Any:
        return asyncio.run(stock_controllers.get_stock_day_controller(
            dynamodb_resource = None,
            dataset_id = DATASET_ID,
            day = day,
            current_user = OWNER,
            auth_token = 'Bearer t',
            request = None
        ))

    with patch.object(stock_controllers, 'get_owned_dataset', lambda **kwargs: world['dataset']):
        response = _read('2026-02-15')
        with pytest.raises(HTTPException) as missing:
            _read('2026-02-16')

    assert [(item.product_id, item.on_hand, item.available) for item in response.items] == [
        ('Producto 1', 7.0, 5.0), ('Producto 2', 4.0, 4.0)
    ]
    assert missing.value.detail == 'NO_STOCK_FOR_DAY'


def test_a_visits_push_feeds_the_client_master(world): # pylint: disable=unused-argument
    '''
        The visits channel reaches clients the sales file never billed, so it
        is the one that has to register them.
    '''
    synced: list = []

    # Patched where it now LIVES: `store_companion` feeds the master for
    # every door, instead of each controller keeping its own copy of the call.
    with patch.object(common, 'sync_master',
                      lambda **kwargs: synced.append(kwargs['source'].value) or kwargs['frame']):
        response = asyncio.run(channels.push_visits_controller(
            dynamodb_resource = None,
            dataset_id = DATASET_ID,
            push = VisitsPushSchema(rows = [VisitRowSchema(
                visit_date = '2026-02-15', seller = 'Mario', pos_name = 'Tienda 1',
                visit_time = '09:30'
            )]),
            current_user = OWNER,
            auth_token = 'Bearer t',
            request = None
        ))

    assert synced == ['API']
    assert response.summary.valid_rows == 1


def test_a_file_staged_in_s3_takes_the_same_path(world):
    '''
        The second door of the file channel: FILES puts the object in S3 and
        the service reads it by key, so the binary never crosses the 10 MB of
        API Gateway.
    '''
    world['objects']['ingest/raw/cobros.csv'] = (
        b'Nro Factura,Fecha Cobro,Monto Cobrado\n'
        b'F-0001,2026-02-10,40\n'
        b'F-0002,2026-02-11,50\n'
    )

    response = asyncio.run(channels.ingest_collections_from_s3_controller(
        dynamodb_resource = None,
        dataset_id = DATASET_ID,
        payload = IngestFromS3CompanionRequest(
            file_key = 'ingest/raw/cobros.csv', file_name = 'cobros.csv'
        ),
        current_user = OWNER,
        auth_token = 'Bearer t',
        request = None
    ))

    assert response.summary.valid_rows == 2
    assert response.summary.collected_amount == 90.0


def test_the_s3_door_feeds_the_client_master_like_the_others(world):
    """
        The gap this closes: each door used to feed the master with its own
        copy of the call, and this one simply forgot. The same visits file
        loaded by upload and by key produced two different masters — the
        prospect it named existed or not depending on the endpoint used.
    """
    world['objects']['ingest/raw/visitas.csv'] = (
        b'Fecha,Vendedor,Cliente,Hora\n'
        b'2026-02-15,Mario,Prospecto Nuevo,09:30\n'
    )
    synced: list = []

    with patch.object(common, 'sync_master',
                      lambda **kwargs: synced.append(kwargs['source'].value) or kwargs['frame']):
        response = asyncio.run(channels.ingest_visits_from_s3_controller(
            dynamodb_resource = None,
            dataset_id = DATASET_ID,
            payload = IngestFromS3CompanionRequest(
                file_key = 'ingest/raw/visitas.csv', file_name = 'visitas.csv'
            ),
            current_user = OWNER,
            auth_token = 'Bearer t',
            request = None
        ))

    assert synced == ['FILE']
    assert response.summary.valid_rows == 1


def test_a_companion_that_does_not_name_clients_never_touches_the_master(world):
    """
        Payments name invoices and the stock names products. Feeding the
        master from them would invent a client out of an invoice number.
    """
    world['objects']['ingest/raw/cobros.csv'] = (
        b'Nro Factura,Fecha Cobro,Monto Cobrado\nF-0001,2026-02-10,40\n'
    )
    synced: list = []

    with patch.object(common, 'sync_master',
                      lambda **kwargs: synced.append(kwargs['source']) or kwargs['frame']):
        asyncio.run(channels.ingest_collections_from_s3_controller(
            dynamodb_resource = None,
            dataset_id = DATASET_ID,
            payload = IngestFromS3CompanionRequest(
                file_key = 'ingest/raw/cobros.csv', file_name = 'cobros.csv'
            ),
            current_user = OWNER,
            auth_token = 'Bearer t',
            request = None
        ))

    assert not synced


def _sale(**overrides: Any) -> SaleRowSchema:
    '''
        Builds one sales line with the minimum the contract asks for.

        Args:
            **overrides (Any): Fields to change.

        Returns:
            SaleRowSchema: The line.
    '''
    row = {'date': '2026-02-15', 'order_id': 'F-0003', 'pos_name': 'Tienda 1',
           'product_name': 'Producto 1', 'quantity': 2.0, 'unit_price': 10.0}
    row.update(overrides)
    return SaleRowSchema(**row)


def _push_sales(
    rows: list[SaleRowSchema],
    **kwargs: Any
) -> Any:
    '''
        Runs the sales push controller.

        Args:
            rows (list[SaleRowSchema]): Lines to push.
            **kwargs (Any): Extra push fields, such as `mode`.

        Returns:
            IngestResponse: What the endpoint answers.
    '''
    return asyncio.run(channels.push_sales_controller(
        dynamodb_resource = None,
        dataset_id = DATASET_ID,
        push = SalesPushSchema(rows = rows, **kwargs),
        current_user = OWNER,
        auth_token = 'Bearer t',
        request = None
    ))


def test_the_erp_pushes_sales_lines_into_its_dataset(world):
    '''
        The API door of the main contract: an ERP that is the system of record
        never exports a workbook.
    '''
    world['objects']['ingest/normalized/sales.csv'] = b'date,order_id\n'

    response = _push_sales([_sale(), _sale(order_id = 'F-0004')])

    assert response.summary.valid_rows == 2
    assert response.status == 'validated'
    assert world['dataset']['file_s3_key'].startswith('ingest/normalized/')


def test_pushing_the_same_line_twice_does_not_count_the_invoice_twice(world):
    '''
        A sales line is its invoice and its product.

        An ERP that retries, or that re-sends the day with one line corrected,
        must not leave the invoice counted twice — the whole revenue figure
        would be wrong and nothing would say so.
    '''
    world['objects']['ingest/normalized/sales.csv'] = b'date,order_id\n'
    _push_sales([_sale()])
    response = _push_sales([_sale(quantity = 5.0)])

    assert response.summary.valid_rows == 1
    stored = read_file(
        world['objects'][world['dataset']['file_s3_key']], 'stored.csv'
    )
    assert len(stored) == 1
    # Last write wins, so the correction is what stays.
    assert stored.iloc[0]['quantity'] == 5.0


def test_a_pushed_line_that_breaks_the_contract_is_set_aside(world): # pylint: disable=unused-argument
    '''
        Partial acceptance is the rule on this door too: the bad line is
        reported with its code and the rest still load.
    '''
    world['objects']['ingest/normalized/sales.csv'] = b'date,order_id\n'

    response = _push_sales([_sale(), _sale(order_id = 'F-0005', pos_name = 'Tienda 9')])

    assert response.summary.valid_rows == 2


def test_the_erp_pushes_objectives_and_they_are_stored(world): # pylint: disable=unused-argument
    '''
        The API door of the objectives contract. An objective is the only
        figure no transaction implies, so the door an ERP uses to send it has
        to be as tested as the file one.
    '''
    with patch.object(common, 'sync_master', lambda **kwargs: kwargs['frame']):
        response = asyncio.run(channels.push_objectives_controller(
            dynamodb_resource = None,
            dataset_id = DATASET_ID,
            push = ObjectivesPushSchema(rows = [
                ObjectiveRowSchema(pos_name = 'Tienda 1', period = '2026-02',
                                   target_amount = 15000.0)
            ]),
            current_user = OWNER,
            auth_token = 'Bearer t',
            request = None
        ))

    assert response.summary.valid_rows == 1
    assert response.summary.target_amount == 15000.0
    assert response.summary.period_start == '2026-02'


def test_pushing_the_same_month_twice_corrects_it_instead_of_doubling_it(world): # pylint: disable=unused-argument
    '''
        The rule that makes the contract usable: objectives get revised
        mid-quarter, and a second truth for one month makes every percentage
        below it meaningless.
    '''
    with patch.object(common, 'sync_master', lambda **kwargs: kwargs['frame']):
        for target in (15000.0, 18000.0):
            response = asyncio.run(channels.push_objectives_controller(
                dynamodb_resource = None,
                dataset_id = DATASET_ID,
                push = ObjectivesPushSchema(rows = [
                    ObjectiveRowSchema(pos_name = 'Tienda 1', period = '2026-02',
                                       target_amount = target)
                ]),
                current_user = OWNER,
                auth_token = 'Bearer t',
                request = None
            ))

    assert response.summary.valid_rows == 1
    assert response.summary.target_amount == 18000.0


def test_the_objectives_and_stock_s3_doors_load_their_files(world):
    '''
        The remaining two staged-in-S3 doors. Same path as their siblings,
        and untested until now for the same reason: they look trivial.
    '''
    world['objects']['ingest/raw/objetivos.csv'] = (
        b'Cliente,Periodo,Objetivo\nTienda 1,2026-02,15000\n'
    )
    world['objects']['ingest/raw/stock.csv'] = (
        b'Fecha,Producto,Existencia\n2026-02-10,Producto 1,40\n'
    )

    with patch.object(common, 'sync_master', lambda **kwargs: kwargs['frame']):
        objectives = asyncio.run(channels.ingest_objectives_from_s3_controller(
            dynamodb_resource = None, dataset_id = DATASET_ID,
            payload = IngestFromS3CompanionRequest(
                file_key = 'ingest/raw/objetivos.csv', file_name = 'objetivos.csv'
            ),
            current_user = OWNER, auth_token = 'Bearer t', request = None
        ))
    stock = asyncio.run(channels.ingest_stock_from_s3_controller(
        dynamodb_resource = None, dataset_id = DATASET_ID,
        payload = IngestFromS3CompanionRequest(
            file_key = 'ingest/raw/stock.csv', file_name = 'stock.csv'
        ),
        current_user = OWNER, auth_token = 'Bearer t', request = None
    ))

    assert objectives.summary.valid_rows == 1
    assert stock.summary.valid_rows == 1
