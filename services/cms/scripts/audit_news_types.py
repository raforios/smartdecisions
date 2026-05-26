'''
    One-off audit: list news items whose `type` falls outside the
    canonical Literal set (`press | communique | photo | article`).

    The schema validation enforces this on every new write, but existing
    items in DynamoDB (manual seeds, imports, legacy rows) bypass it. Run
    this before tightening readers if the table predates the Literal.

    Usage:
        cd services/cms
        python scripts/audit_news_types.py
        python scripts/audit_news_types.py --table other_news_table
        python scripts/audit_news_types.py --remap banner=photo
        python scripts/audit_news_types.py --remap banner=photo \\
            --remap blog=article --dry-run

    Exits 0 when every row is valid after the operation, 1 otherwise.
'''
import argparse
import os
import sys
from datetime import datetime
from typing import Dict, Iterable, Optional
from zoneinfo import ZoneInfo

import boto3
from dotenv import dotenv_values


VALID_TYPES = {'press', 'communique', 'photo', 'article'}
DEFAULT_TABLE = 't_cms_news'
DEFAULT_TIMEZONE = 'America/La_Paz'


def _load_env() -> dict:
    '''
        Loads the same env layering used by the service: process env wins
        over .env. Only the DynamoDB-related keys are needed here.
    '''
    file_env = dotenv_values('.env') if os.path.exists('.env') else {}
    region = (os.environ.get('DYNAMODB_REGION')
              or file_env.get('DYNAMODB_REGION') or 'us-east-1')
    endpoint = (os.environ.get('DYNAMODB_ENDPOINT_URL')
                or file_env.get('DYNAMODB_ENDPOINT_URL') or '')
    timezone = (os.environ.get('TARGET_TIMEZONE')
                or file_env.get('TARGET_TIMEZONE') or DEFAULT_TIMEZONE)
    return {'region': region, 'endpoint': endpoint, 'timezone': timezone}


def _parse_remap(raw_pairs: list, parser: argparse.ArgumentParser
                 ) -> Dict[str, str]:
    '''
        Validates each "source=target" pair against the canonical set and
        returns a dict mapping invalid source → valid target.
    '''
    remap: Dict[str, str] = {}
    for raw in raw_pairs:
        source, _, target = raw.partition('=')
        if not source or not target:
            parser.error(f'Invalid --remap value "{raw}". Expected source=target.')
        if target not in VALID_TYPES:
            parser.error(
                f'--remap target "{target}" is not canonical. '
                f'Allowed: {sorted(VALID_TYPES)}.'
            )
        if source in VALID_TYPES:
            parser.error(
                f'--remap source "{source}" is already canonical; '
                'nothing to remap.'
            )
        remap[source] = target
    return remap


def _scan_all(table) -> Iterable[dict]:
    '''
        Yields every item in the table, following LastEvaluatedKey.
    '''
    scan_kwargs: dict = {}
    while True:
        response = table.scan(**scan_kwargs)
        for item in response.get('Items', []):
            yield item
        last_key = response.get('LastEvaluatedKey')
        if not last_key:
            return
        scan_kwargs['ExclusiveStartKey'] = last_key


def _apply_remap(table, item_id: str, new_type: str, now_iso: str) -> None:
    '''
        Updates a single item's `type` and refreshes its `updated_at`.
        `type` is a DynamoDB reserved word, so we alias it via
        ExpressionAttributeNames.
    '''
    table.update_item(
        Key = {'id': item_id},
        UpdateExpression = 'SET #t = :t, updated_at = :u',
        ExpressionAttributeNames = {'#t': 'type'},
        ExpressionAttributeValues = {':t': new_type, ':u': now_iso},
    )


def _print_table(rows: list) -> None:
    '''
        Pretty-prints the invalid items in a fixed-width table.
    '''
    print(f'{"id":<34} {"type":<20} {"lang":<5} title')
    print('-' * 100)
    for item in rows:
        print(f'{str(item.get("id", "?")):<34} '
              f'{str(item.get("type", "<missing>")):<20} '
              f'{str(item.get("lang", "?")):<5} '
              f'{str(item.get("title", ""))[:60]}')


def main() -> int:
    '''
        Entry point. Returns the process exit code.
    '''
    parser = argparse.ArgumentParser(description = __doc__.strip().splitlines()[0])
    parser.add_argument('--table', default = DEFAULT_TABLE,
                        help = f'DynamoDB table name (default: {DEFAULT_TABLE}).')
    parser.add_argument('--remap', action = 'append', default = [],
                        metavar = 'SOURCE=TARGET',
                        help = ('Rewrite items whose `type` equals SOURCE to '
                                'TARGET (must be canonical). Repeat for '
                                'multiple mappings.'))
    parser.add_argument('--dry-run', action = 'store_true',
                        help = 'With --remap, only print what would change.')
    args = parser.parse_args()

    remap = _parse_remap(args.remap, parser)

    env = _load_env()
    boto_kwargs = {'region_name': env['region']}
    if env['endpoint']:
        boto_kwargs['endpoint_url'] = env['endpoint']

    print(f'Scanning {args.table} on '
          f'{env["endpoint"] or env["region"] + " (AWS)"}...\n')

    dynamodb = boto3.resource('dynamodb', **boto_kwargs)
    table = dynamodb.Table(args.table)

    total = 0
    invalid: list = []
    for item in _scan_all(table):
        total += 1
        if item.get('type') not in VALID_TYPES:
            invalid.append(item)

    if not invalid:
        print(f'OK — {total} item(s) scanned, every `type` is valid.')
        return 0

    print(f'FOUND {len(invalid)} item(s) with invalid `type` '
          f'(out of {total} scanned):\n')
    _print_table(invalid)

    if not remap:
        print(f'\nCanonical types: {sorted(VALID_TYPES)}')
        print('Re-run with --remap source=target (repeatable) to fix them, '
              'or delete the rows manually.')
        return 1

    # Apply (or simulate) the remap.
    now_iso = datetime.now(ZoneInfo(env['timezone'])).isoformat()
    targeted = [r for r in invalid if r.get('type') in remap]
    untouched = [r for r in invalid if r.get('type') not in remap]

    label = 'WOULD REWRITE' if args.dry_run else 'REWRITING'
    print(f'\n{label} {len(targeted)} item(s) using map {remap}:')
    for item in targeted:
        new_type = remap[item['type']]
        print(f'  {item["id"]}: {item["type"]} → {new_type}')
        if not args.dry_run:
            _apply_remap(table, item['id'], new_type, now_iso)

    if args.dry_run:
        print('\nDry-run only — no writes were issued.')
        # Exit non-zero so the dry-run blocks CI just like the audit-only path.
        return 1

    if untouched:
        print(f'\n{len(untouched)} item(s) still invalid '
              '(no --remap rule matched):')
        _print_table(untouched)
        return 1

    print(f'\nDone — every invalid item was remapped to a canonical type.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
