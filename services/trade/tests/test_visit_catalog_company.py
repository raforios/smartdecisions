'''
    services/trade/tests/test_visit_catalog_company.py

    Binaria 2026-08-13: every visit flow (impulse inventory start/end,
    replenishment inventory, supplier reception) must resolve its SKUs against
    the CLIENT company that owns the products, never against the executor
    company running the visit.

    The regression these pin down: the validation loop already used the client
    company, but the bulk write resolved each SKU a second time against the
    executor, so the request failed with "SKU not found for company <executor>"
    after passing validation.
'''
import asyncio
from types import SimpleNamespace

import pytest

from services import trade_utils

EXECUTOR_COMPANY = 1
CLIENT_COMPANY = 42


_ABSENT = object()


def _payload(client_company_id = _ABSENT):
    '''
        Minimal visit payload: an executor company, a POS and one SKU line.

        Passing _ABSENT leaves the client_company_id attribute off entirely
        (a legacy payload); passing None ships the field empty.
    '''
    payload = SimpleNamespace(
        company_id = EXECUTOR_COMPANY,
        pos_id = 7,
        items = [SimpleNamespace(product_sku = 'SKU-001')],
    )
    if client_company_id is not _ABSENT:
        payload.client_company_id = client_company_id
    return payload


@pytest.fixture(name = 'spy')
def _spy(monkeypatch):
    '''
        Replaces the collaborators of create_visit_items with recorders, so the
        test asserts on which company id reached each of them.
    '''
    calls = SimpleNamespace(sku = [], assortment = [], bulk = [])

    monkeypatch.setattr(trade_utils, 'validate_active_attendance',
                        lambda **kwargs: None)
    monkeypatch.setattr(trade_utils, 'get_product_id_by_sku',
                        lambda db, company_id, sku: calls.sku.append(company_id) or 99)
    monkeypatch.setattr(trade_utils, 'validate_product_assigned_to_pos',
                        lambda db, company_id, pos_id, product_id:
                            calls.assortment.append(company_id))

    async def _fake_bulk(**kwargs):
        calls.bulk.append(kwargs['catalog_company_id'])
        return ['row']

    monkeypatch.setattr(trade_utils, 'create_bulk_items_from_skus', _fake_bulk)
    return calls


def test_visit_items_resolve_skus_against_the_client_company(spy):
    '''
        With a client company on the payload, all three lookups use it.
    '''
    asyncio.run(trade_utils.create_visit_items(
        db = None,
        attendance_id = 5,
        payload = _payload(CLIENT_COMPANY),
        model_class = object,
    ))

    assert spy.sku == [CLIENT_COMPANY]
    assert spy.assortment == [CLIENT_COMPANY]
    # The one that used to receive the executor and break the write.
    assert spy.bulk == [CLIENT_COMPANY]


def test_visit_items_fall_back_to_the_executor_company(spy):
    '''
        Legacy payloads without a client company keep working against the
        executor tenant.
    '''
    asyncio.run(trade_utils.create_visit_items(
        db = None,
        attendance_id = 5,
        payload = _payload(),
        model_class = object,
    ))

    assert spy.sku == [EXECUTOR_COMPANY]
    assert spy.assortment == [EXECUTOR_COMPANY]
    assert spy.bulk == [EXECUTOR_COMPANY]


def test_null_client_company_falls_back_to_the_executor(spy):
    '''
        A payload that ships client_company_id = null (the field exists but was
        not filled) behaves like a legacy payload instead of querying company
        "None".
    '''
    asyncio.run(trade_utils.create_visit_items(
        db = None,
        attendance_id = 5,
        payload = _payload(None),
        model_class = object,
    ))

    assert spy.bulk == [EXECUTOR_COMPANY]
