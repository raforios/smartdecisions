'''
    Seed tool: populates the DynamoDB table `mining_summit_aulas` with the 17
    fixed campus rooms, each allocated to a thematic axis according to the summit
    rules (AULAS_SEED + MESA_ALLOCATION). Idempotent: it skips aula codes that
    already exist, so it can be re-run safely.

    Usage (run from the app root):
        python tools/mining_summit/seed_aulas.py

    Config via env vars:
        DYNAMODB_TABLE_NAME_AULAS         (default: mining_summit_aulas)
        AWS_REGION / AWS_DEFAULT_REGION   (default: us-east-1)
        AWS_PROFILE                       (optional, standard boto3 profile)
        DYNAMODB_ENDPOINT_URL             (optional, for local DynamoDB)
'''
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import boto3

APP_ROOT = Path(__file__).resolve().parents[2]
SERVICE_ROOT = APP_ROOT / 'services' / 'mining_summit'
sys.path.insert(0, str(SERVICE_ROOT))

# The service package is added to sys.path above so the seating rules stay
# single-sourced; pylint cannot follow that dynamic path.
# pylint: disable=wrong-import-position,import-error
from services.summit_rules import AULAS_SEED, MESA_ALLOCATION

AULAS_TABLE = os.getenv('DYNAMODB_TABLE_NAME_AULAS', 'mining_summit_aulas')
REGION = os.getenv('AWS_REGION') or os.getenv('AWS_DEFAULT_REGION') or 'us-east-1'
ENDPOINT_URL = os.getenv('DYNAMODB_ENDPOINT_URL')


def build_allocated_aulas() -> List[Dict[str, Any]]:
    '''
        Allocates the ordered AULAS_SEED rooms to thematic axes following the
        per-axis counts in MESA_ALLOCATION, stamping each aula with its axis.

        Returns:
            List[Dict[str, Any]]: Aula items ready to persist, each with code,
                block, location, capacity and axis.

        Raises:
            ValueError: If MESA_ALLOCATION does not sum to the number of aulas.
    '''
    total_allocation = sum(MESA_ALLOCATION.values())
    if total_allocation != len(AULAS_SEED):
        error_msg = (f'MESA_ALLOCATION sums to {total_allocation} but there are '
                     f'{len(AULAS_SEED)} aulas; they must match.')
        raise ValueError(error_msg)

    allocated: List[Dict[str, Any]] = []
    cursor = 0
    for axis, count in MESA_ALLOCATION.items():
        for aula in AULAS_SEED[cursor:cursor + count]:
            allocated.append({**aula, 'axis': axis.value})
        cursor += count
    return allocated


def get_resource():
    '''Builds the DynamoDB resource honoring the region/endpoint env vars.'''
    return boto3.resource('dynamodb', region_name = REGION, endpoint_url = ENDPOINT_URL)


def seed_aulas() -> None:
    '''
        Persists the allocated aulas into the aulas table, skipping any aula
        code that already exists so re-runs are safe.
    '''
    table = get_resource().Table(AULAS_TABLE)
    created = 0
    skipped = 0
    for aula in build_allocated_aulas():
        if table.get_item(Key = {'code': aula['code']}).get('Item'):
            skipped += 1
            continue
        table.put_item(Item = aula)
        created += 1
        print(f'  + {aula["code"]:>4}  axis={aula["axis"]}')
    print(f'Aulas seeded into "{AULAS_TABLE}": {created} created, {skipped} skipped.')


def main() -> None:
    '''CLI entry point: seeds the aulas table.'''
    seed_aulas()


if __name__ == '__main__':
    main()
