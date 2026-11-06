'''
    Cancellations and returns: one record each, a reverted one kept and not
    counted, the report by month and by reason, and the sale left net in the
    latest dataset.
'''
import asyncio
from typing import Any

import pandas as pd

from controllers import reversals as controllers
from controllers import sales_load
from schemas.channels import SaleRowSchema
from schemas.reversals import (
    ReversalKind,
    ReversalLineSchema,
    ReversalSchema,
    ReversalState
)
from services import currency, reversals

OWNER = 'empresa@demo.bo'


def _reversal(**overrides: Any) -> ReversalSchema:
    '''A return of one unit of A-1, unless told otherwise.'''
    values = {'reversal_id': 'NC-1', 'kind': ReversalKind.RETURN, 'order_id': 'A-1',
              'date': '2026-11-06', 'lines': [ReversalLineSchema(
                  product_id = 'P1', product_name = 'Leche', quantity = 1, amount = 10.0)]}
    return ReversalSchema(**{**values, **overrides})


def _table(monkeypatch) -> dict:
    '''An in-memory commercial_reversals, keyed like the real one.'''
    rows: dict = {}
    monkeypatch.setattr(reversals, 'find_item_by_key',
                        lambda _db, _table_name, key: rows.get(key['reversal_id']))
    monkeypatch.setattr(reversals, 'put_items', lambda _db, _table_name, items: [
        rows.__setitem__(item['reversal_id'], item) for item in items])
    monkeypatch.setattr(reversals, 'query_by_partition',
                        lambda *_args: list(rows.values()))
    return rows


def test_reverting_rewrites_the_same_record_and_keeps_its_first_day(monkeypatch):
    '''One record per return; its state changes, the day it was recorded does not.'''
    rows = _table(monkeypatch)
    first = reversals.store_reversal(None, OWNER, _reversal())
    second = reversals.store_reversal(None, OWNER, _reversal(state = ReversalState.REVERTED,
                                                             date = '2026-11-20'))
    assert list(rows) == ['RETURN#NC-1']
    assert second['state'] == 'REVERTED' and second['created_at'] == first['created_at']
    assert second['date'] == '2026-11-06'
    assert (second['quantity'], second['amount']) == (1, 10.0)


def test_the_report_counts_what_stands_by_month_and_by_reason(monkeypatch):
    '''A reverted record is listed and not counted; a missing reason still groups.'''
    _table(monkeypatch)
    # Fixed rates in place of QUOTES: 7 Bs the dollar, 10 the USDT.
    monkeypatch.setattr(reversals, 'with_month_close_factors', lambda frame, *_args: frame.assign(
        **{currency.USD_FACTOR: 1 / 7, currency.USDT_FACTOR: 1 / 10,
           currency.TOTAL_USD_FACTOR: 1 / 7, currency.TOTAL_USDT_FACTOR: 1 / 10}))
    reversals.store_reversal(None, OWNER, _reversal())
    reversals.store_reversal(None, OWNER, _reversal(
        reversal_id = 'S-9', kind = ReversalKind.CANCELLATION, order_id = 'A-9',
        date = '2026-10-20', reason_code = 1, reason = 'Error en datos',
        lines = [ReversalLineSchema(product_name = 'Pan', quantity = 4, amount = 20.0)]))
    reversals.store_reversal(None, OWNER, _reversal(reversal_id = 'NC-2', order_id = 'A-2',
                                                    state = ReversalState.REVERTED))
    report = reversals.build_report(
        reversals.list_reversals(None, OWNER, {'date_from': '2026-10-01'}), 'Bearer t')
    assert (report.count, report.quantity, report.amount.bob) == (2, 5.0, 30.0)
    assert (report.amount.usd, report.amount.usdt) == (4.29, 3.0)
    assert [(row.month, row.kind, row.count, row.amount.bob) for row in report.months] == [
        ('2026-10', ReversalKind.CANCELLATION, 1, 20.0), ('2026-11', ReversalKind.RETURN, 1, 10.0)]
    assert [(row.reason_code, row.reason, row.amount.bob) for row in report.reasons] == [
        (1, 'Error en datos', 20.0), (None, None, 10.0)]
    assert [record.reversal_id for record in report.reversals] == ['NC-2', 'NC-1', 'S-9']


def test_the_window_leaves_out_what_falls_outside(monkeypatch):
    '''The window bounds the day it was undone.'''
    _table(monkeypatch)
    reversals.store_reversal(None, OWNER, _reversal())
    assert not reversals.list_reversals(None, OWNER, {'date_to': '2026-11-05'})


def _sale(
    order_id: str,
    product_id: str,
    quantity: float
) -> dict:
    '''One stored sales line.'''
    return {'date': '2026-11-01', 'order_id': order_id, 'pos_id': 'C-1', 'product_id': product_id,
            'product_name': product_id, 'quantity': quantity, 'unit_price': 10.0}


def test_the_sale_is_left_as_it_stands(monkeypatch):
    '''A return leaves what the buyer kept; a cancellation leaves nothing of the sale.'''
    stored = {'frame': pd.DataFrame([_sale('A-1', 'P1', 4), _sale('A-1', 'P2', 1),
                                     _sale('B-1', 'P1', 2)])}
    dataset = {'dataset_id': 'DS-1', 'owner_email': OWNER, 'file_s3_key': 'old.csv'}
    monkeypatch.setattr(sales_load, 'read_stored_frame', lambda *_args: stored['frame'])
    monkeypatch.setattr(sales_load, 'store_frame',
                        lambda frame, *_args: stored.update(frame = frame) or 'new.csv')
    monkeypatch.setattr(sales_load, 'attach_to_dataset', lambda **kwargs: kwargs['payload'])
    monkeypatch.setattr(sales_load, 'retire_replaced_file', lambda *_args: None)
    monkeypatch.setattr(sales_load, 'with_known_masters', lambda _db, _owner, result, _src: result)

    kept = SaleRowSchema(date = '2026-11-01', order_id = 'A-1', product_id = 'P1',
                         product_name = 'P1', quantity = 3, unit_price = 10.0)
    sales_load.replace_order_lines(None, dataset, 'A-1', [kept], 'Bearer t')
    lines = stored['frame'][['order_id', 'product_id', 'quantity']].values.tolist()
    assert sorted(lines) == [['A-1', 'P1', 3.0], ['B-1', 'P1', 2.0]]

    sales_load.replace_order_lines(None, dataset, 'A-1', [], 'Bearer t')
    assert stored['frame']['order_id'].tolist() == ['B-1']


def test_the_controller_records_and_sets_the_latest_dataset_right(monkeypatch):
    '''With a dataset the sale is set right there; without one only the record stays.'''
    replaced: list = []
    monkeypatch.setattr(controllers, 'store_reversal', lambda _db, owner, reversal: {
        'owner_email': owner, 'reversal_id': f'{reversal.kind.value}#{reversal.reversal_id}',
        'kind': reversal.kind.value, 'state': reversal.state.value, 'order_id': 'A-1',
        'date': '2026-11-06', 'lines': [line.model_dump() for line in reversal.lines],
        'quantity': 1, 'amount': 10.0, 'updated_at': '2026-11-06T10:00:00'})
    monkeypatch.setattr(controllers, 'get_owned_dataset',
                        lambda **kwargs: {'dataset_id': kwargs['dataset_id']})
    monkeypatch.setattr(controllers, 'replace_order_lines',
                        lambda _db, dataset, order, rows, _token: replaced.append(
                            (dataset['dataset_id'], order, rows)))

    def _record():
        return asyncio.run(controllers.record_reversal_controller(
            dynamodb_resource = None, reversal = _reversal(), current_user = OWNER,
            auth_token = 'Bearer t', request = None))

    monkeypatch.setattr(controllers, 'list_datasets_for_owner',
                        lambda *_args, **_kwargs: [{'dataset_id': 'DS-1'}])
    answer = _record()
    assert (answer.reversal_id, answer.dataset_id) == ('NC-1', 'DS-1')
    assert replaced == [('DS-1', 'A-1', [])]

    monkeypatch.setattr(controllers, 'list_datasets_for_owner', lambda *_args, **_kwargs: [])
    assert _record().dataset_id is None and len(replaced) == 1


def test_the_report_controller_reads_the_window(monkeypatch):
    '''The window and the token reach the report.'''
    seen: list = []
    monkeypatch.setattr(controllers, 'list_reversals',
                        lambda _db, owner, params: seen.append((owner, params)) or [])
    report = asyncio.run(controllers.reversals_report_controller(
        dynamodb_resource = None, params = {'date_from': '2026-11-01', 'auth_token': 'Bearer t'},
        current_user = OWNER, request = None))
    assert report.count == 0 and seen == [(OWNER, {'date_from': '2026-11-01',
                                                    'auth_token': 'Bearer t'})]
