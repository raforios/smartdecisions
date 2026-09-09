'''
    Bulk-load tool: imports summit participants from an Excel file into the
    DynamoDB table `mining_summit_participants`.

    Participants are loaded WITHOUT a seat (eje/mesa): the final table/classroom
    distribution happens later, once invitation responses are confirmed. The
    institution is matched against the seeded institutions catalog so the role
    and seat-assignment type can be derived up front.

    Expected Excel columns (header row, case/accent-insensitive, ES/EN):
        ci            (required)  Carnet de Identidad, unique key.
        nombre        (required)  first_name.
        apellido      (required)  last_name.
        institucion   (optional)  institution name, abbreviation or slug id.
        email         (optional)
        celular       (optional)  phone.
        departamento  (optional)

    Usage (run from the app root):
        python tools/mining_summit/import_participants.py [path/to/file.xlsx]

    Config via env vars:
        DYNAMODB_TABLE_NAME_PARTICIPANTS  (default: mining_summit_participants)
        DYNAMODB_TABLE_NAME_INSTITUTIONS  (default: mining_summit_institutions)
        AWS_REGION / AWS_DEFAULT_REGION   (default: us-east-1)
        DYNAMODB_ENDPOINT_URL             (optional, for local DynamoDB)
'''
import os
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

import boto3
import openpyxl

APP_ROOT = Path(__file__).resolve().parents[2]
SERVICE_ROOT = APP_ROOT / 'services' / 'mining_summit'
sys.path.insert(0, str(SERVICE_ROOT))

# The service package is added to sys.path above so the business rules stay
# single-sourced; pylint cannot follow that dynamic path.
# pylint: disable=wrong-import-position,import-error
from schemas.enums import InstitutionCategory
from services.summit_rules import resolve_assignment_type, resolve_role

PARTICIPANTS_TABLE = os.getenv('DYNAMODB_TABLE_NAME_PARTICIPANTS', 'mining_summit_participants')
INSTITUTIONS_TABLE = os.getenv('DYNAMODB_TABLE_NAME_INSTITUTIONS', 'mining_summit_institutions')
REGION = os.getenv('AWS_REGION') or os.getenv('AWS_DEFAULT_REGION') or 'us-east-1'
ENDPOINT_URL = os.getenv('DYNAMODB_ENDPOINT_URL')
TIMEZONE = ZoneInfo('America/La_Paz')

DEFAULT_TEMPLATE = APP_ROOT / 'tools' / 'mining_summit' / 'plantilla_participantes.xlsx'

# Accepted header names per logical field (normalized: lowercase, no accents).
COLUMN_ALIASES = {
    'ci': {'ci', 'carnet', 'carnet_de_identidad', 'documento', 'cedula'},
    'first_name': {'first_name', 'nombre', 'nombres'},
    'last_name': {'last_name', 'apellido', 'apellidos'},
    'institution': {'institution', 'institucion', 'institution_id', 'institucion_id',
                    'organizacion', 'entidad'},
    'email': {'email', 'correo', 'correo_electronico', 'e_mail', 'mail'},
    'phone': {'phone', 'celular', 'telefono', 'movil', 'tel'},
    'department': {'department', 'departamento', 'depto'}
}


def _normalize(text: str) -> str:
    '''Lowercases, strips accents and collapses non-alphanumerics to spaces.'''
    ascii_text = ''.join(
        char for char in unicodedata.normalize('NFKD', str(text))
        if not unicodedata.combining(char)
    ).lower().strip()
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', ascii_text)).strip()


def _header_field(header: str) -> Optional[str]:
    '''Maps a spreadsheet header to a logical field name, or None.'''
    key = _normalize(header).replace(' ', '_')
    for field, aliases in COLUMN_ALIASES.items():
        if key in aliases:
            return field
    return None


def _build_dynamodb():
    '''Creates a boto3 DynamoDB resource honoring the optional local endpoint.'''
    return boto3.resource('dynamodb', region_name = REGION, endpoint_url = ENDPOINT_URL)


def _load_institution_lookup(dynamodb) -> Dict[str, Dict[str, Any]]:
    '''
        Builds a lookup from normalized institution id/name/abbreviation to the
        institution record, so free-typed values can be matched to the catalog.
    '''
    table = dynamodb.Table(INSTITUTIONS_TABLE)
    lookup: Dict[str, Dict[str, Any]] = {}
    response = table.scan()
    items = response.get('Items', [])
    while 'LastEvaluatedKey' in response:
        response = table.scan(ExclusiveStartKey = response['LastEvaluatedKey'])
        items.extend(response.get('Items', []))
    for item in items:
        for key in (item.get('id'), item.get('name'), item.get('abbreviation')):
            if key:
                lookup[_normalize(key)] = item
    return lookup


def _resolve_institution(raw: Any, lookup: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    '''
        Resolves a raw institution cell into persistable attributes. Matched
        institutions contribute id/name/role/assignment_type; unmatched values
        are kept as free-text 'company' so no information is lost.
    '''
    if raw is None or str(raw).strip() == '':
        return {}
    match = lookup.get(_normalize(raw))
    if not match:
        return {'company': str(raw).strip()}
    role = resolve_role(InstitutionCategory(match['category']))
    return {
        'institution_id': match['id'],
        'institution_name': match['name'],
        'role': role.value,
        'assignment_type': resolve_assignment_type(role).value
    }


def _build_participant(row: Dict[str, Any], lookup, now: datetime) -> Optional[Dict[str, Any]]:
    '''Builds a participant item from a mapped row, or None if the CI is missing.'''
    ci = row.get('ci')
    if ci is None or str(ci).strip() == '':
        return None
    item: Dict[str, Any] = {
        'ci': str(ci).strip(),
        'first_name': str(row.get('first_name', '') or '').strip(),
        'last_name': str(row.get('last_name', '') or '').strip(),
        'registered_date': now.date().isoformat(),
        'registered_at': now.isoformat()
    }
    for field in ('email', 'phone', 'department'):
        value = row.get(field)
        if value is not None and str(value).strip() != '':
            item[field] = str(value).strip()
    item.update(_resolve_institution(row.get('institution'), lookup))
    return item


def _read_rows(worksheet) -> list:
    '''Reads the sheet into a list of field-mapped row dicts using the header.'''
    rows = list(worksheet.iter_rows(values_only = True))
    if not rows:
        return []
    header = {index: _header_field(cell) for index, cell in enumerate(rows[0])}
    mapped = []
    for raw_row in rows[1:]:
        entry = {}
        for index, value in enumerate(raw_row):
            field = header.get(index)
            if field:
                entry[field] = value
        mapped.append(entry)
    return mapped


def import_participants(xlsx_path: Path) -> Dict[str, int]:
    '''Loads all participants from the Excel file into DynamoDB (upsert by CI).'''
    dynamodb = _build_dynamodb()
    lookup = _load_institution_lookup(dynamodb)
    workbook = openpyxl.load_workbook(xlsx_path, data_only = True)
    rows = _read_rows(workbook.worksheets[0])
    now = datetime.now(TIMEZONE)

    stats = {'loaded': 0, 'skipped': 0, 'unmatched_institution': 0}
    table = dynamodb.Table(PARTICIPANTS_TABLE)
    with table.batch_writer(overwrite_by_pkeys = ['ci']) as batch:
        for row in rows:
            item = _build_participant(row, lookup, now)
            if item is None:
                stats['skipped'] += 1
                continue
            if 'company' in item and 'institution_id' not in item:
                stats['unmatched_institution'] += 1
            batch.put_item(Item = item)
            stats['loaded'] += 1
    return stats


def main() -> None:
    '''Entry point: bulk-loads participants from the given (or default) file.'''
    xlsx_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TEMPLATE
    if not xlsx_path.exists():
        print(f'Excel file not found: {xlsx_path}')
        sys.exit(1)
    stats = import_participants(xlsx_path)
    target = ENDPOINT_URL or f'AWS {REGION}'
    print(f'Loaded {stats["loaded"]} participants into {PARTICIPANTS_TABLE} ({target}). '
          f'Skipped (no CI): {stats["skipped"]}. '
          f'Unmatched institution: {stats["unmatched_institution"]}.')


if __name__ == '__main__':
    main()
