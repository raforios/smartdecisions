'''
    Mining Analysis Business Logic Services
'''
import unicodedata
from typing import Any
from boto3.resources.base import ServiceResource
from sqlalchemy.orm import Session
from services.utils import load_parameters
from services.prices_store import all_quotations


# Required, not optional: a fallback written in code is still a number the
# code chose.
ENV_VARS = load_parameters({
    'CHANGE_DECIMALS': int
})

# Decimals a published percentage carries.
CHANGE_DECIMALS = ENV_VARS['CHANGE_DECIMALS']

def normalize_name(name: str) -> str:
    '''
    Lower-cases and strips accents so 'Estaño' / 'ESTANO' / 'estano' all match.

    Accent stripping is intentional: source files occasionally arrive with
    ASCII-only mineral names from older OCR pipelines.
    '''
    base = unicodedata.normalize('NFKD', str(name).strip().lower())
    return ''.join(c for c in base if not unicodedata.combining(c))


# Canonical mineral catalog rendered in the official Minerales_0X templates.
# Order is significant: the PNG report mirrors this sequence top-to-bottom.
OFFICIAL_MINERALS: tuple[dict[str, str], ...] = (
    {'name': 'Estaño',    'chemical_symbol': 'Sn', 'unit': 'LF',  'quoted_in': 'LME'},
    {'name': 'Plomo',     'chemical_symbol': 'Pb', 'unit': 'LF',  'quoted_in': 'LME'},
    {'name': 'Zinc',      'chemical_symbol': 'Zn', 'unit': 'LF',  'quoted_in': 'LME'},
    {'name': 'Cobre',     'chemical_symbol': 'Cu', 'unit': 'LF',  'quoted_in': 'LME'},
    {'name': 'Antimonio', 'chemical_symbol': 'Sb', 'unit': 'TMF', 'quoted_in': 'AM'},
    {'name': 'Wolfram',   'chemical_symbol': 'W',  'unit': 'TMF', 'quoted_in': 'AM'},
    {'name': 'Bismuto',   'chemical_symbol': 'Bi', 'unit': 'LF',  'quoted_in': 'AM'},
    {'name': 'Oro',       'chemical_symbol': 'Au', 'unit': 'OT',  'quoted_in': 'LFIX'},
    {'name': 'Plata',     'chemical_symbol': 'Ag', 'unit': 'OT',  'quoted_in': 'LFIX'},
)

async def get_all_prices_service(
    dynamodb_resource: ServiceResource | None,
    db: Session | None = None
) -> list[dict[str, Any]]:
    '''
    Retrieves every quotation with the metadata of its mineral.

    Goes through the store so it answers on either backend. The mineral's unit,
    symbol and market come from OFFICIAL_MINERALS, the published catalogue: on
    DynamoDB the table holds only the name, and the bulletins are built from
    that catalogue anyway.

    Args:
        db (Session): Database session; ignored when running on DynamoDB.

    Returns:
        list[dict[str, Any]]: Rows matching MiningPriceResponseSchema.
    '''
    catalog = {
        normalize_name(entry['name']): entry for entry in OFFICIAL_MINERALS
    }
    rows: list[dict[str, Any]] = []
    for record in all_quotations(dynamodb_resource, db = db):
        entry = catalog.get(normalize_name(record.mineral_name), {})
        rows.append({
            'date': record.date,
            'price_low': record.price_low,
            'price_high': record.price_high,
            'mineral': {
                'name': record.mineral_name,
                'unit': entry.get('unit', ''),
                'chemical_symbol': entry.get('chemical_symbol'),
                'quoted_in': entry.get('quoted_in'),
                'method': entry.get('method'),
            },
        })
    return rows
