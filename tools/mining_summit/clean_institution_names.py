'''
    Cleans the institutions catalog: removes the trailing "(SIGLA)" from the NAME
    field and stores the acronym in the abbreviation field instead. Example:
    "Corporación Minera de Bolivia (COMIBOL)" -> name="Corporación Minera de
    Bolivia", abbreviation="COMIBOL".

    Usage:
      python clean_institution_names.py            # DRY-RUN
      python clean_institution_names.py --commit
'''
import re
import sys

import boto3

REGION = 'us-east-1'
INSTITUTIONS_TABLE = 'mining_summit_institutions'
PAREN = re.compile(r'\s*\(([^)]+)\)\s*$')


def scan_all(table):
    items, kw = [], {}
    while True:
        r = table.scan(**kw)
        items.extend(r.get('Items', []))
        if 'LastEvaluatedKey' not in r:
            return items
        kw['ExclusiveStartKey'] = r['LastEvaluatedKey']


def main():
    commit = '--commit' in sys.argv[1:]
    dynamodb = boto3.resource('dynamodb', region_name=REGION)
    table = dynamodb.Table(INSTITUTIONS_TABLE)

    changes = []
    for item in scan_all(table):
        name = (item.get('name') or '').strip()
        match = PAREN.search(name)
        if not match:
            continue
        acronym = match.group(1).strip()
        clean_name = PAREN.sub('', name).strip()
        abbr = (item.get('abbreviation') or '').strip() or acronym
        changes.append((item['id'], name, clean_name, abbr))

    print(f'== {"COMMIT" if commit else "DRY-RUN"} ==  a limpiar: {len(changes)}')
    for _id, old, new, abbr in changes[:12]:
        print(f'  {old!r} -> name={new!r}  sigla={abbr!r}')
    if len(changes) > 12:
        print(f'  ... (+{len(changes) - 12} más)')

    if not commit:
        print('\nDRY-RUN: nada cambiado.')
        return

    for inst_id, _old, clean_name, abbr in changes:
        table.update_item(
            Key={'id': inst_id},
            UpdateExpression='SET #n = :n, abbreviation = :a',
            ExpressionAttributeNames={'#n': 'name'},
            ExpressionAttributeValues={':n': clean_name, ':a': abbr},
        )
    print(f'\nActualizadas {len(changes)} instituciones.')


if __name__ == '__main__':
    main()
