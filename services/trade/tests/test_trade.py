'''
    services/trade/tests/test_trade.py
'''
from types import SimpleNamespace

from services.trade_utils import attach_visit_fields


def test_placeholder():
    '''
        A simple placeholder test to ensure pytest finds a test to run.
    '''
    assert True


def test_attach_visit_fields_fills_pos_and_user():
    '''
        Binaria 2026-07-08: a row without its own company_id gets company/pos/
        user resolved from the visit attendance (reception / inventory lines).
    '''
    attendance = SimpleNamespace(point_of_sale_id=7, user_id=3, company_id=11)
    row = SimpleNamespace(id=1, quantity=5)

    attach_visit_fields(row, attendance)

    assert row.pos_id == 7
    assert row.user_id == 3
    assert row.company_id == 11


def test_attach_visit_fields_preserves_existing_company_id():
    '''
        A row that already carries its own company_id (e.g. a report) keeps it;
        only pos_id / user_id are resolved from the attendance.
    '''
    attendance = SimpleNamespace(point_of_sale_id=7, user_id=3, company_id=11)
    row = SimpleNamespace(id=1, company_id=99)

    attach_visit_fields(row, attendance)

    assert row.company_id == 99   # own value preserved
    assert row.pos_id == 7
    assert row.user_id == 3


def test_attach_visit_fields_handles_missing_attendance():
    '''
        A row whose visit attendance could not be resolved yields null visit
        fields instead of raising.
    '''
    row = SimpleNamespace(id=1)

    attach_visit_fields(row, None)

    assert row.pos_id is None
    assert row.user_id is None
    assert row.company_id is None
