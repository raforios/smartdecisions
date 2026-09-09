'''
    Cleans participant CIs that carry a department-code suffix (e.g. "4123945 Tj",
    "3498453 LP") by stripping the suffix to the plain number. The CI is the
    partition key, so this migrates the participant + its registration + its
    attendances to the new CI and deletes the old rows. Passports (A00xxxx),
    diplomatic ids and numeric complements (-1M/-1P/...) are left untouched.

    Usage:
      python clean_ci_suffixes.py            # DRY-RUN
      python clean_ci_suffixes.py --commit
'''
import re
import sys

import boto3

REGION = 'us-east-1'
PARTICIPANTS_TABLE = 'mining_summit_participants'
REGISTRATION_TABLE = 'mining_summit_registration'
ATTENDANCES_TABLE = 'mining_summit_attendances'

# Department codes appended to some CIs (case-insensitive), with an optional space.
DEPT_CODES = {'LP', 'OR', 'PT', 'TJA', 'TJ', 'SC', 'CB', 'CBBA', 'CH', 'BN', 'PD'}
PATTERN = re.compile(r'^(\d+)\s+([A-Za-z]{2,4})$')


def strip_ci(ci):
    '''Returns the cleaned CI if it has a department-code suffix, else None.'''
    match = PATTERN.match(str(ci).strip())
    if match and match.group(2).upper() in DEPT_CODES:
        return match.group(1)
    return None


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
    part = dynamodb.Table(PARTICIPANTS_TABLE)
    reg = dynamodb.Table(REGISTRATION_TABLE)
    att = dynamodb.Table(ATTENDANCES_TABLE)

    participants = scan_all(part)
    existing_cis = {p['ci'] for p in participants}
    plan, collisions = [], []
    for p in participants:
        new_ci = strip_ci(p['ci'])
        if not new_ci:
            continue
        if new_ci in existing_cis:
            collisions.append((p['ci'], new_ci))
        else:
            plan.append((p, new_ci))

    print(f'== {"COMMIT" if commit else "DRY-RUN"} ==')
    print(f'CIs a limpiar: {len(plan)}')
    for p, new_ci in plan:
        print(f'  {p["ci"]!r} -> {new_ci}   ({p.get("first_name")} {p.get("last_name")})')
    if collisions:
        print(f'⚠ COLISIONES (el CI numérico ya existe, NO se tocan): {collisions}')

    if not commit:
        print('\nDRY-RUN: nada cambiado.')
        return

    migrated_reg = migrated_att = 0
    for p, new_ci in plan:
        old_ci = p['ci']
        part.put_item(Item={**p, 'ci': new_ci})
        part.delete_item(Key={'ci': old_ci})
        old_reg = reg.get_item(Key={'ci': old_ci}).get('Item')
        if old_reg:
            reg.put_item(Item={**old_reg, 'ci': new_ci})
            reg.delete_item(Key={'ci': old_ci})
            migrated_reg += 1
        for a in att.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key('ci').eq(old_ci)
        ).get('Items', []):
            att.put_item(Item={**a, 'ci': new_ci})
            att.delete_item(Key={'ci': old_ci, 'attendance_date': a['attendance_date']})
            migrated_att += 1

    print(f'\nMigrados {len(plan)} participantes (+{migrated_reg} asientos, +{migrated_att} asistencias).')


if __name__ == '__main__':
    main()
