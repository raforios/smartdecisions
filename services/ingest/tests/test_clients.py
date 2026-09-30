'''
    Tests for the client master.

    They cover the rule the whole design rests on: a load CREATES what is
    missing and COMPLETES what is empty, and never overwrites what is stored.
    A reload that blanked a coordinate captured in the field would silently
    turn Routes off, which is exactly the failure this master exists to stop.
'''
import asyncio
from decimal import Decimal
from typing import Any, Dict, List, Optional

import pandas as pd
import pytest

from controllers import clients as controllers
from schemas.clients import (
    ClientBulkUpsertSchema,
    ClientListResponseSchema,
    ClientResponseSchema,
    ClientSource,
    ClientUpsertResultSchema,
    ClientUpdateSchema,
    ClientUpsertSchema,
    FieldClientSchema
)
from services import clients as master
from services.exceptions import ResourceNotFoundError


class _FakeTable:
    '''
        The slice of a DynamoDB table the master uses: put and get by key.
    '''

    def __init__(
        self,
        rows: Dict[tuple, Dict[str, Any]]
    ) -> None:
        self.rows = rows

    # The boto3 parameter names are the contract; the double has to match them.
    # pylint: disable=invalid-name
    def put_item(
        self,
        Item: Dict[str, Any]
    ) -> None:
        '''Stores the item under its composite key.'''
        self.rows[(Item['owner_email'], Item['id'])] = dict(Item)

    def get_item(
        self,
        Key: Dict[str, Any]
    ) -> Dict[str, Any]:
        '''Returns the item under a composite key, or an empty response.'''
        row = self.rows.get((Key['owner_email'], Key['id']))
        return {'Item': dict(row)} if row else {}

    def query(
        self,
        KeyConditionExpression: Any
    ) -> Dict[str, Any]:
        '''Returns every row of the owner in the condition.'''
        owner = KeyConditionExpression._values[1] # pylint: disable=protected-access
        return {'Items': [dict(row) for key, row in self.rows.items() if key[0] == owner]}


# The double mirrors the boto3 resource surface, which is one method wide.
# pylint: disable=too-few-public-methods
class _FakeResource:
    '''
        A DynamoDB resource backed by one in-memory table.
    '''

    def __init__(self) -> None:
        self.rows: Dict[tuple, Dict[str, Any]] = {}

    # Same reason as _FakeTable: boto3 spells it `Table`.
    # pylint: disable=invalid-name
    def Table(
        self,
        name: str # pylint: disable=unused-argument
    ) -> _FakeTable:
        '''Returns the single table this double holds.'''
        return _FakeTable(self.rows)


OWNER = 'tester@bearsoft.com.bo'


@pytest.fixture(name = 'resource')
def resource_fixture() -> _FakeResource:
    '''
        An empty client master.

        Returns:
            _FakeResource: DynamoDB double.
    '''
    return _FakeResource()


def _client(
    code: str,
    name: str = 'Tienda',
    **attributes: Any
) -> ClientUpsertSchema:
    '''
        Builds one client for a load.

        Args:
            code (str): Client code.
            name (str): Client name.
            **attributes (Any): Any other master attribute.

        Returns:
            ClientUpsertSchema: The client to feed in.
    '''
    return ClientUpsertSchema(id = code, name = name, **attributes)


def _stored(
    resource: _FakeResource,
    code: str
) -> Optional[Dict[str, Any]]:
    '''
        Reads one client straight out of the double.

        Args:
            resource (_FakeResource): DynamoDB double.
            code (str): Client code.

        Returns:
            Optional[Dict[str, Any]]: The stored row.
    '''
    return resource.rows.get((OWNER, code))


def test_a_client_that_does_not_exist_is_created(resource):
    '''The first load of a client stores it with its source and timestamps.'''
    result = master.upsert_clients(
        dynamodb_resource = resource,
        owner_email = OWNER,
        clients = [_client('C-1', 'Tienda Uno', latitude = -16.5, longitude = -68.1)],
        source = ClientSource.FILE
    )

    assert (result.created, result.completed, result.unchanged) == (1, 0, 0)
    row = _stored(resource, 'C-1')
    assert row['name'] == 'Tienda Uno'
    assert float(row['latitude']) == -16.5
    assert row['source'] == 'FILE'
    assert row['created_at'] and row['updated_at']


def test_a_reload_does_not_overwrite_what_is_already_stored(resource):
    '''
        The rule the master exists for: a second file cannot undo a value.

        A seller captured the coordinates at the door; the nightly export has
        none and a different name. Neither may win over what is stored.
    '''
    master.upsert_clients(
        dynamodb_resource = resource, owner_email = OWNER, source = ClientSource.FIELD,
        clients = [_client('C-1', 'Tienda Uno', latitude = -16.5, longitude = -68.1)]
    )
    result = master.upsert_clients(
        dynamodb_resource = resource, owner_email = OWNER, source = ClientSource.FILE,
        clients = [_client('C-1', 'TIENDA 1 (ERP)')]
    )

    assert (result.created, result.completed, result.unchanged) == (0, 0, 1)
    row = _stored(resource, 'C-1')
    assert row['name'] == 'Tienda Uno'
    assert float(row['latitude']) == -16.5


def test_a_reload_fills_in_only_the_empty_fields(resource):
    '''What the master did not know it learns; what it knew it keeps.'''
    master.upsert_clients(
        dynamodb_resource = resource, owner_email = OWNER, source = ClientSource.FILE,
        clients = [_client('C-1', 'Tienda Uno')]
    )
    result = master.upsert_clients(
        dynamodb_resource = resource, owner_email = OWNER, source = ClientSource.FIELD,
        clients = [_client('C-1', 'Otro nombre', latitude = -16.5, longitude = -68.1,
                           address = 'Av. Siempre Viva 742')]
    )

    assert (result.created, result.completed, result.unchanged) == (0, 1, 0)
    row = _stored(resource, 'C-1')
    assert row['name'] == 'Tienda Uno'
    assert float(row['latitude']) == -16.5
    assert row['address'] == 'Av. Siempre Viva 742'


def test_a_coordinate_of_zero_is_not_a_reading(resource):
    '''Zero is the absence of a GPS fix, not a point in the Gulf of Guinea.'''
    master.upsert_clients(
        dynamodb_resource = resource, owner_email = OWNER, source = ClientSource.FILE,
        clients = [_client('C-1', 'Tienda Uno', latitude = 0.0, longitude = 0.0)]
    )

    row = _stored(resource, 'C-1')
    assert 'latitude' not in row
    assert 'longitude' not in row


def test_a_correction_does_overwrite(resource):
    '''PATCH is the explicit act a load is not.'''
    master.upsert_clients(
        dynamodb_resource = resource, owner_email = OWNER, source = ClientSource.FILE,
        clients = [_client('C-1', 'Tienda Uno', latitude = -16.5, longitude = -68.1)]
    )
    master.update_client(
        dynamodb_resource = resource,
        owner_email = OWNER,
        client_id = 'C-1',
        changes = ClientUpdateSchema(latitude = -17.8, longitude = -63.2)
    )

    row = _stored(resource, 'C-1')
    assert float(row['latitude']) == -17.8


def test_another_owners_client_does_not_exist(resource):
    '''Isolation: a foreign record answers exactly like a missing one.'''
    master.upsert_clients(
        dynamodb_resource = resource, owner_email = 'otro@bearsoft.com.bo',
        source = ClientSource.FILE, clients = [_client('C-1')]
    )

    with pytest.raises(Exception) as error:
        master.get_client(resource, OWNER, 'C-1')
    assert 'not found' in str(error.value).lower()


def _frame(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    '''
        Builds a validated-looking sales frame.

        Args:
            rows (List[Dict[str, Any]]): Row dictionaries.

        Returns:
            pd.DataFrame: The frame.
    '''
    return pd.DataFrame(rows)


def test_the_master_learns_from_a_file_and_then_completes_it(resource):
    '''
        One load teaches and learns.

        Monday's file brings coordinates and they are stored; Tuesday's export
        drops the column and the frame comes back with them anyway. Without
        this, a client who changed ERP export would lose Routes overnight.
    '''
    monday = _frame([
        {'pos_id': 'C-1', 'pos_name': 'Tienda Uno',
         'latitude': -16.5, 'longitude': -68.1, 'quantity': 3.0},
    ])
    master.sync_master(
        dynamodb_resource = resource, owner_email = OWNER, frame = monday,
        columns = master.CLIENT_FRAME_COLUMNS, source = ClientSource.FILE
    )

    tuesday = _frame([
        {'pos_id': 'C-1', 'pos_name': 'Tienda Uno',
         'latitude': float('nan'), 'longitude': float('nan'), 'quantity': 5.0},
    ])
    completed = master.sync_master(
        dynamodb_resource = resource, owner_email = OWNER, frame = tuesday,
        columns = master.CLIENT_FRAME_COLUMNS, source = ClientSource.FILE
    )

    assert completed.loc[0, 'latitude'] == -16.5
    assert completed.loc[0, 'longitude'] == -68.1


def test_the_file_wins_over_the_master_for_the_rows_it_does_fill(resource):
    '''The master fills blanks; it does not correct what the file states.'''
    master.upsert_clients(
        dynamodb_resource = resource, owner_email = OWNER, source = ClientSource.FILE,
        clients = [_client('C-1', 'Tienda Uno', latitude = -16.5, longitude = -68.1)]
    )
    frame = master.enrich_frame(
        frame = _frame([{'pos_id': 'C-1', 'latitude': -17.8, 'longitude': -63.2}]),
        master = [dict(_stored(resource, 'C-1'))],
        id_column = 'pos_id'
    )

    assert frame.loc[0, 'latitude'] == -17.8


def test_clients_derived_from_a_frame_are_deduplicated():
    '''Thirty lines of one client are one client, not thirty.'''
    frame = _frame([
        {'pos_id': 'C-1', 'pos_name': 'Tienda Uno', 'city': 'La Paz'},
        {'pos_id': 'C-1', 'pos_name': 'Tienda Uno', 'city': 'La Paz'},
        {'pos_id': 'C-2', 'pos_name': 'Tienda Dos', 'city': 'El Alto'},
    ])
    derived = master.clients_from_frame(frame, 'pos_id', 'pos_name')

    assert [client.id for client in derived] == ['C-1', 'C-2']
    assert derived[0].city == 'La Paz'


def test_the_list_counts_how_many_can_be_placed_on_a_map(resource):
    '''That count is what decides whether Routes has anything to draw.'''
    master.upsert_clients(
        dynamodb_resource = resource, owner_email = OWNER, source = ClientSource.FILE,
        clients = [_client('C-1', 'Uno', latitude = -16.5, longitude = -68.1),
                   _client('C-2', 'Dos')]
    )
    response = master.to_client_list_response(master.list_clients(resource, OWNER))

    assert response.total == 2
    assert response.with_coordinates == 1


def test_decimals_never_reach_the_dtos(resource):
    '''DynamoDB hands back Decimal; a DTO must not meet one.'''
    resource.rows[(OWNER, 'C-1')] = {
        'owner_email': OWNER, 'id': 'C-1', 'name': 'Uno',
        'latitude': Decimal('-16.5'), 'longitude': Decimal('-68.1'),
        'credit_limit': Decimal('1000'), 'source': 'API',
        'created_at': '2026-09-27T10:00:00Z', 'updated_at': '2026-09-27T10:00:00Z'
    }
    client = master.to_client_response(_stored(resource, 'C-1'))

    assert isinstance(client.latitude, float)
    assert client.credit_limit == 1000


def test_the_seller_registers_a_client_from_the_street(resource):
    '''
        The third door.

        Without it an off-plan stop stays a pin with no client: no plan can be
        inferred from that day and no later route can reuse it.
    '''
    stored = master.register_field_client(
        dynamodb_resource = resource,
        owner_email = OWNER,
        client = FieldClientSchema(
            name = 'Abarrotes Nueva', latitude = -16.4957, longitude = -68.1335,
            address = 'Calle Murillo 120'
        ),
        seller = 'vendedor@bearsoft.com.bo'
    )

    assert stored['source'] == 'FIELD'
    assert stored['seller'] == 'vendedor@bearsoft.com.bo'
    assert float(stored['latitude']) == -16.4957
    # No code of its own, so one is derived from the reading that created it.
    assert stored['id'].startswith('FLD-')


def test_two_sellers_at_the_same_door_do_not_create_two_clients(resource):
    '''
        The derived code comes from the position, rounded to about a metre.

        Two sellers standing at the same shop on different days must land on
        the same record, or the master fills up with duplicates nobody can
        merge afterwards.
    '''
    first = master.register_field_client(
        dynamodb_resource = resource, owner_email = OWNER, seller = 'ana@bearsoft.com.bo',
        client = FieldClientSchema(name = 'Abarrotes Nueva',
                                   latitude = -16.49570, longitude = -68.13350)
    )
    second = master.register_field_client(
        dynamodb_resource = resource, owner_email = OWNER, seller = 'juan@bearsoft.com.bo',
        client = FieldClientSchema(name = 'Abarrotes Nueva 2',
                                   latitude = -16.495701, longitude = -68.133502,
                                   phone = '77712345')
    )

    assert first['id'] == second['id']
    assert len(resource.rows) == 1
    # The second visit did not rename the shop, but it did add what was missing.
    assert second['name'] == 'Abarrotes Nueva'
    assert second['phone'] == '77712345'


def test_a_seller_who_knows_the_erp_code_uses_it(resource):
    '''
        When the seller knows the code, the record marries the ERP\'s own
        client instead of creating a parallel one.
    '''
    master.upsert_clients(
        dynamodb_resource = resource, owner_email = OWNER, source = ClientSource.FILE,
        clients = [_client('C-77', 'Tienda Setenta y Siete')]
    )
    stored = master.register_field_client(
        dynamodb_resource = resource, owner_email = OWNER, seller = 'ana@bearsoft.com.bo',
        client = FieldClientSchema(id = 'C-77', name = 'Tienda 77',
                                   latitude = -16.5, longitude = -68.1)
    )

    assert len(resource.rows) == 1
    assert stored['name'] == 'Tienda Setenta y Siete'
    # What the file never knew —where the shop is— is what the street added.
    assert float(stored['latitude']) == -16.5


# ---------------------------------------------------------------------------
# Controllers
#
# The layer the engine tests never run. Twice in one session a route or a
# controller named something its schema no longer had, and the suite stayed
# green because nothing above `services/` was ever executed. These call the
# controllers exactly as their endpoints do.
# ---------------------------------------------------------------------------

def _run(coroutine):
    '''
        Runs a controller coroutine without extra plugins.

        Args:
            coroutine: The coroutine to execute.

        Returns:
            Any: Whatever the controller returns.
    '''
    return asyncio.run(coroutine)


def test_the_bulk_upsert_controller_returns_its_model(resource):
    '''The ERP door answers a fully built result, counts included.'''
    response = _run(controllers.upsert_clients_controller(
        dynamodb_resource = resource,
        payload = ClientBulkUpsertSchema(clients = [
            _client('PDV-1', 'Tienda Uno'),
            _client('PDV-2', 'Tienda Dos', latitude = -16.5, longitude = -68.1)
        ]),
        current_user = OWNER,
        request = None
    ))

    assert isinstance(response, ClientUpsertResultSchema)
    assert response.created == 2


def test_the_list_and_read_controllers_return_their_models(resource):
    '''Listing the portfolio and reading one client, as the endpoints do.'''
    _run(controllers.upsert_clients_controller(
        dynamodb_resource = resource,
        payload = ClientBulkUpsertSchema(clients = [_client('PDV-1', 'Tienda Uno')]),
        current_user = OWNER, request = None
    ))

    listed = _run(controllers.list_clients_controller(
        dynamodb_resource = resource, seller = None,
        current_user = OWNER, request = None
    ))
    one = _run(controllers.get_client_controller(
        dynamodb_resource = resource, client_id = 'PDV-1',
        current_user = OWNER, request = None
    ))

    assert isinstance(listed, ClientListResponseSchema) and listed.total == 1
    assert isinstance(one, ClientResponseSchema) and one.name == 'Tienda Uno'


def test_reading_another_owners_client_answers_not_found(resource):
    '''
        A foreign resource answers exactly like a missing one. Telling them
        apart would confirm which identifiers exist.
    '''
    _run(controllers.upsert_clients_controller(
        dynamodb_resource = resource,
        payload = ClientBulkUpsertSchema(clients = [_client('PDV-1')]),
        current_user = OWNER, request = None
    ))

    with pytest.raises(ResourceNotFoundError):
        _run(controllers.get_client_controller(
            dynamodb_resource = resource, client_id = 'PDV-1',
            current_user = 'otra@empresa.com', request = None
        ))


def test_the_update_controller_overwrites_on_purpose(resource):
    '''
        A correction is the one path that DOES overwrite, and it has to come
        back as the stored client so the screen can show what it now holds.
    '''
    _run(controllers.upsert_clients_controller(
        dynamodb_resource = resource,
        payload = ClientBulkUpsertSchema(clients = [_client('PDV-1', 'Nombre Viejo')]),
        current_user = OWNER, request = None
    ))

    response = _run(controllers.update_client_controller(
        dynamodb_resource = resource, client_id = 'PDV-1',
        changes = ClientUpdateSchema(name = 'Nombre Corregido'),
        current_user = OWNER, request = None
    ))

    assert isinstance(response, ClientResponseSchema)
    assert response.name == 'Nombre Corregido'


def test_the_field_registration_controller_returns_its_model(resource):
    '''
        The third door: a seller standing at a door nobody billed. It answers
        the created client, which is what the phone shows back.
    '''
    response = _run(controllers.register_field_client_controller(
        dynamodb_resource = resource,
        client = FieldClientSchema(
            name = 'Tienda Nueva', latitude = -16.5, longitude = -68.1
        ),
        current_user = OWNER,
        seller = 'Ana',
        request = None
    ))

    assert isinstance(response, ClientResponseSchema)
    assert response.name == 'Tienda Nueva'
    assert response.seller == 'Ana'


def test_an_empty_numeric_column_does_not_break_the_load(resource):
    '''
        The bug a real client file found: `enrich_frame` wrote the master's
        misses as well as its hits, and assigning None into a numeric column
        raises. A sales file whose `credit_limit` is entirely empty —which is
        most files— failed the whole load with a pandas TypeError.
    '''
    master.upsert_clients(resource, OWNER, [_client('PDV-1', 'Tienda Uno')],
                          ClientSource.API)
    frame = pd.DataFrame([
        {'pos_id': 'PDV-1', 'pos_name': 'Tienda Uno', 'credit_limit': float('nan')},
        {'pos_id': 'PDV-2', 'pos_name': 'Tienda Dos', 'credit_limit': float('nan')}
    ])

    enriched = master.enrich_frame(frame, master.list_clients(resource, OWNER), 'pos_id')

    assert len(enriched) == 2
    assert enriched['credit_limit'].isna().all()
