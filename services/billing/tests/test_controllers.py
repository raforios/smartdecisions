'''
    Controller-level tests for the cash tills: each endpoint returns its model
    assembled, and every change is audited (case 16 of
    `docs/cambios/billing-caja/spec.md`).

    `request` is None, so no usage log leaves; the audit hook is replaced by a
    recorder.
'''
import asyncio
from unittest.mock import patch

import pytest

from controllers import billing_cash as controllers
from schemas.billing_cash import (
    CashAlertsResponse,
    CashCloseIn,
    CashOpenIn,
    CashSessionOut,
    CashSessionsResponse,
    CashSessionStatus,
    ExpenseIn,
    ExpenseType,
    TillClose,
    TillExpense,
    TillExpenseRef,
    TillQuery,
    TillRef
)
from services import utils
from tests.test_billing import OWNER, _dynamodb # pylint: disable=unused-import

SELLER = 'vendedor@farmacia.bo'


@pytest.fixture(name = 'audited')
def _audited():
    '''
        Records every audit the controllers schedule.

        Returns:
            list: (entity, action) pairs, in order.
    '''
    calls: list = []

    def _record(
        result, # pylint: disable=unused-argument
        kwargs, # pylint: disable=unused-argument
        microservice_name, # pylint: disable=unused-argument
        entity_name,
        action
    ):
        calls.append((entity_name, action))

    with patch.object(utils, '_schedule_audit', _record):
        yield calls


def _call(
    controller,
    **arguments
):
    '''
        Runs a controller as the endpoint would, as SELLER in the demo shop.

        Args:
            controller: The async controller.
            **arguments: Its specific arguments.

        Returns:
            Any: What it returned.
    '''
    return asyncio.run(controller(owner = OWNER, request = None, current_user = SELLER,
                                  **arguments))


def test_every_till_action_is_audited_and_returns_its_model(
    dynamodb,
    audited
):
    '''Case 16: open, expense, cancel and close audited; the reads are not.'''
    opened = _call(controllers.open_till_controller, dynamodb_resource = dynamodb,
                   opening = CashOpenIn(opening_cash = 200))
    assert isinstance(opened, CashSessionOut)
    session_id = opened.session_id

    current = _call(controllers.current_till_controller, dynamodb_resource = dynamodb)
    assert current.session_id == session_id

    spent = _call(controllers.add_expense_controller, dynamodb_resource = dynamodb,
                  target = TillExpense(session_id = session_id, expense = ExpenseIn(
                      expense_type = ExpenseType.PETTY_CASH, amount = 20,
                      concept = 'Bolsas')))
    movement_id = spent.movements[0].movement_id

    _call(controllers.cancel_expense_controller, dynamodb_resource = dynamodb,
          target = TillExpenseRef(session_id = session_id, movement_id = movement_id))

    one = _call(controllers.get_till_controller, dynamodb_resource = dynamodb,
                ref = TillRef(session_id = session_id))
    assert one.expected_cash == 200

    listed = _call(controllers.list_tills_controller, dynamodb_resource = dynamodb,
                   query = TillQuery())
    assert isinstance(listed, CashSessionsResponse)

    alerts = _call(controllers.till_alerts_controller, dynamodb_resource = dynamodb,
                   is_manager = False)
    assert isinstance(alerts, CashAlertsResponse)

    closed = _call(controllers.close_till_controller, dynamodb_resource = dynamodb,
                   target = TillClose(session_id = session_id,
                                      closing = CashCloseIn(counted_cash = 200)))
    assert closed.status is CashSessionStatus.CLOSED

    assert audited == [('CashSession', 'OPEN'), ('CashSession', 'EXPENSE'),
                       ('CashSession', 'CANCEL_EXPENSE'), ('CashSession', 'CLOSE')]
