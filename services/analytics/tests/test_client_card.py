'''
    Tests for the client card (plan phase 7): one client's purchases, what it
    owes and the timeline of its invoices and payments.
'''
import asyncio

import pytest
from fastapi import HTTPException

from controllers import analytics, client_card as controller
from schemas.client import ClientCardResponse, ClientListResponse, TimelineKind
from services import currency
from tests.demo_files import serve_demo_files
from tests.test_controllers import _sales_frame


@pytest.fixture(autouse = True)
def _files(monkeypatch) -> None:
    '''
        The demo sales and payments in place of S3, at ten bolivianos per dollar.

        Args:
            monkeypatch: Pytest fixture.
    '''
    monkeypatch.setattr(currency, '_fetch_rates',
                        lambda *args: [{'date': '2020-01-01', 'rate': 10.0}])
    serve_demo_files(monkeypatch, (analytics, controller))
    monkeypatch.setattr(controller, 'get_credit_policy', lambda **_: None)


def _card(client_id: str) -> ClientCardResponse:
    '''
        Runs the card controller.

        Args:
            client_id (str): The client.

        Returns:
            ClientCardResponse: What the endpoint answers.
    '''
    return asyncio.run(controller.client_card_controller(
        dynamodb_resource = None, dataset_id = 'test-dataset-id', client_id = client_id,
        params = {}, current_user = 'tester@bearsoft.com.bo'))


def test_the_card_gathers_one_client():
    '''PDV-0 bought 15 times; its total and its months come in three currencies.'''
    card = _card('PDV-0')
    sales = _sales_frame()
    own = sales.loc[sales['pos_id'] == 'PDV-0']

    assert card.name == 'Tienda 0'
    assert card.purchases == own['order_id'].nunique()
    assert card.total.bob == round(own['total_amount'].sum(), 2)
    assert card.total.usd == round(card.total.bob / 10, 2)
    assert card.months and card.months[0].amount.usd is not None


def test_the_timeline_follows_invoices_and_payments():
    '''Each credit invoice says what was paid and what is owed; the balance adds up.'''
    card = _card('PDV-0')
    invoices = [entry for entry in card.timeline if entry.kind is TimelineKind.INVOICE]
    payments = [entry for entry in card.timeline if entry.kind is TimelineKind.PAYMENT]

    assert invoices and payments
    assert card.timeline == sorted(card.timeline, key = lambda entry: entry.date, reverse = True)
    owed = round(sum(entry.balance.bob for entry in invoices), 2)
    assert owed == card.receivable.balance.bob


def test_a_client_not_in_the_dataset_answers_not_found():
    '''An unknown client is a 404 with its code, not an empty card.'''
    with pytest.raises(HTTPException) as refused:
        _card('NOBODY')

    assert refused.value.status_code == 404
    assert refused.value.detail == 'CLIENT_NOT_FOUND'


def test_the_client_list_puts_the_largest_first():
    '''Eight clients, sorted by what they bought.'''
    response = asyncio.run(controller.client_list_controller(
        dynamodb_resource = None, dataset_id = 'test-dataset-id', params = {},
        current_user = 'tester@bearsoft.com.bo', request = None))

    assert isinstance(response, ClientListResponse)
    assert len(response.clients) == 8
    amounts = [client.amount.bob for client in response.clients]
    assert amounts == sorted(amounts, reverse = True)
