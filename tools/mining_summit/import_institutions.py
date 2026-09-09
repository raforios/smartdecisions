'''
    Seed tool: loads the Mining Summit institutions catalog from the official
    participation matrix (matriz_participantes.xlsx) into the DynamoDB table
    `mining_summit_institutions`.

    Usage (run from the app root):
        # AWS (uses your default credentials / region):
        python tools/mining_summit/import_institutions.py

        # Local DynamoDB:
        DYNAMODB_ENDPOINT_URL=http://localhost:3100 \
        python tools/mining_summit/import_institutions.py

    Config via env vars:
        DYNAMODB_TABLE_NAME_INSTITUTIONS  (default: mining_summit_institutions)
        AWS_REGION / AWS_DEFAULT_REGION   (default: us-east-1)
        DYNAMODB_ENDPOINT_URL             (optional, for local DynamoDB)

    Each institution is normalized (id, number, name, abbreviation, category,
    cupos) and written to the table. Role and seat-assignment are NOT stored:
    they are derived at runtime from the category so the business rules stay
    single-sourced in services/summit_rules.py.
'''
import os
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional

import boto3
import openpyxl

APP_ROOT = Path(__file__).resolve().parents[2]
SPREADSHEET_PATH = APP_ROOT / 'demo' / 'cumbre-minera' / 'assets' / 'matriz_participantes.xlsx'

TABLE_NAME = os.getenv('DYNAMODB_TABLE_NAME_INSTITUTIONS', 'mining_summit_institutions')
REGION = os.getenv('AWS_REGION') or os.getenv('AWS_DEFAULT_REGION') or 'us-east-1'
ENDPOINT_URL = os.getenv('DYNAMODB_ENDPOINT_URL')

# Column indexes (0-based) in the 'Matriz Oficial de Trabajo' sheet.
COL_NUMBER = 0
COL_CATEGORY = 1
COL_NAME = 2
COL_CUPOS = 3


def _strip_accents(text: str) -> str:
    '''Removes diacritics so slugs stay ASCII-safe and URL-friendly.'''
    normalized = unicodedata.normalize('NFKD', text)
    return ''.join(char for char in normalized if not unicodedata.combining(char))


def _slugify(text: str) -> str:
    '''Builds a stable, lowercase, hyphenated slug from an institution name.'''
    ascii_text = _strip_accents(text).lower()
    return re.sub(r'[^a-z0-9]+', '-', ascii_text).strip('-')


def _parse_abbreviation(name: str) -> Optional[str]:
    '''Extracts a trailing acronym in parentheses, e.g. "... (FENCOMIN)".'''
    match = re.search(r'\(([^()]+)\)\s*$', name)
    if not match:
        return None
    candidate = match.group(1).strip()
    if len(candidate) <= 12 and candidate.upper() == candidate:
        return candidate
    return None


def _build_institution(row: tuple) -> Optional[Dict[str, Any]]:
    '''Maps a spreadsheet row to a normalized institution dict, or None.'''
    number = row[COL_NUMBER]
    if not isinstance(number, int):
        return None
    name = str(row[COL_NAME]).strip()
    institution = {
        'id': _slugify(name),
        'number': number,
        'name': name,
        'category': str(row[COL_CATEGORY]).strip(),
        'cupos': int(row[COL_CUPOS])
    }
    abbreviation = _parse_abbreviation(name)
    if abbreviation:
        institution['abbreviation'] = abbreviation
    return institution


def build_catalog() -> List[Dict[str, Any]]:
    '''Reads the spreadsheet and returns the normalized institution catalog.'''
    workbook = openpyxl.load_workbook(SPREADSHEET_PATH, data_only = True)
    worksheet = workbook.worksheets[0]
    catalog: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()
    for row in worksheet.iter_rows(values_only = True):
        institution = _build_institution(row)
        if institution is None:
            continue
        if institution['id'] in seen_ids:
            institution['id'] = f'{institution["id"]}-{institution["number"]}'
        seen_ids.add(institution['id'])
        catalog.append(institution)
    return catalog


def seed_table(catalog: List[Dict[str, Any]]) -> None:
    '''Writes the catalog into the DynamoDB institutions table.'''
    resource = boto3.resource('dynamodb', region_name = REGION, endpoint_url = ENDPOINT_URL)
    table = resource.Table(TABLE_NAME)
    with table.batch_writer() as batch:
        for institution in catalog:
            batch.put_item(Item = institution)


def main() -> None:
    '''Entry point: builds the catalog and seeds the DynamoDB table.'''
    catalog = build_catalog()
    seed_table(catalog)
    total_cupos = sum(item['cupos'] for item in catalog)
    target = ENDPOINT_URL or f'AWS {REGION}'
    print(f'Seeded {len(catalog)} institutions ({total_cupos} cupos) into '
          f'{TABLE_NAME} ({target}).')


if __name__ == '__main__':
    main()
