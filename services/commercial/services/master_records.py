'''
    The rule every master of the account follows —clients, products—, stated
    once (`.claude/rules/datos.md`): a record that is not there is CREATED; a
    record that is already there is NOT rewritten, only its empty fields are
    filled in. A reload cannot undo a correction; overwriting is a separate,
    explicit act of each master.
'''
from collections import Counter
from dataclasses import dataclass
from typing import Any

import pandas as pd
from boto3.resources.base import ServiceResource

from core.crud import find_item_by_key
from core.logger_config import custom_logger as logger
from core.utils import get_current_time_gmt
from services.commercial_utils import from_dynamo, to_dynamo

# A coordinate of exactly zero is the absence of a reading, not the Gulf of
# Guinea. Stated here because every master agrees on it.
NO_COORDINATE = 0.0
_COORDINATES = ('latitude', 'longitude')


@dataclass(frozen = True)
class MasterTable:
    '''
        Where a master lives: its table and the attribute that identifies a
        record inside the owner's partition.
    '''
    name: str
    key: str


@dataclass(frozen = True)
class MasterLoad:
    '''
        What a load did: the three counts are separate on purpose, because a
        load that only completed empty fields did not change anybody's data.
    '''
    created: int
    completed: int
    unchanged: int


def is_empty(value: Any) -> bool:
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
    return isinstance(value, str) and not value.strip()


def clean_attributes(attributes: dict[str, Any]) -> dict[str, Any]:
    '''
        Drops the attributes that carry no information, so an absent field
        never travels as a value that overwrites a known one. Coordinates at
        exactly zero are dropped with them.

        Args:
            attributes (dict[str, Any]): Raw attributes of one record.

        Returns:
            dict[str, Any]: Only the attributes worth storing.
    '''
    cleaned: dict[str, Any] = {}
    for key, value in attributes.items():
        if is_empty(value):
            continue
        if key in _COORDINATES and float(value) == NO_COORDINATE:
            continue
        cleaned[key] = value.strip() if isinstance(value, str) else value
    return cleaned


def feed_master(
    dynamodb_resource: ServiceResource,
    table: MasterTable,
    owner_email: str,
    records: dict[str, dict[str, Any]],
    source: str
) -> MasterLoad:
    '''
        Creates the records that are missing and completes the empty fields of
        the ones already there; never overwrites a stored value.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            table (MasterTable): The master.
            owner_email (str): Authenticated account that owns the data.
            records (dict[str, dict[str, Any]]): Attributes per record key.
            source (str): The door they came through.

        Returns:
            MasterLoad: Created, completed and unchanged counts.
    '''
    target = dynamodb_resource.Table(table.name)
    now = get_current_time_gmt().isoformat()
    counts: Counter[str] = Counter()
    for record_key, raw in records.items():
        attributes = clean_attributes(raw)
        stored = find_item_by_key(dynamodb_resource = dynamodb_resource, table_name = table.name,
                                  key = {'owner_email': owner_email, table.key: record_key})
        if stored is None:
            target.put_item(Item = to_dynamo({
                'owner_email': owner_email, table.key: record_key, 'source': source,
                'created_at': now, 'updated_at': now, **attributes
            }))
            counts['created'] += 1
            continue
        missing = {key: value for key, value in attributes.items()
                   if is_empty(from_dynamo(stored.get(key)))}
        if not missing:
            counts['unchanged'] += 1
            continue
        stored.update(to_dynamo(missing))
        stored['updated_at'] = now
        target.put_item(Item = stored)
        counts['completed'] += 1
    load = MasterLoad(created = counts['created'], completed = counts['completed'],
                      unchanged = counts['unchanged'])
    message = f'{table.name} of {owner_email} fed from {source}: {load}.'
    logger.info(message)
    return load
