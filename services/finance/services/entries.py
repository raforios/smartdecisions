'''
    What a client loads: amounts per account and period, and the loads that
    brought them.

    The owner is the client of the token and it is part of every key, never a
    filter after the fact: another client's amount answers exactly like one
    that does not exist. Every load also records which user made it.

    A load only replaces what it brings (Rafael, 16-oct): the same account and
    period overwrite, everything else stays. A wrong amount or date is
    corrected one by one, and a period is emptied before it is loaded again
    with another periodicity.
'''
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from boto3.dynamodb.conditions import Key
from boto3.resources.base import ServiceResource

from models.finance import EntryItem, LoadItem
from schemas.entries import (
    HEADER_TO_FIELD,
    EntryListResponseSchema,
    EntryRowSchema,
    EntrySchema,
    EntryUpdateSchema,
    LoadChannel,
    LoadError,
    LoadFlow,
    LoadListResponseSchema,
    LoadResultSchema,
    ENTRY_COLUMNS,
    LoadSchema,
    PeriodDeleteResultSchema,
    Periodicity,
    RejectedRowSchema
)
from services.entries_validator import (
    RowRejected,
    ValidEntry,
    conflicting_prefixes,
    entry_key,
    validate_row,
    validate_rows
)
from services.environment import load_and_validate_env_vars
from services.exceptions import InvalidInputError, ResourceNotFoundError
from services.finance import catalog_by_code
from services.finance_utils import to_dynamo
from services.logger_config import custom_logger as logger
from services.utils import (
    TARGET_TIMEZONE,
    delete_stored_file,
    get_current_time_gmt,
    read_file_rows
)

ENV_VARS = load_and_validate_env_vars({
    'DYNAMODB_TABLE_NAME_FINANCE_LOADS': str,
    'DYNAMODB_TABLE_NAME_FINANCE_ENTRIES': str,
})
LOADS_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_FINANCE_LOADS']
ENTRIES_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_FINANCE_ENTRIES']

# The fields of a row, in contract order.
_ROW_FIELDS = tuple(column.field for column in ENTRY_COLUMNS)
# Rows of a file are reported with their Excel number: row 1 is the header.
_FILE_FIRST_ROW = 2
_API_FIRST_ROW = 1


def _today() -> datetime:
    '''
        Now, in the client's timezone: "a date after today" is a local idea.

        Returns:
            datetime: The current moment there.
    '''
    return datetime.now(ZoneInfo(TARGET_TIMEZONE))


def _has_prefix(
    dynamodb_resource: ServiceResource,
    client: str,
    prefix: str
) -> bool:
    '''
        Whether the client has anything stored under a key prefix.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            client (str): The owner.
            prefix (str): Key prefix, e.g. "DAILY#2026-03-".

        Returns:
            bool: True when at least one amount is there.
    '''
    response = dynamodb_resource.Table(ENTRIES_TABLE).query(
        KeyConditionExpression = Key('client').eq(client) & Key('entry_key').begins_with(prefix),
        Limit = 1
    )
    return bool(response.get('Items'))


def _query_prefix(
    dynamodb_resource: ServiceResource,
    client: str,
    prefix: str
) -> list[dict]:
    '''
        Every amount of the client under a key prefix, following the pages.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            client (str): The owner.
            prefix (str): Key prefix; empty for everything.

        Returns:
            list[dict]: The stored items.
    '''
    table = dynamodb_resource.Table(ENTRIES_TABLE)
    condition = Key('client').eq(client)
    if prefix:
        condition = condition & Key('entry_key').begins_with(prefix)
    response = table.query(KeyConditionExpression = condition)
    items = response.get('Items', [])
    while 'LastEvaluatedKey' in response:
        response = table.query(KeyConditionExpression = condition,
                               ExclusiveStartKey = response['LastEvaluatedKey'])
        items.extend(response.get('Items', []))
    return items


def _to_item(
    entry: ValidEntry,
    client: str,
    stamp: dict[str, str]
) -> EntryItem:
    '''
        The stored form of a valid row.

        Args:
            entry (ValidEntry): The row.
            client (str): The owner.
            stamp (dict[str, str]): flow, load_id, user and updated_at.

        Returns:
            EntryItem: The item.
    '''
    return {
        'client': client,
        'entry_key': entry.key,
        'periodicity': entry.periodicity.value,
        'date': entry.date,
        'account_code': entry.account_code,
        'amount': entry.amount,
        'note': entry.note,
        'taxes_included': entry.taxes_included,
        **stamp
    }


def to_entry_response(item: EntryItem | dict) -> EntrySchema:
    '''
        Builds the response of one stored amount.

        Args:
            item (EntryItem | dict): The stored item.

        Returns:
            EntrySchema: The amount.
    '''
    return EntrySchema(
        periodicity = item['periodicity'],
        date = item['date'],
        account_code = item['account_code'],
        amount = float(item['amount']),
        note = item.get('note'),
        taxes_included = item.get('taxes_included'),
        flow = item['flow'],
        load_id = item['load_id'],
        user = item['user'],
        updated_at = item['updated_at']
    )


def _validate_load(
    dynamodb_resource: ServiceResource,
    client: str,
    rows: list[EntryRowSchema],
    channel: LoadChannel
) -> tuple[list[ValidEntry], list[RejectedRowSchema]]:
    '''
        Runs the validator over a load, against the catalog and what the
        client already has. Each stored prefix is asked once per load.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            client (str): The owner.
            rows (list[EntryRowSchema]): The rows as they arrived.
            channel (LoadChannel): API or FILE, which numbers the rows.

        Returns:
            tuple[list[ValidEntry], list[RejectedRowSchema]]: What goes in and
                what is set aside.
    '''
    checked: dict[str, bool] = {}

    def stored_has(prefix: str) -> bool:
        if prefix not in checked:
            checked[prefix] = _has_prefix(dynamodb_resource, client, prefix)
        return checked[prefix]

    first_row = _FILE_FIRST_ROW if channel is LoadChannel.FILE else _API_FIRST_ROW
    return validate_rows(rows, catalog_by_code(dynamodb_resource),
                         _today().date(), stored_has, first_row)


def _store_entries(
    dynamodb_resource: ServiceResource,
    client: str,
    valid: list[ValidEntry],
    stamp: dict[str, str]
) -> None:
    '''
        Writes the valid rows. The same account and period overwrite: a load
        only replaces what it brings.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            client (str): The owner.
            valid (list[ValidEntry]): The rows that passed.
            stamp (dict[str, str]): flow, load_id, user and updated_at.
    '''
    with dynamodb_resource.Table(ENTRIES_TABLE).batch_writer() as batch:
        for entry in valid:
            batch.put_item(Item = to_dynamo(dict(_to_item(entry, client, stamp))))


# pylint: disable=too-many-arguments, too-many-positional-arguments
def load_entries(
    dynamodb_resource: ServiceResource,
    client: str,
    user: str,
    flow: LoadFlow,
    rows: list[EntryRowSchema],
    origin: tuple[LoadChannel, str | None] = (LoadChannel.API, None)
) -> LoadResultSchema:
    '''
        Validates a load, stores what passed and records the load.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            client (str): The owner, from the token.
            user (str): Who made the load.
            flow (LoadFlow): PROCESSED or BASE, chosen on each load.
            rows (list[EntryRowSchema]): The rows as they arrived.
            origin (tuple[LoadChannel, str | None]): The channel, and the file
                key when it came from a file.

        Returns:
            LoadResultSchema: What went in and what was set aside.
    '''
    channel, file_key = origin
    valid, rejected = _validate_load(dynamodb_resource, client, rows, channel)

    now = get_current_time_gmt().isoformat()
    load_id = f'{now}#{uuid4().hex[:8]}'
    _store_entries(dynamodb_resource, client, valid,
                   {'flow': flow.value, 'load_id': load_id, 'user': user, 'updated_at': now})
    load: LoadItem = {
        'client': client, 'load_id': load_id, 'user': user, 'flow': flow.value,
        'channel': channel.value, 'file_key': file_key,
        'accepted': len(valid), 'rejected': len(rejected), 'created_at': now
    }
    dynamodb_resource.Table(LOADS_TABLE).put_item(Item = dict(load))
    message = (f'Load {load_id} for {client} by {user}: {len(valid)} accepted, '
               f'{len(rejected)} set aside.')
    logger.info(message)
    return LoadResultSchema(load_id = load_id, flow = flow, channel = channel,
                            accepted = len(valid), rejected = rejected)


def rows_from_file(raw_rows: list[dict]) -> list[EntryRowSchema]:
    '''
        The rows of the template, from its Spanish headers to the API fields.
        A header the contract does not know is ignored.

        Args:
            raw_rows (list[dict]): The rows FILES read, keyed by header.

        Returns:
            list[EntryRowSchema]: The same rows, keyed by field.
    '''
    rows = []
    for raw in raw_rows:
        fields = {HEADER_TO_FIELD[header.strip()]: value
                  for header, value in raw.items()
                  if isinstance(header, str) and header.strip() in HEADER_TO_FIELD}
        rows.append(EntryRowSchema.model_construct(**{
            field: fields.get(field) for field in _ROW_FIELDS
        }))
    return rows


def load_entries_from_file(
    dynamodb_resource: ServiceResource,
    client: str,
    user: str,
    load: tuple[LoadFlow, str],
    auth_token: str
) -> LoadResultSchema:
    '''
        A load from a file the client uploaded through FILES. The file is read
        through FILES and removed once its rows are in: a staged upload is
        temporary.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            client (str): The owner, from the token.
            user (str): Who made the load.
            load (tuple[LoadFlow, str]): The flow and the file key.
            auth_token (str): The caller's Authorization header, for FILES.

        Returns:
            LoadResultSchema: What went in and what was set aside.

        Raises:
            InvalidInputError: EMPTY_LOAD.
    '''
    flow, file_key = load
    rows = rows_from_file(read_file_rows(file_key, auth_token))
    if not rows:
        error_msg = f'File {file_key} of {client} has no rows.'
        logger.warning(error_msg)
        raise InvalidInputError(detail = LoadError.EMPTY_LOAD.value)
    result = load_entries(dynamodb_resource, client, user, flow, rows,
                          origin = (LoadChannel.FILE, file_key))
    delete_stored_file(file_key, auth_token)
    return result


def list_loads(
    dynamodb_resource: ServiceResource,
    client: str
) -> LoadListResponseSchema:
    '''
        The loads of the client, newest first.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            client (str): The owner.

        Returns:
            LoadListResponseSchema: The history.
    '''
    response = dynamodb_resource.Table(LOADS_TABLE).query(
        KeyConditionExpression = Key('client').eq(client),
        ScanIndexForward = False
    )
    loads = [
        LoadSchema(load_id = item['load_id'], user = item['user'], flow = item['flow'],
                   channel = item['channel'], accepted = int(item['accepted']),
                   rejected = int(item['rejected']), created_at = item['created_at'])
        for item in response.get('Items', [])
    ]
    return LoadListResponseSchema(loads = loads, total = len(loads))


def list_entries(
    dynamodb_resource: ServiceResource,
    client: str,
    period: tuple[Periodicity | None, str | None] = (None, None)
) -> EntryListResponseSchema:
    '''
        The amounts of the client, all of them or those of a period.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            client (str): The owner.
            period (tuple[Periodicity | None, str | None]): The periodicity
                and a date prefix ("2026", "2026-03"); both optional.

        Returns:
            EntryListResponseSchema: The amounts.
    '''
    periodicity, day = period
    prefix = ''
    if periodicity is not None:
        prefix = f'{periodicity.value}#{day or ""}'
    entries = [to_entry_response(item)
               for item in _query_prefix(dynamodb_resource, client, prefix)]
    return EntryListResponseSchema(entries = entries, total = len(entries))


def _stored_entry(
    dynamodb_resource: ServiceResource,
    client: str,
    key: str
) -> dict:
    '''
        One amount of the client.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            client (str): The owner.
            key (str): Its sort key.

        Returns:
            dict: The stored item.

        Raises:
            ResourceNotFoundError: ENTRY_NOT_FOUND, also for another client's.
    '''
    item = dynamodb_resource.Table(ENTRIES_TABLE).get_item(
        Key = {'client': client, 'entry_key': key}
    ).get('Item')
    if not item:
        error_msg = f'Entry {key} not found for {client}.'
        logger.warning(error_msg)
        raise ResourceNotFoundError(detail = LoadError.ENTRY_NOT_FOUND.value)
    return item


def _check_new_place(
    dynamodb_resource: ServiceResource,
    client: str,
    entry: ValidEntry
) -> None:
    '''
        A corrected date moves the amount: the new place must not mix
        periodicities nor land on an amount that already exists.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            client (str): The owner.
            entry (ValidEntry): The amount at its new date.

        Raises:
            RowRejected: PERIODICITY_CONFLICT or DUPLICATE_ROW.
    '''
    if any(_has_prefix(dynamodb_resource, client, prefix)
           for prefix in conflicting_prefixes(entry.periodicity, entry.date)):
        raise RowRejected(LoadError.PERIODICITY_CONFLICT, entry.date)
    if _has_prefix(dynamodb_resource, client, entry.key):
        raise RowRejected(LoadError.DUPLICATE_ROW, entry.key)


def _corrected_entry(
    dynamodb_resource: ServiceResource,
    client: str,
    stored: dict,
    update: EntryUpdateSchema
) -> ValidEntry:
    '''
        The stored amount with the correction applied, through the same
        validator as a load.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            client (str): The owner.
            stored (dict): The amount as it is stored.
            update (EntryUpdateSchema): What changes.

        Returns:
            ValidEntry: The corrected amount.

        Raises:
            InvalidInputError: The code of the rule the correction breaks.
    '''
    row = EntryRowSchema(**{**{field: stored.get(field) for field in _ROW_FIELDS},
                            'amount': float(stored['amount']),
                            **update.model_dump(exclude_unset = True)})
    try:
        entry = validate_row(row, catalog_by_code(dynamodb_resource), _today().date())
        if entry.key != stored['entry_key']:
            _check_new_place(dynamodb_resource, client, entry)
    except RowRejected as refusal:
        error_msg = (f'Correction of {stored["entry_key"]} for {client} refused: '
                     f'{refusal.code.value}.')
        logger.warning(error_msg)
        raise InvalidInputError(detail = refusal.code.value) from refusal
    return entry


def update_entry(
    dynamodb_resource: ServiceResource,
    owner: tuple[str, str],
    target: tuple[Periodicity, str, str],
    update: EntryUpdateSchema
) -> EntrySchema:
    '''
        Corrects one amount: its figure, its date, its note or its invoice
        flags. A new date passes the same rules as a load.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (tuple[str, str]): The client and the user correcting it.
            target (tuple[Periodicity, str, str]): Periodicity, date and account.
            update (EntryUpdateSchema): What changes.

        Returns:
            EntrySchema: The amount after the correction.

        Raises:
            ResourceNotFoundError: ENTRY_NOT_FOUND.
            InvalidInputError: The code of the rule the correction breaks.
    '''
    client, user = owner
    old_key = entry_key(*target)
    stored = _stored_entry(dynamodb_resource, client, old_key)
    entry = _corrected_entry(dynamodb_resource, client, stored, update)

    stamp = {'flow': stored['flow'], 'load_id': stored['load_id'], 'user': user,
             'updated_at': get_current_time_gmt().isoformat()}
    item = _to_item(entry, client, stamp)
    table = dynamodb_resource.Table(ENTRIES_TABLE)
    table.put_item(Item = to_dynamo(dict(item)))
    if entry.key != old_key:
        table.delete_item(Key = {'client': client, 'entry_key': old_key})
    message = f'Entry {old_key} of {client} corrected by {user} as {entry.key}.'
    logger.info(message)
    return to_entry_response(item)


def delete_entry(
    dynamodb_resource: ServiceResource,
    client: str,
    target: tuple[Periodicity, str, str]
) -> EntrySchema:
    '''
        Removes one amount.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            client (str): The owner.
            target (tuple[Periodicity, str, str]): Periodicity, date and account.

        Returns:
            EntrySchema: The amount that was removed.

        Raises:
            ResourceNotFoundError: ENTRY_NOT_FOUND.
    '''
    key = entry_key(*target)
    stored = _stored_entry(dynamodb_resource, client, key)
    dynamodb_resource.Table(ENTRIES_TABLE).delete_item(Key = {'client': client, 'entry_key': key})
    message = f'Entry {key} of {client} removed.'
    logger.info(message)
    return to_entry_response(stored)


def delete_period(
    dynamodb_resource: ServiceResource,
    client: str,
    period: tuple[Periodicity, str]
) -> PeriodDeleteResultSchema:
    '''
        Empties a period: every amount of that periodicity whose date starts
        with the given one. "DAILY 2026-03" removes every day of March, which
        is what has to happen before March is loaded as a month.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            client (str): The owner.
            period (tuple[Periodicity, str]): The periodicity and a date prefix.

        Returns:
            PeriodDeleteResultSchema: How many amounts were removed.
    '''
    periodicity, day = period
    items = _query_prefix(dynamodb_resource, client, f'{periodicity.value}#{day}')
    with dynamodb_resource.Table(ENTRIES_TABLE).batch_writer() as batch:
        for item in items:
            batch.delete_item(Key = {'client': client, 'entry_key': item['entry_key']})
    message = f'Period {periodicity.value} {day} of {client}: {len(items)} amount(s) removed.'
    logger.info(message)
    return PeriodDeleteResultSchema(periodicity = periodicity, date = day, deleted = len(items))
