'''
    Bulk loader for the Cumbre Minera accreditation Excel files (emergency load).

    Reads every .xlsx/.xls in the accreditation folder, normalizes each row and
    writes participants (and a seat for PARTICIPANTE roles) directly to the
    production DynamoDB tables. Rows that cannot be loaded are collected into a
    single CSV with the reason, so the operator can fix and re-run.

    Role rules (per the event owner):
      1. Institution ~ "Ministerio de Minería y Metalurgia" -> ORGANIZADOR
         (no aula; rotativo), regardless of the eje.
      2. No valid eje (1-6)                                  -> INVITADO (no aula).
      3. Valid eje                                           -> PARTICIPANTE,
         seated in the least-occupied aula of that eje.

    Usage:
      python bulk_load_acreditacion.py            # DRY-RUN (no writes) + errors CSV
      python bulk_load_acreditacion.py --commit    # writes to DynamoDB + errors CSV
'''
import csv
import os
import re
import sys
import unicodedata
import warnings
from collections import Counter, defaultdict
from datetime import datetime, timezone

import boto3
import pandas as pd

warnings.filterwarnings('ignore')

FOLDER = '/Users/rafael/Work/projects/back/SmartBear/data/acreditacion'
ERRORS_CSV = '/Users/rafael/Work/projects/back/SmartBear/data/errores_carga_acreditacion.csv'
REGION = 'us-east-1'

PARTICIPANTS_TABLE = 'mining_summit_participants'
REGISTRATION_TABLE = 'mining_summit_registration'
AULAS_TABLE = 'mining_summit_aulas'

# Official eje number (1-6) -> (axis value, human label).
AXIS_BY_NUMBER = {
    1: ('SEGURIDAD_JURIDICA', 'Seguridad Jurídica Minera'),
    2: ('CONTRATOS', 'Contratos Mineros'),
    3: ('INSTITUCIONALIDAD', 'Institucionalidad y Organización del Sector Minero'),
    4: ('MEDIO_AMBIENTE', 'Medio Ambiente'),
    5: ('COMERCIALIZACION', 'Comercialización, Trazabilidad y Minería Ilegal'),
    6: ('DESARROLLO_PRODUCTIVO', 'Desarrollo Productivo, Inversiones e Incentivos'),
}

ROLE_ORGANIZADOR = 'ORGANIZADOR'
ROLE_INVITADO = 'INVITADO'
ROLE_PARTICIPANTE = 'PARTICIPANTE'

COLUMN_ALIASES = {
    'ci': {'ci', 'carnet', 'carnet de identidad', 'documento', 'cedula'},
    'first_name': {'nombre', 'nombres', 'nombre s'},
    'last_name': {'apellido', 'apellidos'},
    'institution': {'institucion organizacion', 'institucion', 'organizacion', 'empresa'},
    'email': {'correo electronico', 'correo', 'email', 'mail'},
    'phone': {'celular', 'telefono', 'movil', 'tel'},
    'department': {'departamento', 'depto'},
    'axis': {'eje tematico', 'eje', 'eje de preferencia'},
    'role': {'rol', 'cargo', 'funcion'},
}

SKIP_SHEETS = {'instrucciones', 'ejes tematicos'}
ERROR_HEADERS = ['source_file', 'ci', 'first_name', 'last_name', 'institution',
                 'email', 'phone', 'department', 'eje', 'error_reason']


def norm(text):
    '''Lowercase, strip accents/asterisks, collapse to single spaces.'''
    ascii_text = ''.join(
        ch for ch in unicodedata.normalize('NFKD', str(text))
        if not unicodedata.combining(ch)
    ).lower().strip()
    ascii_text = ascii_text.replace('*', ' ')
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', ascii_text)).strip()


def cell(value):
    '''Trimmed string of a cell, empty for NaN/None sentinels.'''
    if value is None:
        return ''
    text = str(value).strip()
    return '' if text.lower() in ('', 'nan', 'none', 'nat') else text


def field_of(header):
    key = norm(header)
    for field, aliases in COLUMN_ALIASES.items():
        if key in aliases:
            return field
    return None


def find_header(df):
    '''Returns (header_row_index, {col_index: field}) or (None, None).'''
    for i in range(min(10, len(df))):
        mapping = {}
        for j, value in enumerate(df.iloc[i].tolist()):
            field = field_of(value)
            if field and field not in mapping.values():
                mapping[j] = field
        if 'ci' in mapping.values() and 'first_name' in mapping.values():
            return i, mapping
    return None, None


def parse_eje(raw):
    '''Returns 1-6 int for a valid eje cell, else None.'''
    text = cell(raw)
    if not text:
        return None
    try:
        number = int(float(text))
    except (TypeError, ValueError):
        return None
    return number if number in AXIS_BY_NUMBER else None


def institution_from_filename(name):
    '''Best-effort institution name from the file name (fallback only).'''
    base = os.path.splitext(name)[0]
    base = re.sub(r'^\s*registro\s+', '', base, flags=re.IGNORECASE)
    return base.strip()


def is_ministerio_mineria(institution):
    key = norm(institution)
    return 'ministerio' in key and 'mineria' in key


def read_rows(path):
    '''Yields (row_number, {field: value}) for the data sheet of a workbook.'''
    xls = pd.ExcelFile(path)
    for sheet in xls.sheet_names:
        if norm(sheet) in SKIP_SHEETS:
            continue
        df = xls.parse(sheet, header=None, dtype=str)
        header_i, mapping = find_header(df)
        if header_i is None:
            continue
        for offset in range(header_i + 1, len(df)):
            row = df.iloc[offset].tolist()
            values = {field: cell(row[idx]) for idx, field in mapping.items()
                      if idx < len(row)}
            if any(values.get(f) for f in ('ci', 'first_name', 'last_name')):
                yield offset + 1, values
        return  # only the first matching sheet
    raise ValueError('no data sheet with the expected header')


class Seater:
    '''Assigns the least-occupied aula within an eje, tracking live occupancy.'''

    def __init__(self, dynamodb):
        self.by_axis = defaultdict(list)      # axis -> [aula code]
        self.capacity = {}                    # code -> capacity
        self.occupied = Counter()             # code -> seats taken
        for item in _scan(dynamodb, AULAS_TABLE):
            axis = item.get('axis')
            if axis:
                self.by_axis[axis].append(item['code'])
                self.capacity[item['code']] = int(item['capacity'])
        for reg in _scan(dynamodb, REGISTRATION_TABLE):
            code = reg.get('mesa_code')
            if code and reg.get('status', 'ACTIVE') == 'ACTIVE':
                self.occupied[code] += 1

    def assign(self, axis):
        '''Returns the least-occupied aula code for the axis, or None if none.'''
        codes = self.by_axis.get(axis)
        if not codes:
            return None
        code = min(codes, key=lambda c: self.occupied[c])
        self.occupied[code] += 1
        return code

    def overflows(self):
        return {c: (self.occupied[c], self.capacity[c])
                for c in self.capacity if self.occupied[c] > self.capacity[c]}


def _scan(dynamodb, table_name):
    table = dynamodb.Table(table_name)
    kwargs = {}
    while True:
        resp = table.scan(**kwargs)
        yield from resp.get('Items', [])
        if 'LastEvaluatedKey' not in resp:
            return
        kwargs['ExclusiveStartKey'] = resp['LastEvaluatedKey']


def build_records(dynamodb):
    '''Parses every file into (participants, registrations, errors, stats).'''
    seater = Seater(dynamodb)
    participants, registrations, errors = {}, {}, []
    stats = Counter()
    seen_ci = set()
    now = datetime.now(timezone.utc).isoformat()

    files = sorted(f for f in os.listdir(FOLDER) if f.lower().endswith(('.xlsx', '.xls')))
    for name in files:
        path = os.path.join(FOLDER, name)
        try:
            rows = list(read_rows(path))
        except Exception as err:
            errors.append({'source_file': name, 'error_reason': f'archivo ilegible: {err}'})
            stats['file_errors'] += 1
            continue

        for _row_no, values in rows:
            ci = cell(values.get('ci'))
            first = cell(values.get('first_name'))
            last = cell(values.get('last_name'))
            institution = cell(values.get('institution')) or institution_from_filename(name)
            eje_num = parse_eje(values.get('axis'))
            base = {
                'source_file': name, 'ci': ci, 'first_name': first, 'last_name': last,
                'institution': institution, 'email': cell(values.get('email')),
                'phone': cell(values.get('phone')), 'department': cell(values.get('department')),
                'eje': cell(values.get('axis')),
            }

            missing = [label for label, val in
                       (('CI', ci), ('Nombre', first), ('Apellido', last)) if not val]
            if missing:
                errors.append({**base, 'error_reason': f'faltan campos obligatorios: {", ".join(missing)}'})
                stats['rejected'] += 1
                continue

            if is_ministerio_mineria(institution):
                role = ROLE_ORGANIZADOR
            elif eje_num is None:
                role = ROLE_INVITADO
            else:
                role = ROLE_PARTICIPANTE

            if ci in seen_ci:
                stats['duplicates'] += 1
            seen_ci.add(ci)

            participants[ci] = {
                'ci': ci, 'first_name': first, 'last_name': last,
                'email': base['email'] or None, 'phone': base['phone'] or None,
                'department': base['department'] or None,
                'institution_id': institution or None, 'role': role, 'created_at': now,
            }
            stats[f'role_{role}'] += 1

            if role == ROLE_PARTICIPANTE:
                axis, label = AXIS_BY_NUMBER[eje_num]
                mesa = seater.assign(axis)
                if not mesa:
                    errors.append({**base, 'error_reason': f'eje {eje_num} sin aulas disponibles'})
                    stats['seat_errors'] += 1
                    registrations.pop(ci, None)
                    continue
                registrations[ci] = {
                    'ci': ci, 'assignment_type': 'FIJO', 'axis': axis, 'axis_label': label,
                    'mesa_code': mesa, 'observation': None, 'replaces_ci': None,
                    'replaced_by_ci': None, 'status': 'ACTIVE', 'registered_at': now,
                    'registered_by': 'bulk_load_acreditacion',
                }
                stats['seated'] += 1

    return participants, registrations, errors, stats, seater


def write_errors_csv(errors):
    with open(ERRORS_CSV, 'w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=ERROR_HEADERS, extrasaction='ignore')
        writer.writeheader()
        for row in errors:
            writer.writerow(row)


def batch_put(dynamodb, table_name, items):
    table = dynamodb.Table(table_name)
    with table.batch_writer(overwrite_by_pkeys=['ci']) as batch:
        for item in items:
            batch.put_item(Item={k: v for k, v in item.items() if v is not None})


def main():
    commit = '--commit' in sys.argv[1:]
    dynamodb = boto3.resource('dynamodb', region_name=REGION)
    participants, registrations, errors, stats, seater = build_records(dynamodb)

    write_errors_csv(errors)

    print(f'== {"COMMIT" if commit else "DRY-RUN"} ==')
    print(f'Archivos procesados en {FOLDER}')
    print(f'Participantes a cargar : {len(participants)}')
    print(f'  con aula (PARTICIPANTE): {stats["seated"]}')
    print(f'  roles: ORGANIZADOR={stats["role_ORGANIZADOR"]} '
          f'INVITADO={stats["role_INVITADO"]} PARTICIPANTE={stats["role_PARTICIPANTE"]}')
    print(f'  CIs duplicados (upsert, gana el último): {stats["duplicates"]}')
    print(f'Registros con error -> {ERRORS_CSV}: {len(errors)} '
          f'(rechazados={stats["rejected"]}, sin_aula={stats["seat_errors"]}, '
          f'archivos={stats["file_errors"]})')
    overflows = seater.overflows()
    if overflows:
        print(f'⚠ aulas sobre capacidad: {overflows}')

    if not commit:
        print('\nDRY-RUN: no se escribió nada. Re-ejecuta con --commit para cargar.')
        return

    batch_put(dynamodb, PARTICIPANTS_TABLE, participants.values())
    batch_put(dynamodb, REGISTRATION_TABLE, registrations.values())
    print(f'\nCargados {len(participants)} participantes y {len(registrations)} registros en DynamoDB.')


if __name__ == '__main__':
    main()
