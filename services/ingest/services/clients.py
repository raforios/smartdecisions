'''
    The client master — who buys, stated once.

    A sales file says a client bought; it does not say where the client is, what
    kind of shop it is or who its contact is. Repeating that on every line makes
    it true in one file and false in the next, and loses whatever the last file
    happened to omit. So it lives here, keyed by the code the owner's own system
    uses, and the transaction files only identify it.

    Three doors feed the master and one rule governs all three: a client that is
    not there is CREATED; a client that is already there is NOT rewritten, only
    its empty fields are filled in. A reload cannot undo a correction, and a
    file exported without coordinates cannot blank the coordinates a seller
    walked to the door to capture. Overwriting is a separate, explicit act.

    Reading goes the other way: what a file omits about a client is taken from
    the master before the frame is analysed, which is what keeps Routes alive
    when the ERP of the month exports no latitude.
'''
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from boto3.resources.base import ServiceResource

from models.clients import ClientItem
from schemas.clients import (
    ClientListResponseSchema,
    FieldClientSchema,
    ClientResponseSchema,
    ClientSource,
    ClientUpdateSchema,
    ClientUpsertResultSchema,
    ClientUpsertSchema
)
from schemas.ingest import CLIENT_SALES_ATTRIBUTES
from services.crud import find_item_by_key, query_by_partition
from services.environment import load_and_validate_env_vars
from services.exceptions import ResourceNotFoundError
from services.ingest_utils import from_dynamo, to_dynamo
from services.logger_config import custom_logger as logger
from services.utils import get_current_time_gmt


ENV_VARS = load_and_validate_env_vars({
    'DYNAMODB_TABLE_NAME_INGEST_CLIENTS': str,
    'FIELD_CLIENT_COORDINATE_DECIMALS': int,
})
CLIENTS_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_INGEST_CLIENTS']

# How a client is identified inside a validated frame: its code and its name.
# Stated once so the sales, visits and field pipelines cannot disagree.
CLIENT_FRAME_COLUMNS: Tuple[str, str] = ('pos_id', 'pos_name')

# A client registered from the street with no code of its own gets one built
# from the reading that created it: stable, and it says where it came from.
_FIELD_PREFIX = 'FLD'
# How close two readings have to be to be the same door. It decides whether a
# second seller registers the same shop or a duplicate, so it is a decision and
# it lives in the environment.
_COORDINATE_DECIMALS = ENV_VARS['FIELD_CLIENT_COORDINATE_DECIMALS']

# A coordinate of exactly zero is the absence of a reading, not the Gulf of
# Guinea. Stated here because the whole master agrees on it.
_NO_COORDINATE = 0.0


def _is_empty(value: Any) -> bool:
    '''
        Whether a value carries no information, and may therefore be filled in.

        Args:
            value (Any): Candidate value.

        Returns:
            bool: True when the field is considered empty.
    '''
    if value is None:
        return True
    if isinstance(value, float) and pd.isna(value):
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def _clean(attributes: Dict[str, Any]) -> Dict[str, Any]:
    '''
        Drops the attributes that carry no information, so an absent field never
        travels as a value that overwrites a known one. Coordinates at exactly
        zero are dropped with them.

        Args:
            attributes (Dict[str, Any]): Raw attributes of one client.

        Returns:
            Dict[str, Any]: Only the attributes worth storing.
    '''
    cleaned: Dict[str, Any] = {}
    for key, value in attributes.items():
        if _is_empty(value):
            continue
        if key in ('latitude', 'longitude') and float(value) == _NO_COORDINATE:
            continue
        cleaned[key] = value.strip() if isinstance(value, str) else value
    return cleaned


def to_client_response(item: ClientItem) -> ClientResponseSchema:
    '''
        Turns a stored client into its DTO.

        Args:
            item (ClientItem): Item as DynamoDB returned it.

        Returns:
            ClientResponseSchema: The client as the API publishes it.
    '''
    return ClientResponseSchema(**from_dynamo(
        {key: value for key, value in item.items() if key != 'owner_email'}
    ))


def get_client(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    client_id: str
) -> ClientItem:
    '''
        One client of the owner's master.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account that owns the data.
            client_id (str): Client code.

        Returns:
            ClientItem: The stored client.

        Raises:
            ResourceNotFoundError: CLIENT_NOT_FOUND when it is not the owner's.
    '''
    item = find_item_by_key(
        dynamodb_resource = dynamodb_resource,
        table_name = CLIENTS_TABLE,
        key = {'owner_email': owner_email, 'id': client_id}
    )
    if not item:
        error_msg = f'Client {client_id} not found for {owner_email}.'
        logger.warning(error_msg)
        raise ResourceNotFoundError(detail = error_msg)
    return item


def list_clients(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    seller: Optional[str] = None
) -> List[ClientItem]:
    '''
        The owner's clients, optionally narrowed to one seller's portfolio.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account that owns the data.
            seller (Optional[str]): Salesperson the client is assigned to.

        Returns:
            List[ClientItem]: Matching clients, by code.
    '''
    items = query_by_partition(
        dynamodb_resource = dynamodb_resource,
        table_name = CLIENTS_TABLE,
        partition_key = 'owner_email',
        partition_value = owner_email
    )
    if seller:
        items = [item for item in items if item.get('seller') == seller]
    return sorted(items, key = lambda item: item['id'])


def to_client_list_response(items: List[ClientItem]) -> ClientListResponseSchema:
    '''
        Wraps a list of clients with the two counts that matter when deciding
        whether Routes has anything to draw.

        Args:
            items (List[ClientItem]): Stored clients.

        Returns:
            ClientListResponseSchema: The list and its counts.
    '''
    clients = [to_client_response(item) for item in items]
    placed = sum(
        1 for client in clients
        if client.latitude is not None and client.longitude is not None
    )
    return ClientListResponseSchema(
        clients = clients,
        total = len(clients),
        with_coordinates = placed
    )


def upsert_clients(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    clients: List[ClientUpsertSchema],
    source: ClientSource
) -> ClientUpsertResultSchema:
    '''
        Feeds the master: creates what is missing and completes what is empty.

        Never overwrites a field that already holds a value — that is what
        `update_client` is for. The three counts it returns are what tells a
        caller whether the load did anything at all.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account that owns the data.
            clients (List[ClientUpsertSchema]): Clients to feed in.
            source (ClientSource): Which of the three doors they came through.

        Returns:
            ClientUpsertResultSchema: Created, completed and unchanged counts.
    '''
    table = dynamodb_resource.Table(CLIENTS_TABLE)
    now = get_current_time_gmt().isoformat()
    created = completed = unchanged = 0

    for candidate in clients:
        attributes = _clean(candidate.model_dump(exclude = {'id'}))
        stored = find_item_by_key(
            dynamodb_resource = dynamodb_resource,
            table_name = CLIENTS_TABLE,
            key = {'owner_email': owner_email, 'id': candidate.id}
        )
        if stored is None:
            item: ClientItem = {
                'owner_email': owner_email,
                'id': candidate.id,
                'source': source.value,
                'created_at': now,
                'updated_at': now,
                **attributes
            }
            table.put_item(Item = to_dynamo(item))
            created += 1
            continue

        missing = {
            key: value for key, value in attributes.items()
            if _is_empty(from_dynamo(stored.get(key)))
        }
        if not missing:
            unchanged += 1
            continue
        stored.update(to_dynamo(missing))
        stored['updated_at'] = now
        table.put_item(Item = stored)
        completed += 1

    message = (f'Client master of {owner_email} fed from {source.value}: '
               f'{created} created, {completed} completed, {unchanged} unchanged.')
    logger.info(message)
    return ClientUpsertResultSchema(
        created = created,
        completed = completed,
        unchanged = unchanged
    )


def update_client(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    client_id: str,
    changes: ClientUpdateSchema
) -> ClientItem:
    '''
        Corrects a client already in the master, overwriting what it names.

        This is the explicit act a load is not: someone decided this value is
        wrong. Fields left out of the payload are untouched.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account that owns the data.
            client_id (str): Client code.
            changes (ClientUpdateSchema): Attributes to overwrite.

        Returns:
            ClientItem: The stored client after the change.

        Raises:
            ResourceNotFoundError: CLIENT_NOT_FOUND when it is not the owner's.
    '''
    stored = get_client(dynamodb_resource, owner_email, client_id)
    stored.update(to_dynamo(changes.model_dump(exclude_unset = True)))
    stored['updated_at'] = get_current_time_gmt().isoformat()
    dynamodb_resource.Table(CLIENTS_TABLE).put_item(Item = stored)
    message = f'Client {client_id} of {owner_email} corrected.'
    logger.info(message)
    return stored


# ---------------------------------------------------------------------------
# The bridge with the transaction frames
# ---------------------------------------------------------------------------

def clients_from_frame(
    frame: pd.DataFrame,
    id_column: str,
    name_column: str
) -> List[ClientUpsertSchema]:
    '''
        The clients a validated frame implies, each once.

        Only the attributes the frame is allowed to carry about a client are
        read, so a column that happens to share a name with a master field
        cannot leak into it.

        Args:
            frame (pd.DataFrame): Validated sales or visits frame.
            id_column (str): Column holding the client code.
            name_column (str): Column holding the client name.

        Returns:
            List[ClientUpsertSchema]: One entry per distinct client.
    '''
    if frame.empty or id_column not in frame.columns:
        return []
    columns = [
        column for column in CLIENT_SALES_ATTRIBUTES
        if column in frame.columns and column != 'name'
    ]
    rows = frame[[id_column] + ([name_column] if name_column in frame.columns else [])
                 + columns].drop_duplicates(subset = [id_column], keep = 'last')
    clients: List[ClientUpsertSchema] = []
    for record in rows.to_dict(orient = 'records'):
        client_id = record.get(id_column)
        if _is_empty(client_id):
            continue
        name = record.get(name_column)
        attributes = _clean({column: record.get(column) for column in columns})
        clients.append(ClientUpsertSchema(
            id = str(client_id),
            name = str(name) if not _is_empty(name) else str(client_id),
            **attributes
        ))
    return clients


def enrich_frame(
    frame: pd.DataFrame,
    master: List[ClientItem],
    id_column: str
) -> pd.DataFrame:
    '''
        Fills in what the file did not say about its clients, from the master.

        Only empty cells are written, so a file that DOES carry a value keeps
        it: the file is the fresher evidence about the transaction, the master
        about the client.

        Args:
            frame (pd.DataFrame): Validated frame to complete.
            master (List[ClientItem]): The owner's clients.
            id_column (str): Column holding the client code.

        Returns:
            pd.DataFrame: The same frame with its blanks filled where possible.
    '''
    if frame.empty or not master or id_column not in frame.columns:
        return frame
    known = {str(item['id']): from_dynamo(item) for item in master}
    codes = frame[id_column].astype(str)
    for column in CLIENT_SALES_ATTRIBUTES:
        if column not in frame.columns:
            continue
        replacement = codes.map(lambda code, field = column: known.get(code, {}).get(field))
        if column in ('latitude', 'longitude'):
            blank = frame[column].isna() | (frame[column] == _NO_COORDINATE)
        else:
            blank = frame[column].isna()
        frame.loc[blank, column] = replacement[blank]
    return frame


def sync_master(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    frame: pd.DataFrame,
    columns: Tuple[str, str],
    source: ClientSource
) -> pd.DataFrame:
    '''
        Runs both directions of the master against one validated frame.

        First the frame feeds the master —clients it does not know are created,
        fields it has empty are filled— and only then the master fills the
        frame's own blanks. In that order a single load both teaches and
        learns: a file that brings coordinates for the first time leaves them
        stored, and a file that brings none gets the ones already known.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account that owns the data.
            frame (pd.DataFrame): Validated sales or visits frame.
            columns (Tuple[str, str]): Client code column and client name column.
            source (ClientSource): Which door the frame came through.

        Returns:
            pd.DataFrame: The frame with its client blanks filled where possible.
    '''
    id_column, name_column = columns
    upsert_clients(
        dynamodb_resource = dynamodb_resource,
        owner_email = owner_email,
        clients = clients_from_frame(frame, id_column, name_column),
        source = source
    )
    return enrich_frame(
        frame = frame,
        master = list_clients(dynamodb_resource, owner_email),
        id_column = id_column
    )


def field_client_code(client: FieldClientSchema) -> str:
    '''
        The identifier of a client the seller registered without a code.

        Args:
            client (FieldClientSchema): What the seller reported.

        Returns:
            str: A stable code derived from the position.
    '''
    latitude = round(client.latitude, _COORDINATE_DECIMALS)
    longitude = round(client.longitude, _COORDINATE_DECIMALS)
    return f'{_FIELD_PREFIX}-{latitude}-{longitude}'.replace('.', '_')


def register_field_client(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    client: FieldClientSchema,
    seller: str
) -> ClientItem:
    '''
        The third door: a seller registers a client from the street.

        It runs the same `upsert_clients` the file and the API run —creating
        what is missing and completing what is empty— rather than a second copy
        of that rule. What this adds is its own two facts: the code derived
        from the reading when the seller has none, and who was standing there.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account that owns the data.
            client (FieldClientSchema): What the seller reported.
            seller (str): Email of the person reporting it.

        Returns:
            ClientItem: The stored client, new or completed.
    '''
    client_id = client.id or field_client_code(client)
    upsert_clients(
        dynamodb_resource = dynamodb_resource,
        owner_email = owner_email,
        clients = [ClientUpsertSchema(
            **client.model_dump(exclude = {'id'}),
            id = client_id,
            seller = seller
        )],
        source = ClientSource.FIELD
    )
    return get_client(dynamodb_resource, owner_email, client_id)
