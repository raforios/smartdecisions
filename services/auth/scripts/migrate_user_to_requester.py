'''
    One-off migration: AUTH users with role 'USER' are remapped to 'REQUESTER'.

    Background:
        The Role enum was reshaped to (ADMIN, WAREHOUSE_MANAGER, REQUESTER).
        Existing DynamoDB items still carry the legacy 'USER' value, which is
        no longer part of the enum. This script normalizes them so the new
        JWT payload (which now includes 'role') stays consistent with the
        downstream services that validate roles.

    Usage:
        # Inspect what would change without writing
        python migrate_user_to_requester.py --dry-run

        # Apply the update
        python migrate_user_to_requester.py --apply

    Environment:
        TABLE_NAME : Name of the AUTH DynamoDB users table.
        AWS_PROFILE: Optional. The AWS profile to use (defaults to the
                     default credential chain).
        AWS_REGION : Optional. Defaults to us-east-1.
'''
import argparse
import os
import sys
from typing import Any, Dict, List

import boto3
from botocore.exceptions import ClientError

LEGACY_ROLE = 'USER'
TARGET_ROLE = 'REQUESTER'


def _build_client() -> Any:
    '''
        Returns a DynamoDB resource using the optional AWS profile/region.
    '''
    profile = os.environ.get('AWS_PROFILE')
    region = os.environ.get('AWS_REGION', 'us-east-1')

    session_kwargs = {'region_name': region}
    if profile:
        session_kwargs['profile_name'] = profile

    session = boto3.session.Session(**session_kwargs)
    return session.resource('dynamodb')


def _scan_users(table) -> List[Dict[str, Any]]:
    '''
        Full scan of the users table. AUTH tables are small (admin users),
        so a single scan is acceptable for a one-off migration.
    '''
    items: List[Dict[str, Any]] = []
    response = table.scan()
    items.extend(response.get('Items', []))

    while 'LastEvaluatedKey' in response:
        response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        items.extend(response.get('Items', []))

    return items


def _update_role(table, email: str) -> None:
    '''
        Updates a single user item, setting role = TARGET_ROLE.

        Uses ExpressionAttributeNames because 'role' is not reserved in
        DynamoDB, but the alias keeps the script safe against future
        reserved-word collisions.
    '''
    table.update_item(
        Key={'email': email},
        UpdateExpression='SET #role_alias = :new_role',
        ExpressionAttributeNames={'#role_alias': 'role'},
        ExpressionAttributeValues={':new_role': TARGET_ROLE},
    )


def main() -> int:
    '''
        Entry point. Returns process exit code.
    '''
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--dry-run', action='store_true',
                       help='Show users that would be updated without writing.')
    group.add_argument('--apply', action='store_true',
                       help='Apply the update to DynamoDB.')
    args = parser.parse_args()

    table_name = os.environ.get('TABLE_NAME')
    if not table_name:
        print('ERROR: TABLE_NAME env var is required.', file=sys.stderr)
        return 2

    dynamodb = _build_client()
    table = dynamodb.Table(table_name)

    try:
        items = _scan_users(table)
    except ClientError as exc:
        print(f'ERROR scanning table {table_name}: {exc}', file=sys.stderr)
        return 3

    candidates = [item for item in items if item.get('role') == LEGACY_ROLE]

    print(f'Total users scanned : {len(items)}')
    print(f'Candidates to update: {len(candidates)} (role == \'{LEGACY_ROLE}\')')
    for item in candidates:
        print(f'  - {item.get("email")}')

    if args.dry_run:
        print('\nDry-run: no changes applied.')
        return 0

    updated = 0
    for item in candidates:
        email = item.get('email')
        if not email:
            print(f'WARN: skipping item without email: {item}')
            continue
        try:
            _update_role(table, email)
            updated += 1
        except ClientError as exc:
            print(f'ERROR updating {email}: {exc}', file=sys.stderr)

    print(f'\nDone. Updated {updated}/{len(candidates)} users.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
