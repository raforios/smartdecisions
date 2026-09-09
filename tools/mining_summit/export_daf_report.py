'''
    Report tool: builds the attendance workbook requested by the Dirección
    Administrativa Financiera for the Mining Summit (Cumbre Nacional Minera).

    The workbook has one worksheet per event day plus a final 'No asistieron'
    sheet, each with the same columns (CI · Nombre completo · Institución · Rol ·
    Aula · Departamento · Fecha · Hora) and rows grouped by Rol then Institución.

    The event days are DISCOVERED from the attendances table (not hard-coded), so
    the report automatically covers every day that has attendance marks. Each day
    sheet is titled in Spanish (e.g. '23 de julio'); the 'No asistieron' sheet
    lists accredited participants with no attendance on ANY day (Fecha/Hora empty).

    The population is every accredited participant (mining_summit_participants);
    Aula comes from the person's ACTIVE registration (blank for unseated roles).

    Usage (run from the app root):
        AWS_PROFILE=deploy_ml python tools/mining_summit/export_daf_report.py \
            --out /path/to/reporte.xlsx

    Config via env vars:
        DYNAMODB_TABLE_NAME_PARTICIPANTS   (default: mining_summit_participants)
        DYNAMODB_TABLE_NAME_REGISTRATION   (default: mining_summit_registration)
        DYNAMODB_TABLE_NAME_INSTITUTIONS   (default: mining_summit_institutions)
        DYNAMODB_TABLE_NAME_ATTENDANCES    (default: mining_summit_attendances)
        AWS_REGION / AWS_DEFAULT_REGION    (default: us-east-1)
        AWS_PROFILE                        (optional, standard boto3 profile)
        DYNAMODB_ENDPOINT_URL              (optional, for local DynamoDB)
'''
import argparse
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

import boto3
import openpyxl
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

NO_SHOW_SHEET_TITLE = 'No asistieron'

_SPANISH_MONTHS = {
    1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril', 5: 'mayo', 6: 'junio',
    7: 'julio', 8: 'agosto', 9: 'septiembre', 10: 'octubre', 11: 'noviembre',
    12: 'diciembre'
}


def _day_title(iso_date: str) -> str:
    '''
        Builds the Spanish worksheet title for a day, e.g. '23 de julio'. Falls
        back to the raw ISO date if it cannot be parsed.
    '''
    try:
        parsed = datetime.strptime(iso_date, '%Y-%m-%d')
        return f'{parsed.day} de {_SPANISH_MONTHS[parsed.month]}'
    except (ValueError, KeyError):
        return iso_date

REGION = os.getenv('AWS_REGION') or os.getenv('AWS_DEFAULT_REGION') or 'us-east-1'
ENDPOINT_URL = os.getenv('DYNAMODB_ENDPOINT_URL')

PARTICIPANTS_TABLE = os.getenv('DYNAMODB_TABLE_NAME_PARTICIPANTS', 'mining_summit_participants')
REGISTRATION_TABLE = os.getenv('DYNAMODB_TABLE_NAME_REGISTRATION', 'mining_summit_registration')
INSTITUTIONS_TABLE = os.getenv('DYNAMODB_TABLE_NAME_INSTITUTIONS', 'mining_summit_institutions')
ATTENDANCES_TABLE = os.getenv('DYNAMODB_TABLE_NAME_ATTENDANCES', 'mining_summit_attendances')

# (header, row-dict key) columns shared by the three worksheets.
COLUMNS: Sequence[tuple[str, str]] = (
    ('CI', 'ci'),
    ('Nombre completo', 'full_name'),
    ('Institución', 'institution'),
    ('Rol', 'role'),
    ('Aula', 'aula'),
    ('Departamento', 'department'),
    ('Fecha', 'fecha'),
    ('Hora', 'hora')
)

_HEADER_FILL = PatternFill('solid', fgColor = '242732')
_HEADER_FONT = Font(bold = True, color = 'FFFFFF')
_ACTIVE_STATUS = 'ACTIVE'


def _dynamodb_resource() -> Any:
    '''Builds the DynamoDB resource, honoring an optional local endpoint.'''
    session = boto3.session.Session()
    if ENDPOINT_URL:
        return session.resource('dynamodb', region_name = REGION, endpoint_url = ENDPOINT_URL)
    return session.resource('dynamodb', region_name = REGION)


def _scan_all(dynamodb_resource: Any, table_name: str) -> List[Dict[str, Any]]:
    '''Returns every item of a table, transparently following pagination.'''
    table = dynamodb_resource.Table(table_name)
    items: List[Dict[str, Any]] = []
    scan_kwargs: Dict[str, Any] = {}
    while True:
        response = table.scan(**scan_kwargs)
        items.extend(response.get('Items', []))
        last_key = response.get('LastEvaluatedKey')
        if not last_key:
            break
        scan_kwargs['ExclusiveStartKey'] = last_key
    return items


def _format_time(attendance_at: Optional[str]) -> str:
    '''
        Extracts the wall-clock time (HH:MM:SS) from an ISO-8601 attendance
        timestamp. Falls back to an empty string when the value is missing or
        not parseable, so a bad record never breaks the whole report.
    '''
    if not attendance_at:
        return ''
    try:
        return datetime.fromisoformat(attendance_at).strftime('%H:%M:%S')
    except ValueError:
        return ''


def _format_date(iso_date: Optional[str]) -> str:
    '''Reformats an ISO date (YYYY-MM-DD) to DD/MM/YYYY for the report.'''
    if not iso_date:
        return ''
    try:
        return datetime.strptime(iso_date, '%Y-%m-%d').strftime('%d/%m/%Y')
    except ValueError:
        return iso_date


def _build_row(
    person: Dict[str, Any],
    institution_names: Dict[str, str],
    aula_by_ci: Dict[str, str],
    fecha: str = '',
    hora: str = ''
) -> Dict[str, Any]:
    '''
        Flattens a participant into a report row, joining the institution name
        and the seat (aula). Fecha/Hora are supplied by the caller (empty for
        the no-show sheet).
    '''
    full_name = f'{person.get("first_name", "")} {person.get("last_name", "")}'.strip()
    return {
        'ci': person.get('ci', ''),
        'full_name': full_name,
        'institution': institution_names.get(person.get('institution_id'), '') or '',
        'role': person.get('role') or '',
        'aula': aula_by_ci.get(person.get('ci'), '') or '',
        'department': person.get('department') or '',
        'fecha': fecha,
        'hora': hora
    }


def _sort_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    '''Groups rows by Rol, then Institución, then name for a tidy layout.'''
    return sorted(
        rows,
        key = lambda row: (row['role'], row['institution'], row['full_name'])
    )


def _write_sheet(worksheet: Any, rows: List[Dict[str, Any]]) -> None:
    '''Writes the shared header and the given rows into a worksheet.'''
    for col_index, (header, _key) in enumerate(COLUMNS, start = 1):
        cell = worksheet.cell(row = 1, column = col_index, value = header)
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        worksheet.column_dimensions[get_column_letter(col_index)].width = 26
    worksheet.freeze_panes = 'A2'

    for row_index, record in enumerate(_sort_rows(rows), start = 2):
        for col_index, (_header, key) in enumerate(COLUMNS, start = 1):
            worksheet.cell(row = row_index, column = col_index, value = record.get(key))


def build_workbook(dynamodb_resource: Any) -> tuple[openpyxl.Workbook, Dict[str, int]]:
    '''
        Builds the three-sheet attendance workbook and returns it alongside a
        per-sheet row-count summary for the console log.
    '''
    persons = {person['ci']: person for person in _scan_all(dynamodb_resource, PARTICIPANTS_TABLE)}
    institution_names = {
        institution['id']: institution.get('name', '')
        for institution in _scan_all(dynamodb_resource, INSTITUTIONS_TABLE)
    }
    # Aula ≡ mesa_code from the person's ACTIVE registration (unseated => none).
    aula_by_ci = {
        registration['ci']: registration.get('mesa_code', '')
        for registration in _scan_all(dynamodb_resource, REGISTRATION_TABLE)
        if registration.get('status') == _ACTIVE_STATUS
    }

    # Attendances grouped by date: ci -> attendance_at timestamp. The event days
    # are discovered from the data and processed in chronological order.
    attendances = _scan_all(dynamodb_resource, ATTENDANCES_TABLE)
    present_by_date: Dict[str, Dict[str, str]] = {}
    for attendance in attendances:
        date = attendance.get('attendance_date')
        if date and attendance.get('ci'):
            present_by_date.setdefault(date, {})[attendance['ci']] = \
                attendance.get('attendance_at', '')

    workbook = openpyxl.Workbook()
    workbook.remove(workbook.active)
    summary: Dict[str, int] = {}

    for date in sorted(present_by_date):
        title = _day_title(date)
        rows = [
            _build_row(
                person = persons[ci],
                institution_names = institution_names,
                aula_by_ci = aula_by_ci,
                fecha = _format_date(date),
                hora = _format_time(attendance_at)
            )
            for ci, attendance_at in present_by_date[date].items()
            if ci in persons
        ]
        _write_sheet(workbook.create_sheet(title = title), rows)
        summary[title] = len(rows)

    # No-show sheet: accredited participants absent on EVERY day.
    present_any_day = set().union(*present_by_date.values()) if present_by_date else set()
    no_show_rows = [
        _build_row(person, institution_names, aula_by_ci)
        for ci, person in persons.items()
        if ci not in present_any_day
    ]
    _write_sheet(workbook.create_sheet(title = NO_SHOW_SHEET_TITLE), no_show_rows)
    summary[NO_SHOW_SHEET_TITLE] = len(no_show_rows)

    return workbook, summary


def main() -> None:
    '''Entry point: builds the workbook and saves it to the --out path.'''
    parser = argparse.ArgumentParser(description = 'Build the DAF attendance report (.xlsx).')
    parser.add_argument(
        '--out',
        default = 'reporte_asistencia_cumbre.xlsx',
        help = 'Output .xlsx path (default: reporte_asistencia_cumbre.xlsx).'
    )
    args = parser.parse_args()

    workbook, summary = build_workbook(_dynamodb_resource())
    workbook.save(args.out)

    print(f'Reporte generado -> {args.out}')
    for title, count in summary.items():
        print(f'  Hoja "{title}": {count} filas')


if __name__ == '__main__':
    main()
