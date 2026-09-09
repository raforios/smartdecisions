'''
    Re-packs the aula seats with a SEQUENTIAL fill: within each eje, aula 1 is
    filled to capacity before using aula 2, etc., so people concentrate in fewer
    aulas when the quotas are not full. Pivot aulas (no axis, e.g. A16/L11) are
    excluded. Active registrations whose participant is no longer a PARTICIPANTE
    are removed (they hold no aula).

    Usage:
      python redistribute_aulas.py            # DRY-RUN (shows the resulting map)
      python redistribute_aulas.py --commit
'''
import sys
from collections import defaultdict

import boto3

REGION = 'us-east-1'
PARTICIPANTS_TABLE = 'mining_summit_participants'
REGISTRATION_TABLE = 'mining_summit_registration'
AULAS_TABLE = 'mining_summit_aulas'


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

    # Real aulas per axis (pivots have axis=None), ordered by code -> sequential fill.
    aulas_by_axis = defaultdict(list)
    capacity = {}
    for a in scan_all(dynamodb.Table(AULAS_TABLE)):
        if a.get('axis'):
            aulas_by_axis[a['axis']].append(a['code'])
            capacity[a['code']] = int(a['capacity'])
    for axis in aulas_by_axis:
        aulas_by_axis[axis].sort()

    roles = {p['ci']: p.get('role') for p in scan_all(dynamodb.Table(PARTICIPANTS_TABLE))}
    regs = scan_all(dynamodb.Table(REGISTRATION_TABLE))

    orphans = [r for r in regs if roles.get(r['ci']) != 'PARTICIPANTE'
               or r.get('status', 'ACTIVE') != 'ACTIVE']
    seated = [r for r in regs if r not in orphans]

    # group seated by axis, ordered deterministically
    by_axis = defaultdict(list)
    for r in seated:
        by_axis[r.get('axis')].append(r)
    for axis in by_axis:
        by_axis[axis].sort(key=lambda r: r['ci'])

    assignment = {}          # ci -> mesa_code
    fill = defaultdict(int)  # mesa_code -> count
    overflow = []
    for axis, people in by_axis.items():
        codes = aulas_by_axis.get(axis, [])
        idx = 0
        for r in people:
            while idx < len(codes) and fill[codes[idx]] >= capacity[codes[idx]]:
                idx += 1
            if idx >= len(codes):
                overflow.append((axis, r['ci']))
                assignment[r['ci']] = codes[-1] if codes else None
                if codes:
                    fill[codes[-1]] += 1
                continue
            assignment[r['ci']] = codes[idx]
            fill[codes[idx]] += 1

    print(f'== {"COMMIT" if commit else "DRY-RUN"} ==')
    print(f'Asientos activos (PARTICIPANTE): {len(seated)}  | huérfanos a borrar: {len(orphans)}')
    print('Distribución resultante (llenado secuencial):')
    for axis in sorted(aulas_by_axis):
        used = [(c, fill[c]) for c in aulas_by_axis[axis]]
        print(f'  {axis:22} {used}')
    if overflow:
        print(f'⚠ sobrecupo (más gente que aulas): {len(overflow)}')

    if not commit:
        print('\nDRY-RUN: nada cambiado.')
        return

    reg = dynamodb.Table(REGISTRATION_TABLE)
    for r in orphans:
        reg.delete_item(Key={'ci': r['ci']})
    for ci, mesa in assignment.items():
        if mesa:
            reg.update_item(
                Key={'ci': ci},
                UpdateExpression='SET mesa_code = :m',
                ExpressionAttributeValues={':m': mesa},
            )
    print(f'\nReasignados {len(assignment)} asientos; borrados {len(orphans)} huérfanos.')


if __name__ == '__main__':
    main()
