'''
    Loads specific accreditation files with a FORCED role and NO aula (support
    staff: ORGANIZADOR / COMUNICACION). Upserts the participant and removes any
    existing seat (registration), since these roles never hold an aula.

    Usage:
      python add_special_roles.py            # DRY-RUN
      python add_special_roles.py --commit     # writes to DynamoDB
'''
import csv
import os
import sys
from datetime import datetime, timezone

import boto3

import bulk_load_acreditacion as b
from institution_resolver import Resolver

# file name -> forced role
FORCED = {
    'protocolo.xlsx': 'ORGANIZADOR',
}
ERRORS_CSV = '/Users/rafael/Work/projects/back/SmartBear/data/errores_roles_especiales.csv'


def main():
    commit = '--commit' in sys.argv[1:]
    dynamodb = boto3.resource('dynamodb', region_name=b.REGION)
    part = dynamodb.Table(b.PARTICIPANTS_TABLE)
    reg = dynamodb.Table(b.REGISTRATION_TABLE)
    insts = dynamodb.Table('mining_summit_institutions').scan().get('Items', [])
    resolver = Resolver([i for i in insts if i.get('number') is not None])
    now = datetime.now(timezone.utc).isoformat()

    participants, drop_seats, errors = {}, [], []
    for name, role in FORCED.items():
        path = os.path.join(b.FOLDER, name)
        if not os.path.exists(path):
            errors.append({'source_file': name, 'error_reason': 'archivo no encontrado'})
            continue
        for _rn, values in b.read_rows(path):
            ci = b.cell(values.get('ci'))
            first = b.cell(values.get('first_name'))
            last = b.cell(values.get('last_name'))
            raw_inst = b.cell(values.get('institution')) or b.institution_from_filename(name)
            institution = resolver.resolve(raw_inst) or raw_inst
            if not (ci and first and last):
                miss = [l for l, v in (('CI', ci), ('Nombre', first), ('Apellido', last)) if not v]
                errors.append({'source_file': name, 'ci': ci, 'first_name': first,
                               'last_name': last, 'institution': institution,
                               'error_reason': f'faltan: {", ".join(miss)}'})
                continue
            participants[ci] = {
                'ci': ci, 'first_name': first, 'last_name': last,
                'email': b.cell(values.get('email')) or None,
                'phone': b.cell(values.get('phone')) or None,
                'department': b.cell(values.get('department')) or None,
                'institution_id': institution or None, 'role': role, 'created_at': now,
            }
            drop_seats.append(ci)

    with open(ERRORS_CSV, 'w', encoding='utf-8', newline='') as h:
        w = csv.DictWriter(h, fieldnames=b.ERROR_HEADERS, extrasaction='ignore')
        w.writeheader()
        w.writerows(errors)

    print(f'== {"COMMIT" if commit else "DRY-RUN"} ==')
    print(f'Archivos: {list(FORCED)}')
    print(f'Personas a cargar (rol forzado, sin aula): {len(participants)}')
    print(f'Errores -> {ERRORS_CSV}: {len(errors)}')
    if not commit:
        print('\nDRY-RUN: nada escrito.')
        return

    with part.batch_writer(overwrite_by_pkeys=['ci']) as batch:
        for item in participants.values():
            batch.put_item(Item={k: v for k, v in item.items() if v is not None})
    dropped = 0
    for ci in drop_seats:
        if reg.get_item(Key={'ci': ci}).get('Item'):
            reg.delete_item(Key={'ci': ci})
            dropped += 1
    print(f'\nCargadas {len(participants)} personas; se removieron {dropped} asientos previos.')


if __name__ == '__main__':
    main()
