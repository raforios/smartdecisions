'''
    One-off migration: splits the legacy `mining_summit_participants` items
    (which mixed person master data with the event seat) into the new two-table
    model:

        mining_summit_participants  -> person master data only
        mining_summit_registration  -> event seat + lifecycle + replacement chain

    For every legacy item it writes/updates the person record (dropping the seat
    and legacy fields such as company/institution_name/status) and, when the item
    carried a seat (mesa_code or axis), writes the matching registration row.
    Idempotent: re-running it overwrites the derived rows with the same content.

    Usage (run from the app root):
        python tools/mining_summit/migrate_split_registration.py [--dry-run]

    Config via env vars:
        DYNAMODB_TABLE_NAME_PARTICIPANTS  (default: mining_summit_participants)
        DYNAMODB_TABLE_NAME_REGISTRATION  (default: mining_summit_registration)
        AWS_REGION / AWS_DEFAULT_REGION   (default: us-east-1)
        AWS_PROFILE                       (optional, standard boto3 profile)
        DYNAMODB_ENDPOINT_URL             (optional, for local DynamoDB)
'''
import argparse
import os
from typing import Any, Dict, List, Optional

import boto3

PARTICIPANTS_TABLE = os.getenv('DYNAMODB_TABLE_NAME_PARTICIPANTS', 'mining_summit_participants')
REGISTRATION_TABLE = os.getenv('DYNAMODB_TABLE_NAME_REGISTRATION', 'mining_summit_registration')
REGION = os.getenv('AWS_REGION') or os.getenv('AWS_DEFAULT_REGION') or 'us-east-1'
ENDPOINT_URL = os.getenv('DYNAMODB_ENDPOINT_URL')

# Fields that belong to the person master record (everything else is dropped
# from participants; the seat fields move to the registration table).
_PERSON_FIELDS = (
    'ci', 'first_name', 'last_name', 'email', 'phone', 'department',
    'institution_id', 'role'
)
# Registration fields lifted out of the legacy item.
_REGISTRATION_FIELDS = (
    'assignment_type', 'axis', 'axis_label', 'mesa_code', 'observation',
    'replaces_ci', 'replaced_by_ci', 'status'
)


def _scan(table) -> List[Dict[str, Any]]:
    '''Returns every item of a DynamoDB table, following pagination.'''
    response = table.scan()
    items = response.get('Items', [])
    while 'LastEvaluatedKey' in response:
        response = table.scan(ExclusiveStartKey = response['LastEvaluatedKey'])
        items.extend(response.get('Items', []))
    return items


def _build_person(legacy: Dict[str, Any]) -> Dict[str, Any]:
    '''
        Extracts the person master record from a legacy item. `created_at` is
        backfilled from the legacy `registered_at`/`registered_date` when present.
    '''
    person = {field: legacy[field] for field in _PERSON_FIELDS if legacy.get(field) is not None}
    person['created_at'] = (
        legacy.get('registered_at')
        or legacy.get('registered_date')
        or legacy.get('created_at')
    )
    return person


def _build_registration(legacy: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    '''
        Extracts the registration/seat record from a legacy item, or None when
        the legacy item had no seat (never registered).
    '''
    if not (legacy.get('mesa_code') or legacy.get('axis')):
        return None
    registration = {
        field: legacy[field]
        for field in _REGISTRATION_FIELDS if legacy.get(field) is not None
    }
    registration['ci'] = legacy['ci']
    registration['registered_at'] = legacy.get('registered_at') or legacy.get('registered_date')
    registration.setdefault('status', 'ACTIVE')
    return registration


def migrate(dry_run: bool) -> None:
    '''
        Runs the split migration over the participants table, writing person and
        registration rows. With dry_run=True it only reports what it would write.
    '''
    session = boto3.Session()
    dynamodb = session.resource('dynamodb', region_name = REGION, endpoint_url = ENDPOINT_URL)
    participants = dynamodb.Table(PARTICIPANTS_TABLE)
    registration = dynamodb.Table(REGISTRATION_TABLE)

    legacy_items = _scan(participants)
    persons = 0
    registrations = 0
    for legacy in legacy_items:
        person = _build_person(legacy)
        reg = _build_registration(legacy)
        seat = reg.get('mesa_code') if reg else '—'
        print(f'  ci={legacy["ci"]:>12}  role={person.get("role") or "—":<12}  seat={seat}')
        if dry_run:
            persons += 1
            registrations += 1 if reg else 0
            continue
        participants.put_item(Item = person)
        persons += 1
        if reg:
            registration.put_item(Item = reg)
            registrations += 1

    verb = 'Would write' if dry_run else 'Wrote'
    print(f'{verb} {persons} person rows and {registrations} registration rows '
          f'from {len(legacy_items)} legacy items.')


def main() -> None:
    '''CLI entry point: parses flags and runs the migration.'''
    parser = argparse.ArgumentParser(description = 'Split participants into person + registration.')
    parser.add_argument('--dry-run', action = 'store_true',
                        help = 'Report the split without writing anything.')
    args = parser.parse_args()
    migrate(dry_run = args.dry_run)


if __name__ == '__main__':
    main()
