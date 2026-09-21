'''
    Mining Analysis Business Logic Services
'''
from collections import defaultdict
import io
import re
import unicodedata
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, Any, List, Tuple
from fastapi import Request
import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Query, Session
from models.mining_analysis import (
    Company,
    Mineral,
    MiningPrice,
    Department,
    Municipality,
    RoyaltyPayment,
    RoyaltyTransaction
)
from schemas.mining_analysis import MiningResult, MiningStatus
from services.environment import load_and_validate_env_vars
from services.utils import handle_service_errors
from services.exceptions import InvalidInputError
from services.logger_config import custom_logger as logger
from services.prices_store import all_quotations


# Required, not optional: a fallback written in code is still a number the
# code chose.
ENV_VARS = load_and_validate_env_vars({
    'CHANGE_DECIMALS': int,
    'ROYALTIES_MAX_VARIATION_PERCENT': str,
    'ROYALTIES_MIN_BASELINE_BOB': str,
    'ROYALTIES_CRITICAL_DROP_PERCENT': float,
    'ROYALTIES_KPI_TOP_ROWS': int,
})

# Decimals a published percentage carries.
CHANGE_DECIMALS = ENV_VARS['CHANGE_DECIMALS']

# Royalty KPIs. The cap keeps a percentage readable when a municipality starts
# from almost nothing; the baseline filter drops the amounts too small to make
# a variation mean anything; the drop threshold is what the Ministry calls a
# critical fall; and the top rows are how many make the bulletin. Read as
# strings so Decimal takes them exactly, without a float in between.
MAX_VARIATION_PERCENT = Decimal(ENV_VARS['ROYALTIES_MAX_VARIATION_PERCENT'])
MIN_BASELINE_BOB = Decimal(ENV_VARS['ROYALTIES_MIN_BASELINE_BOB'])
CRITICAL_DROP_PERCENT = ENV_VARS['ROYALTIES_CRITICAL_DROP_PERCENT']
KPI_TOP_ROWS = ENV_VARS['ROYALTIES_KPI_TOP_ROWS']

# A percentage is published with the same decimals everywhere in the service.
_PERCENT_QUANTUM: Decimal = Decimal(1).scaleb(-CHANGE_DECIMALS)


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
OFFICIAL_MINERALS: Tuple[Dict[str, str], ...] = (
    {'name': 'Estaño',    'chemical_symbol': 'Sn', 'unit': 'LF',  'quoted_in': 'LFIX'},
    {'name': 'Plomo',     'chemical_symbol': 'Pb', 'unit': 'LF',  'quoted_in': 'LME'},
    {'name': 'Zinc',      'chemical_symbol': 'Zn', 'unit': 'LF',  'quoted_in': 'LME'},
    {'name': 'Cobre',     'chemical_symbol': 'Cu', 'unit': 'LF',  'quoted_in': 'LME'},
    {'name': 'Antimonio', 'chemical_symbol': 'Sb', 'unit': 'TMF', 'quoted_in': 'AM'},
    {'name': 'Wolfram',   'chemical_symbol': 'W',  'unit': 'TMF', 'quoted_in': 'AM'},
    {'name': 'Bismuto',   'chemical_symbol': 'Bi', 'unit': 'LF',  'quoted_in': 'AM'},
    {'name': 'Oro',       'chemical_symbol': 'Au', 'unit': 'OT',  'quoted_in': 'LFIX'},
    {'name': 'Plata',     'chemical_symbol': 'Ag', 'unit': 'OT',  'quoted_in': 'LFIX'},
)

def _normalize_separators(digits: str) -> str:
    '''
    Rewrites a numeric string so Python can parse it, whichever convention the
    source used.

    The rule is positional: the rightmost separator is the decimal mark and the
    other one groups thousands. When only one kind appears, repetition decides —
    two dots cannot both be decimals, so they are grouping.

    Args:
        digits (str): String holding only digits, dots and commas.

    Returns:
        str: The same number with a single dot as the decimal mark.
    '''
    has_dot = '.' in digits
    has_comma = ',' in digits

    if has_dot and has_comma:
        if digits.rfind('.') > digits.rfind(','):
            return digits.replace(',', '')
        return digits.replace('.', '').replace(',', '.')

    if has_dot:
        # Multiple dots → european thousands grouping; single dot → anglo decimal.
        return digits.replace('.', '') if digits.count('.') > 1 else digits

    if has_comma:
        # Multiple commas → anglo thousands grouping; single comma → european decimal.
        return digits.replace(',', '') if digits.count(',') > 1 else digits.replace(',', '.')

    return digits


def clean_currency_pro(value: Any) -> float:
    '''
    Normalizes mixed numeric cell values from CSV/Excel into a float.

    Detects anglo (`1,234.56`) vs european (`1.234,56`) conventions by the
    position of the rightmost separator. Earlier versions stripped every `.`
    blindly, which corrupted anglo decimals such as `17.54` into `1754`.

    Args:
        value (Any): Raw cell value (str, int, float, None, NaN).

    Returns:
        float: Parsed numeric value; 0.0 for empty/null/non-numeric input.
    '''
    if pd.isna(value):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)

    str_val = str(value).strip()
    if str_val in ('', '-'):
        return 0.0

    is_negative = str_val.lstrip().startswith('-')
    str_val = re.sub(r'[^\d.,]', '', str_val)
    if not str_val:
        return 0.0

    try:
        result = float(_normalize_separators(str_val))
    except ValueError:
        return 0.0

    return -result if is_negative and result > 0 else result

def _parse_mining_file(
    file_content: bytes,
    file_name: str,
    delimiter: str
) -> pd.DataFrame:
    ''' Parses the uploaded file and validates required columns. '''
    file_extension = file_name.split('.')[-1].lower()

    if file_extension == 'csv':
        df = pd.read_csv(io.BytesIO(file_content), sep=delimiter)
    elif file_extension in ['xls', 'xlsx']:
        df = pd.read_excel(io.BytesIO(file_content))
    else:
        raise ValueError('Unsupported file format. Please upload a .csv or .xlsx file.')

    # Standardize column names to lowercase and strip spaces for safe matching
    df.columns = df.columns.str.strip().str.lower()

    required_columns = ['fecha', 'mineral', 'simbolo', 'unidad', 'referencia']
    missing_cols = [col for col in required_columns if col not in df.columns]

    if missing_cols:
        raise ValueError(f'Missing required columns in file: {missing_cols}')

    df['fecha'] = pd.to_datetime(df['fecha'], dayfirst=True).dt.date
    return df

def _extract_prices(row: pd.Series) -> tuple:
    ''' Extracts the min and max prices based on the market reference. '''
    reference = str(row.get('referencia', '')).strip().upper()

    if reference == 'LME':
        target_cols = ['cash bid', 'cash offer', 'month bid', 'month offer']
    elif reference in ['AM']:
        target_cols = ['low', 'high']
    elif reference in ['LFIX']:
        target_cols = ['low']
    else:
        return 0.0, 0.0

    # Clean and collect valid numeric values
    vals = [
        clean_currency_pro(row.get(c)) for c in target_cols
        if c in row and pd.notna(row.get(c))
    ]
    valid_vals = [v for v in vals if v > 0]

    if not valid_vals:
        return 0.0, 0.0

    return min(valid_vals), max(valid_vals)

def _process_single_mineral_row(
    db: Session,
    row: pd.Series
) -> bool:
    ''' 
        Handles the upsert logic for a single mineral and its price.
        Returns True if a new price was processed, False if it was skipped.
    '''
    mineral_name = str(row['mineral']).strip()
    mineral = db.query(Mineral).filter(Mineral.name == mineral_name).first()

    # Create or update the mineral record
    if not mineral:
        mineral = Mineral(
            name = mineral_name,
            unit = str(row.get('unidad', '')).strip(),
            chemical_symbol = str(row.get('simbolo', '')).strip(),
            quoted_in = str(row.get('referencia', '')).strip().upper(),
            method = str(row.get('method', '')).strip()
        )
        db.add(mineral)
        db.flush()
    else:
        # Update existing metadata in case it changed or was empty
        mineral.chemical_symbol = str(row.get('simbolo', '')).strip()
        mineral.quoted_in = str(row.get('referencia', '')).strip().upper()
        mineral.method = str(row.get('method', '')).strip()

    # Calculate price_low and price_high dynamically using helper
    price_low, price_high = _extract_prices(row)

    existing = db.query(MiningPrice).filter(
        MiningPrice.mineral_id == mineral.id,
        MiningPrice.date == row['fecha']
    ).first()

    if not existing:
        new_price = MiningPrice(
            mineral_id = mineral.id,
            date = row['fecha'],
            price_low = price_low,
            price_high = price_high
        )
        db.add(new_price)
        return True

    return False


async def process_mining_etl_service(
    db: Session,
    file_content: bytes,
    file_name: str,
    delimiter: str = ','
) -> Dict[str, Any]:
    ''' 
        Optimized ETL logic using Pandas for both CSV and Excel parsing with
        dynamic reference mapping.
    '''
    try:
        df = _parse_mining_file(file_content, file_name, delimiter)
    except ValueError as ve:
        error_msg = f'Validation Error processing file: {ve}'
        logger.error(error_msg, exc_info = True)
        raise InvalidInputError(detail = str(ve)) from ve
    except Exception as e:
        error_msg = f'Error processing file: {e}'
        logger.error(error_msg, exc_info = True)
        raise InvalidInputError(
            detail = 'Invalid/corrupt file format. Please ensure it is a valid CSV or Excel file.'
        ) from e

    processed, skipped = 0, 0

    with db.begin_nested():
        for _, row in df.iterrows():
            # Orchestrate the row processing cleanly
            if _process_single_mineral_row(db, row):
                processed += 1
            else:
                skipped += 1

    db.commit()

    return {
        'status': MiningStatus.SUCCESS,
        'result': MiningResult.PRICES_ETL_COMPLETED,
        'processed_records': processed,
        'skipped_records': skipped
    }

async def get_all_prices_service(db: Session) -> List[Dict[str, Any]]:
    '''
    Retrieves every quotation with the metadata of its mineral.

    Goes through the store so it answers on either backend. The mineral's unit,
    symbol and market come from OFFICIAL_MINERALS, the published catalogue: on
    DynamoDB the table holds only the name, and the bulletins are built from
    that catalogue anyway.

    Args:
        db (Session): Database session; ignored when running on DynamoDB.

    Returns:
        List[Dict[str, Any]]: Rows matching MiningPriceResponseSchema.
    '''
    catalog = {
        normalize_name(entry['name']): entry for entry in OFFICIAL_MINERALS
    }
    rows: List[Dict[str, Any]] = []
    for record in all_quotations(db = db):
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

def _calculate_advanced_kpis(
    data: List[Dict[str, Any]],
    prev_data: List[Dict[str, Any]]
) -> Dict[str, Any]:
    '''
    Calculates YoY variations by mapping exactly Month, Department, and Municipality.
    Aggregates annual performance to prevent single-month anomalies in Top 5 KPIs.

    Args:
        data (List[Dict[str, Any]]): Current period data to be evaluated.
        prev_data (List[Dict[str, Any]]): Previous period data for baseline comparison.

    Returns:
        Dict[str, Any]: A dictionary containing the detailed records and aggregated KPIs.
    '''
    comparison_map = {
        (d['month'], d['department'], d['municipality']): d for d in prev_data
    }

    total_period = Decimal('0')
    muni_agg = defaultdict(lambda: {'actual': Decimal('0'), 'pasado': Decimal('0')})

    for row in data:
        actual = Decimal(str(row['total_recaudado_bob']))
        total_period += actual

        row['variacion_monto_bob'] = 0.0
        row['variacion_porcentaje'] = 0.0

        m_key = (row['department'], row['municipality'])
        muni_agg[m_key]['actual'] += actual

        prev = comparison_map.get((row['month'], row['department'], row['municipality']))
        if prev and Decimal(str(prev['total_recaudado_bob'])) > 0:
            pasado = Decimal(str(prev['total_recaudado_bob']))
            muni_agg[m_key]['pasado'] += pasado

            row['variacion_monto_bob'] = float(actual - pasado)
            porc = ((actual - pasado) / pasado) * Decimal('100')

            porc = max(-MAX_VARIATION_PERCENT, min(porc, MAX_VARIATION_PERCENT))
            row['variacion_porcentaje'] = float(porc.quantize(_PERCENT_QUANTUM,
                                        rounding = ROUND_HALF_UP))

    annual_kpis = []
    for (dept, muni), vals in muni_agg.items():
        # Significance filter: Ignore if previous baseline was < 5000 Bs (statistical noise)
        if vals['pasado'] > MIN_BASELINE_BOB:
            porc = ((vals['actual'] - vals['pasado']) / vals['pasado']) * Decimal('100')
            porc = max(-MAX_VARIATION_PERCENT, min(porc, MAX_VARIATION_PERCENT))

            annual_kpis.append({
                'department': dept,
                'municipality': muni,
                'variacion_porcentaje': float(porc.quantize(_PERCENT_QUANTUM,
                                        rounding = ROUND_HALF_UP))
            })

    return {
        'detailed_records': data,
        'summary_kpis': {
            'total_recaudado_periodo': float(total_period),
            'municipios_destacados': sorted(
                [d for d in annual_kpis if d['variacion_porcentaje'] > 0],
                key = lambda x: x['variacion_porcentaje'],
                reverse = True
            )[:KPI_TOP_ROWS],
            'alerta_caida_critica': sorted(
                [d for d in annual_kpis
                 if d['variacion_porcentaje'] < CRITICAL_DROP_PERCENT],
                key = lambda x: x['variacion_porcentaje']
            )[:KPI_TOP_ROWS]
        }
    }

@handle_service_errors('MINING_ANALYSIS')
async def get_royalties_summary_service(
    db: Session,
    year: int = None,
    quarter: int = None, # pylint: disable=unused-argument
    request: Request = None, # pylint: disable=unused-argument
    current_user: str = None # pylint: disable=unused-argument
) -> Dict[str, Any]:
    '''
        Aggregates financial metrics.
        Returns data for the target year AND the previous year to allow
        dynamic YoY calculation in frontend.
    '''
    def fetch_data(target_year: int) -> Query:
        query = db.query(
            RoyaltyPayment.year.label('year'),
            RoyaltyPayment.month.label('month'),
            Department.name.label('department'),
            Municipality.name.label('municipality'),
            func.sum(RoyaltyPayment.total_collected_bob).label('total_bob'),
            func.sum(RoyaltyPayment.commission_bob).label('comision_bob'),
            func.sum(RoyaltyPayment.subtotal_bob).label('subtotal_bob'),
            func.sum(RoyaltyPayment.gov_dept_bob).label('dept_bob'),
            func.sum(RoyaltyPayment.gov_muni_bob).label('muni_bob'),
            func.sum(RoyaltyPayment.total_collected_usd).label('total_usd'),
            func.sum(RoyaltyPayment.commission_usd).label('comision_usd'),
            func.sum(RoyaltyPayment.subtotal_usd).label('subtotal_usd'),
            func.sum(RoyaltyPayment.gov_dept_usd).label('dept_usd'),
            func.sum(RoyaltyPayment.gov_muni_usd).label('muni_usd')
        ).join(
            Municipality, RoyaltyPayment.municipality_id == Municipality.id
        ).join(
            Department, Municipality.department_id == Department.id
        )

        if target_year:
            query = query.filter(RoyaltyPayment.year.in_([target_year, target_year - 1]))

        return query.group_by(
            RoyaltyPayment.year,
            RoyaltyPayment.month,
            Department.name,
            Municipality.name
        ).all()

    results = fetch_data(year)

    formatted_data = [
        {
            'year': int(r.year),
            'month': int(r.month),
            'department': r.department,
            'municipality': r.municipality,
            'total_recaudado_bob': float(r.total_bob),
            'comision_bob': float(r.comision_bob),
            'subtotal_bob': float(r.subtotal_bob),
            'distribucion_dept_bob': float(r.dept_bob),
            'distribucion_muni_bob': float(r.muni_bob),
            'total_recaudado_usd': float(r.total_usd),
            'comision_usd': float(r.comision_usd),
            'subtotal_usd': float(r.subtotal_usd),
            'distribucion_dept_usd': float(r.dept_usd),
            'distribucion_muni_usd': float(r.muni_usd),
            'variacion_monto_bob': 0.0,
            'variacion_porcentaje': 0.0
        } for r in results
    ]

    total_periodo = sum(d['total_recaudado_bob'] for d in formatted_data if d['year'] == year) \
                    if year else 0

    return {
        'status': MiningStatus.SUCCESS,
        'result': MiningResult.ROYALTY_SUMMARY_RETRIEVED,
        'data': {
            'detailed_records': formatted_data,
            'summary_kpis': {
                'total_recaudado_periodo': total_periodo,
                'municipios_destacados': [],
                'alerta_caida_critica': []
            }
        }
    }

@handle_service_errors('MINING_ANALYSIS')
async def get_transactions_summary_service(
    db: Session,
    year: int = None
) -> Dict[str, Any]:
    '''
    Retrieves aggregated transactions data joined with companies.
    
    Args:
        db (Session): Database session.
        year (int, optional): Fiscal year to filter by.
        
    Returns:
        Dict[str, Any]: Dictionary containing status, message, and formatted transaction data.
    '''
    query = db.query(
        Company.name.label('company_name'),
        Company.nit.label('nit'),
        RoyaltyTransaction.year.label('year'),
        RoyaltyTransaction.month.label('month'),
        Municipality.name.label('municipality'),
        func.sum(RoyaltyTransaction.amount_paid_bob).label('amount_paid_bob'),
        func.sum(RoyaltyTransaction.amount_paid_usd).label('amount_paid_usd')
    ).join(
        Company, RoyaltyTransaction.company_id == Company.id
    ).join(
        Municipality, RoyaltyTransaction.municipality_id == Municipality.id
    )

    if year:
        query = query.filter(RoyaltyTransaction.year == year)

    results = query.group_by(
        Company.name,
        Company.nit,
        RoyaltyTransaction.year,
        RoyaltyTransaction.month,
        Municipality.name
    ).all()

    formatted_data = [
        {
            'company_name': r.company_name,
            'nit': r.nit,
            'year': int(r.year),
            'month': int(r.month),
            'municipality': r.municipality,
            'amount_paid_bob': float(r.amount_paid_bob),
            'amount_paid_usd': float(r.amount_paid_usd)
        } for r in results
    ]

    return {
        'status': MiningStatus.SUCCESS,
        'result': MiningResult.TRANSACTIONS_RETRIEVED,
        'data': formatted_data
    }
