'''
    Cleans diplomatic-carnet noise from participant CIs: drops a trailing
    "(Carnet Diplomático)" note and a leading "CD " prefix. Example:
    "A007687 (Carnet Diplomático)" -> "A007687", "CD A007403" -> "A007403".
    CI is the partition key, so it migrates participant + registration +
    attendances to the new CI and deletes the old rows.

    Usage:
      python clean_ci_diplomatic.py            # DRY-RUN
      python clean_ci_diplomatic.py --commit
'''
import re
import sys
import unicodedata

import boto3

REGION = 'us-east-1'
PARTICIPANTS_TABLE = 'mining_summit_participants'
REGISTRATION_TABLE = 'mining_summit_registration'
ATTENDANCES_TABLE = 'mining_summit_attendances'


def strip_ci(ci):
    '''Returns the cleaned CI if it carries diplomatic-carnet noise, else None.'''
    original = str(ci).strip()
    cleaned = original
    # Drop a "(...)" note that mentions "diplomat".
    match = re.search(r'\(([^)]*)\)\s*$', cleaned)
    if match:
        note = ''.join(c for c in unicodedata.normalize('NFKD', match.group(1))
                       if not unicodedata.combining(c)).lower()
        if 'diplomat' in note:
            cleaned = cleaned[:match.start()].strip()
    # Drop a leading "CD " (Carnet Diplomático) prefix.
    cleaned = re.sub(r'^CD\s+', '', cleaned).strip()
    return cleaned if cleaned and cleaned != original else None


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
    existing = {p['ci'] for p in participants}
    plan, collisions = [], []
    for p in participants:
        new_ci = strip_ci(p['ci'])
        if not new_ci:
            continue
        (collisions if new_ci in existing else plan).append((p, new_ci))

    print(f'== {"COMMIT" if commit else "DRY-RUN"} ==  a limpiar: {len(plan)}')
    for p, new_ci in plan:
        print(f'  {p["ci"]!r} -> {new_ci!r}   ({p.get("first_name")} {p.get("last_name")})')
    if collisions:
        print(f'⚠ COLISIONES (ya existe, NO se tocan): {[(p["ci"], n) for p, n in collisions]}')

    if not commit:
        print('\nDRY-RUN: nada cambiado.')
        return

    for p, new_ci in plan:
        old_ci = p['ci']
        part.put_item(Item={**p, 'ci': new_ci})
        part.delete_item(Key={'ci': old_ci})
        old_reg = reg.get_item(Key={'ci': old_ci}).get('Item')
        if old_reg:
            reg.put_item(Item={**old_reg, 'ci': new_ci})
            reg.delete_item(Key={'ci': old_ci})
        for a in att.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key('ci').eq(old_ci)
        ).get('Items', []):
            att.put_item(Item={**a, 'ci': new_ci})
            att.delete_item(Key={'ci': old_ci, 'attendance_date': a['attendance_date']})
    print(f'\nMigrados {len(plan)} participantes.')


if __name__ == '__main__':
    main()
