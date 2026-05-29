'''
    One-off helper: set a single user's role to ADMIN | WAREHOUSE_MANAGER |
    REQUESTER directly in the AUTH DynamoDB table.

    Designed for development convenience (seeding test users). For
    production use the PATCH /v1/users/{email} endpoint with a valid JWT.

    Usage:
        TABLE_NAME=auth-users AWS_PROFILE=deploy_ml AWS_REGION=us-east-1 \
            python set_user_role.py --email raforios@gmail.com --role ADMIN

    Environment:
        TABLE_NAME : AUTH DynamoDB users table.
        AWS_PROFILE: Optional AWS profile (defaults to default chain).
        AWS_REGION : Optional. Defaults to us-east-1.
'''
import argparse
import os
import sys
from typing import Any

import boto3
from botocore.exceptions import ClientError

ALLOWED_ROLES = {'ADMIN', 'WAREHOUSE_MANAGER', 'REQUESTER'}


def _build_client() -> Any:
    profile = os.environ.get('AWS_PROFILE')
    region = os.environ.get('AWS_REGION', 'us-east-1')
    session_kwargs = {'region_name': region}
    if profile:
        session_kwargs['profile_name'] = profile
    return boto3.session.Session(**session_kwargs).resource('dynamodb')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--email', required=True, help='User email (PK).')
    parser.add_argument('--role', required=True, choices=sorted(ALLOWED_ROLES),
                        help='Role to assign.')
    args = parser.parse_args()

    table_name = os.environ.get('TABLE_NAME')
    if not table_name:
        print('ERROR: TABLE_NAME env var is required.', file=sys.stderr)
        return 2

    table = _build_client().Table(table_name)

    try:
        # Confirm the user exists first so the script does not silently
        # create a phantom item with only the role attribute.
        existing = table.get_item(Key={'email': args.email}).get('Item')
        if not existing:
            print(f'ERROR: user {args.email} not found in {table_name}.',
                  file=sys.stderr)
            return 4

        previous = existing.get('role')
        table.update_item(
            Key={'email': args.email},
            UpdateExpression='SET #role_alias = :new_role',
            ExpressionAttributeNames={'#role_alias': 'role'},
            ExpressionAttributeValues={':new_role': args.role},
        )
    except ClientError as exc:
        print(f'ERROR updating {args.email}: {exc}', file=sys.stderr)
        return 3

    print(f'OK: {args.email}: {previous} -> {args.role}')
    print('Remember the user must log out / log in again so the JWT '
          'carries the new role claim.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
