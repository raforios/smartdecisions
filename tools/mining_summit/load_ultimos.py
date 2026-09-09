'''
    Loads the updated accreditation lists in data/acreditacion/ultimos as an
    UPSERT: participants may already exist, be new, or have a changed eje/role.
    Reconciles the seat (registration): a PARTICIPANTE with a valid eje gets an
    ACTIVE registration for that axis (mesa assigned later by redistribute_aulas);
    anyone who is no longer a PARTICIPANTE has their seat removed. Institution
    text is resolved to the official catalog slug so the name shows in the app.

    Usage:
      python load_ultimos.py            # DRY-RUN
      python load_ultimos.py --commit
'''
import csv
import os
import sys
from datetime import datetime, timezone

import boto3

import bulk_load_acreditacion as b
from institution_resolver import Resolver

FOLDER = os.path.join(b.FOLDER, 'ultimos')
ERRORS_CSV = '/Users/rafael/Work/projects/back/SmartBear/data/errores_carga_ultimos.csv'


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
    dynamodb = boto3.resource('dynamodb', region_name=b.REGION)
    official = [i for i in scan_all(dynamodb.Table('mining_summit_institutions'))
                if i.get('number') is not None]
    resolver = Resolver(official)
    now = datetime.now(timezone.utc).isoformat()

    participants, seats, drop_seats, errors = {}, {}, set(), []
    stats = {'PARTICIPANTE': 0, 'INVITADO': 0, 'ORGANIZADOR': 0, 'unresolved_inst': set()}

    files = sorted(f for f in os.listdir(FOLDER) if f.lower().endswith(('.xlsx', '.xls')))
    for name in files:
        for _rn, values in b.read_rows(os.path.join(FOLDER, name)):
            ci = b.cell(values.get('ci'))
            first = b.cell(values.get('first_name'))
            last = b.cell(values.get('last_name'))
            raw_inst = b.cell(values.get('institution')) or b.institution_from_filename(name)
            if not (ci and first and last):
                miss = [l for l, v in (('CI', ci), ('Nombre', first), ('Apellido', last)) if not v]
                errors.append({'source_file': name, 'ci': ci, 'error_reason': f'faltan: {", ".join(miss)}'})
                continue

            eje = b.parse_eje(values.get('axis'))
            if b.is_ministerio_mineria(raw_inst):
                role = 'ORGANIZADOR'
            elif eje is None:
                role = 'INVITADO'
            else:
                role = 'PARTICIPANTE'

            slug = resolver.resolve(raw_inst)
            if not slug:
                stats['unresolved_inst'].add(raw_inst)
            institution_id = slug or raw_inst

            participants[ci] = {
                'ci': ci, 'first_name': first, 'last_name': last,
                'email': b.cell(values.get('email')) or None,
                'phone': b.cell(values.get('phone')) or None,
                'department': b.cell(values.get('department')) or None,
                'institution_id': institution_id, 'role': role, 'created_at': now,
            }
            stats[role] += 1
            if role == 'PARTICIPANTE':
                axis, label = b.AXIS_BY_NUMBER[eje]
                seats[ci] = {
                    'ci': ci, 'assignment_type': 'FIJO', 'axis': axis, 'axis_label': label,
                    'mesa_code': None, 'observation': None, 'replaces_ci': None,
                    'replaced_by_ci': None, 'status': 'ACTIVE', 'registered_at': now,
                    'registered_by': 'load_ultimos',
                }
            else:
                drop_seats.add(ci)

    with open(ERRORS_CSV, 'w', encoding='utf-8', newline='') as h:
        w = csv.DictWriter(h, fieldnames=b.ERROR_HEADERS, extrasaction='ignore')
        w.writeheader()
        w.writerows(errors)

    print(f'== {"COMMIT" if commit else "DRY-RUN"} ==  archivos={len(files)}')
    print(f'Participantes (upsert): {len(participants)}  '
          f'[PARTICIPANTE={stats["PARTICIPANTE"]} INVITADO={stats["INVITADO"]} ORGANIZADOR={stats["ORGANIZADOR"]}]')
    print(f'Asientos a fijar: {len(seats)}  | asientos a quitar (rol no-participante): {len(drop_seats)}')
    print(f'Errores -> {ERRORS_CSV}: {len(errors)}')
    if stats['unresolved_inst']:
        print(f'Instituciones sin slug oficial (se crearán aparte): {sorted(stats["unresolved_inst"])}')
    if not commit:
        print('\nDRY-RUN: nada escrito.')
        return

    part = dynamodb.Table(b.PARTICIPANTS_TABLE)
    reg = dynamodb.Table(b.REGISTRATION_TABLE)
    with part.batch_writer(overwrite_by_pkeys=['ci']) as batch:
        for item in participants.values():
            batch.put_item(Item={k: v for k, v in item.items() if v is not None})
    for item in seats.values():
        reg.put_item(Item={k: v for k, v in item.items() if v is not None})
    dropped = 0
    for ci in drop_seats:
        if reg.get_item(Key={'ci': ci}).get('Item'):
            reg.delete_item(Key={'ci': ci})
            dropped += 1
    print(f'\nUpsert {len(participants)} participantes; {len(seats)} asientos fijados; '
          f'{dropped} asientos removidos.')


if __name__ == '__main__':
    main()
