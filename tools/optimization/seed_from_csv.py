'''
    Seeds the t_optimization_routes table from a CSV file.

    Expected CSV columns:
        route_id, day, client_id, latitude, longitude, client (optional)

    Each row is materialized as a DynamoDB item with the composite partition
    key `route_day_key = "{route_id}#{day}"` and sort key `client_id`. Uses
    `Table.batch_writer` to amortize the put_item calls.

    Local DynamoDB:
        python scripts/seed_from_csv.py \\
            --csv scripts/sample_routes.csv \\
            --endpoint-url http://localhost:3100

    AWS DynamoDB (uses default credentials chain):
        python scripts/seed_from_csv.py --csv path/to/routes.csv
'''
import argparse
import csv
import os
from decimal import Decimal
from pathlib import Path
from typing import Iterable

import boto3
from boto3.resources.base import ServiceResource
from dotenv import dotenv_values


DEFAULT_TABLE = 't_optimization_routes'
REQUIRED_COLUMNS = {'route_id', 'day', 'client_id', 'latitude', 'longitude'}


def _resolve_table_name() -> str:
    '''
        Picks the table name from env / .env / fallback default.
    '''
    env_value = os.environ.get('DYNAMODB_TABLE_NAME_OPTIMIZATION_ROUTES')
    if env_value:
        return env_value
    service_root = Path(__file__).resolve().parent.parent
    local_env = dotenv_values(service_root / '.env')
    return local_env.get('DYNAMODB_TABLE_NAME_OPTIMIZATION_ROUTES') or DEFAULT_TABLE


def _build_dynamodb_resource(endpoint_url: str | None, region: str) -> ServiceResource:
    '''
        Returns a DynamoDB resource pointing at local or AWS.
    '''
    if endpoint_url:
        return boto3.resource(
            'dynamodb',
            endpoint_url = endpoint_url,
            region_name = region,
            aws_access_key_id = 'local',
            aws_secret_access_key = 'local'
        )
    return boto3.resource('dynamodb', region_name = region)


def _row_to_item(row: dict) -> dict:
    '''
        Converts a CSV row into the t_optimization_routes item shape.

        Latitude/longitude are stored as Decimal because DynamoDB rejects
        Python floats; the algorithm casts them back to float at read time.
    '''
    route_id = int(row['route_id'])
    day = int(row['day'])
    item = {
        'route_day_key': f'{route_id}#{day}',
        'client_id': int(row['client_id']),
        'route_id': route_id,
        'day': day,
        'latitude': Decimal(str(row['latitude'])),
        'longitude': Decimal(str(row['longitude']))
    }
    client_name = (row.get('client') or '').strip()
    if client_name:
        item['client'] = client_name
    return item


def _iter_rows(csv_path: Path) -> Iterable[dict]:
    '''
        Yields rows from the CSV after enforcing the required columns.
    '''
    with csv_path.open(newline = '') as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(
                f'CSV is missing required columns: {sorted(missing)}. '
                f'Expected at least {sorted(REQUIRED_COLUMNS)}.'
            )
        for row in reader:
            yield row


def seed(csv_path: Path, table_name: str, dynamodb_resource: ServiceResource) -> int:
    '''
        Loads the CSV and bulk-writes its rows into the target table.

        Returns:
            int: Number of items written.
    '''
    table = dynamodb_resource.Table(table_name)
    count = 0
    with table.batch_writer() as batch:
        for row in _iter_rows(csv_path):
            batch.put_item(Item = _row_to_item(row))
            count += 1
    return count


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description = 'Seed t_optimization_routes from a CSV file.'
    )
    parser.add_argument('--csv', type = Path, required = True, help = 'Source CSV path.')
    parser.add_argument(
        '--table',
        type = str,
        default = None,
        help = 'Override table name (defaults to DYNAMODB_TABLE_NAME_OPTIMIZATION_ROUTES).'
    )
    parser.add_argument(
        '--endpoint-url',
        type = str,
        default = None,
        help = 'DynamoDB endpoint URL (e.g. http://localhost:3100 for DynamoDB Local).'
    )
    parser.add_argument(
        '--region',
        type = str,
        default = os.environ.get('AWS_REGION', 'us-east-1'),
        help = 'AWS region (default: us-east-1).'
    )
    args = parser.parse_args()

    table_name = args.table or _resolve_table_name()
    resource = _build_dynamodb_resource(args.endpoint_url, args.region)

    written = seed(args.csv, table_name, resource)
    target = args.endpoint_url or f'AWS DynamoDB ({args.region})'
    print(f'Seeded {written} items into "{table_name}" at {target}.')
