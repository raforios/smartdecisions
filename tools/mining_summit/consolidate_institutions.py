'''
    Consolidates the accreditation institutions: for each MERGE row of the review
    CSV (data/mapa_fusion_instituciones.csv), reassigns every participant whose
    institution_id == new_id to the official slug, then deletes the duplicate
    catalog entry. KEEP rows are left untouched.

    Edit the CSV first (columns 'accion' MERGE/KEEP and 'oficial_slug') to override
    any decision, then run:
      python consolidate_institutions.py            # DRY-RUN
      python consolidate_institutions.py --commit     # applies changes
'''
import csv
import sys
from collections import Counter

import boto3

REGION = 'us-east-1'
PARTICIPANTS_TABLE = 'mining_summit_participants'
INSTITUTIONS_TABLE = 'mining_summit_institutions'
MAP_CSV = '/Users/rafael/Work/projects/back/SmartBear/data/mapa_fusion_instituciones.csv'


def scan_all(table):
    items, kw = [], {}
    while True:
        r = table.scan(**kw)
        items.extend(r.get('Items', []))
        if 'LastEvaluatedKey' not in r:
            return items
        kw['ExclusiveStartKey'] = r['LastEvaluatedKey']


def load_merges():
    merges = {}
    with open(MAP_CSV, encoding='utf-8') as handle:
        for row in csv.DictReader(handle):
            if row['accion'].strip().upper() == 'MERGE' and row['oficial_slug'].strip():
                merges[row['new_id']] = row['oficial_slug'].strip()
    return merges


def main():
    commit = '--commit' in sys.argv[1:]
    dynamodb = boto3.resource('dynamodb', region_name=REGION)
    merges = load_merges()

    all_ids = {i['id'] for i in scan_all(dynamodb.Table(INSTITUTIONS_TABLE))}
    # A target must exist in the catalog and must not itself be a merge source
    # (no chained merges).
    bad = [t for t in set(merges.values()) if t not in all_ids or t in merges]
    if bad:
        print(f'⚠ destinos inválidos (no existen o son a su vez origen): {bad}')
        return

    participants = scan_all(dynamodb.Table(PARTICIPANTS_TABLE))
    reassign = [p for p in participants if (p.get('institution_id') or '') in merges]
    moved = Counter(p['institution_id'] for p in reassign)

    print(f'== {"COMMIT" if commit else "DRY-RUN"} ==')
    print(f'Entradas a fusionar (borrar): {len(merges)}')
    print(f'Participantes a reasignar   : {len(reassign)}')
    for new_id, slug in sorted(merges.items(), key=lambda kv: -moved.get(kv[0], 0)):
        print(f'  {moved.get(new_id, 0):>3}  {new_id[:40]:42} -> {slug}')

    if not commit:
        print('\nDRY-RUN: nada cambiado. Revisa/edita el CSV y re-ejecuta con --commit.')
        return

    part_table = dynamodb.Table(PARTICIPANTS_TABLE)
    for person in reassign:
        part_table.update_item(
            Key={'ci': person['ci']},
            UpdateExpression='SET institution_id = :s',
            ExpressionAttributeValues={':s': merges[person['institution_id']]},
        )
    inst_table = dynamodb.Table(INSTITUTIONS_TABLE)
    for new_id in merges:
        inst_table.delete_item(Key={'id': new_id})

    print(f'\nReasignados {len(reassign)} participantes; borradas {len(merges)} instituciones duplicadas.')


if __name__ == '__main__':
    main()
