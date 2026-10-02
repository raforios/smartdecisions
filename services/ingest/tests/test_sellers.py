'''
    Tests for the seller master.

    What they defend: the files name a seller the way the ERP does and the
    phone signs in with an email, and Routes only works if the two are the same
    person. A load registers the sellers without ever rewriting the link a
    manager made, and the link is what lets a user find their own sellers.
'''
import asyncio

import pandas as pd
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from controllers import sellers as controllers
from main import app
from schemas.clients import ClientSource
from schemas.sellers import SellerListResponseSchema, SellerResponseSchema, SellerUpdateSchema
from services import clients as master
from services import sellers as seller_master
from services.db_connection import GET_DB_DEPENDENCY
from services.security import get_current_payload
from tests.test_clients import OWNER, _FakeResource


@pytest.fixture(name = 'resource')
def resource_fixture() -> _FakeResource:
    '''
        Empty masters.

        Returns:
            _FakeResource: DynamoDB double.
    '''
    return _FakeResource()


def _load(
    resource: _FakeResource,
    sellers: list
) -> None:
    '''
        Runs a sales frame through the same sync every load goes through.

        Args:
            resource (_FakeResource): DynamoDB double.
            sellers (list): One seller per sales row.
    '''
    frame = pd.DataFrame({
        'pos_id': [f'C-{index}' for index in range(len(sellers))],
        'pos_name': [f'Tienda {index}' for index in range(len(sellers))],
        'seller': sellers
    })
    master.sync_master(resource, OWNER, frame, master.CLIENT_FRAME_COLUMNS, ClientSource.FILE)


def _list(
    resource: _FakeResource,
    user_email: str | None = None
) -> SellerListResponseSchema:
    '''
        Runs the list controller.

        Args:
            resource (_FakeResource): DynamoDB double.
            user_email (str | None): Narrow to the sellers one user is.

        Returns:
            SellerListResponseSchema: What the endpoint answers.
    '''
    return asyncio.run(controllers.list_sellers_controller(
        dynamodb_resource = resource,
        user_email = user_email,
        current_user = OWNER,
        request = None
    ))


def _link(
    resource: _FakeResource,
    seller_id: str,
    changes: SellerUpdateSchema
) -> SellerResponseSchema:
    '''
        Runs the update controller.

        Args:
            resource (_FakeResource): DynamoDB double.
            seller_id (str): Seller code.
            changes (SellerUpdateSchema): What to overwrite.

        Returns:
            SellerResponseSchema: What the endpoint answers.
    '''
    return asyncio.run(controllers.update_seller_controller(
        dynamodb_resource = resource,
        seller_id = seller_id,
        changes = changes,
        current_user = OWNER,
        request = None
    ))


def test_a_load_registers_the_sellers_it_names_once(resource):
    '''
        Every door that loads sales or visits goes through `sync_master`, so
        that is where the sellers are learnt: each one once, blanks ignored.
    '''
    _load(resource, ['Ana', 'Juan', 'Ana', None, ' '])

    listed = _list(resource)
    assert [seller.id for seller in listed.sellers] == ['Ana', 'Juan']
    assert listed.total == 2 and listed.linked == 0
    # The client master is a different table and did not get the sellers.
    assert all(key[1].startswith('C-') for key in resource.rows)


def test_a_reload_never_undoes_the_link_a_manager_made(resource):
    '''A file cannot know who the seller signs in as; it must not erase it.'''
    _load(resource, ['Ana'])
    _link(resource, 'Ana', SellerUpdateSchema(user_email = 'Ana@Empresa.com'))
    _load(resource, ['Ana', 'Juan'])

    by_id = {seller.id: seller for seller in _list(resource).sellers}
    assert by_id['Ana'].user_email == 'ana@empresa.com'
    assert by_id['Juan'].user_email is None


def test_a_user_finds_the_sellers_they_are(resource):
    '''
        The phone signs in with an email; this is how it learns which names in
        the files are its own, whatever case the manager typed.
    '''
    _load(resource, ['Ana', 'V-017', 'Juan'])
    _link(resource, 'Ana', SellerUpdateSchema(user_email = 'ana@empresa.com'))
    _link(resource, 'V-017', SellerUpdateSchema(user_email = 'ana@empresa.com'))

    mine = _list(resource, 'ANA@empresa.com')
    assert [seller.id for seller in mine.sellers] == ['Ana', 'V-017']
    assert _list(resource).linked == 2


def test_an_unknown_seller_answers_its_code(resource):
    '''A seller of another owner, or none at all, is the same not-found.'''
    with pytest.raises(HTTPException) as missing:
        _link(resource, 'Nadie', SellerUpdateSchema(name = 'Nadie'))
    assert missing.value.detail == 'SELLER_NOT_FOUND'


def test_sellers_from_frame_ignores_a_frame_without_the_column():
    '''Collections carry no seller; reading them must not invent one.'''
    assert not seller_master.sellers_from_frame(pd.DataFrame({'order_id': ['F-1']}))


def test_the_sellers_route_is_not_swallowed_by_the_dataset_route(resource):
    '''
        `/v1/ingest/{dataset_id}` would take `/v1/ingest/sellers` and answer
        422, the same collision `/clients` and `/history` already had.
    '''
    _load(resource, ['Ana'])
    app.dependency_overrides[GET_DB_DEPENDENCY] = lambda: resource
    app.dependency_overrides[get_current_payload] = lambda: {
        'email': OWNER, 'role': 'MANAGER', 'client': None
    }
    try:
        response = TestClient(app).get('/v1/ingest/sellers')
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    assert [seller['id'] for seller in response.json()['sellers']] == ['Ana']
