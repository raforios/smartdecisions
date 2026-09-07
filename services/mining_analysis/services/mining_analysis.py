'''
    Mining Analysis Business Logic Services
'''
import calendar
from dataclasses import dataclass
from collections import defaultdict
from datetime import date
import io
import re
import unicodedata
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, Any, List, Optional, Tuple
from fastapi import Request
import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session
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
from services.prices_store import (
    all_quotations,
    average_low,
    date_bounds,
    latest_prices_before,
    list_minerals
)


# Required, not optional: a fallback written in code is still a number the
# code chose.
ENV_VARS = load_and_validate_env_vars({
    'MAX_FALLBACK_PERIODS': int,
    'CHANGE_DECIMALS': int,
})

# Decimals a published percentage carries.
CHANGE_DECIMALS = ENV_VARS['CHANGE_DECIMALS']


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

def _parse_mining_file(file_content: bytes, file_name: str, delimiter: str) -> pd.DataFrame:
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

def _process_single_mineral_row(db: Session, row: pd.Series) -> bool:
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
        _normalize_name(entry['name']): entry for entry in OFFICIAL_MINERALS
    }
    rows: List[Dict[str, Any]] = []
    for record in all_quotations(db = db):
        entry = catalog.get(_normalize_name(record.mineral_name), {})
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

            porc = max(Decimal('-999.99'), min(porc, Decimal('999.99')))
            row['variacion_porcentaje'] = float(porc.quantize(Decimal('1.00'),
                                        rounding = ROUND_HALF_UP))

    annual_kpis = []
    for (dept, muni), vals in muni_agg.items():
        # Significance filter: Ignore if previous baseline was < 5000 Bs (statistical noise)
        if vals['pasado'] > Decimal('5000'):
            porc = ((vals['actual'] - vals['pasado']) / vals['pasado']) * Decimal('100')
            porc = max(Decimal('-999.99'), min(porc, Decimal('999.99')))

            annual_kpis.append({
                'department': dept,
                'municipality': muni,
                'variacion_porcentaje': float(porc.quantize(Decimal('1.00'),
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
            )[:5],
            'alerta_caida_critica': sorted(
                [d for d in annual_kpis if d['variacion_porcentaje'] < -20],
                key = lambda x: x['variacion_porcentaje']
            )[:5]
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
    def fetch_data(target_year: int):
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


# --- OFFICIAL REPORTS (DAILY + BIWEEKLY) ---

def _normalize_name(name: str) -> str:
    '''
    Lower-cases and strips accents so 'Estaño' / 'ESTANO' / 'estano' all match.

    Accent stripping is intentional: source files occasionally arrive with
    ASCII-only mineral names from older OCR pipelines.
    '''
    base = unicodedata.normalize('NFKD', str(name).strip().lower())
    return ''.join(c for c in base if not unicodedata.combining(c))


def _biweekly_period_bounds(year: int, month: int, half: int) -> Tuple[date, date]:
    '''
    Returns (period_start, period_end) for the requested half of the month.
    Half 1 covers days 1-15, half 2 covers day 16 through month end.
    '''
    if half not in (1, 2):
        raise InvalidInputError(detail = 'half must be 1 (days 1-15) or 2 (16-end).')
    if half == 1:
        return date(year, month, 1), date(year, month, 15)
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 16), date(year, month, last_day)


def _prev_biweekly_period(year: int, month: int, half: int) -> Tuple[int, int, int]:
    '''
    Returns (prev_year, prev_month, prev_half) — the period immediately before
    the requested one. Wraps to December of the previous year when needed.
    '''
    if half == 2:
        return year, month, 1
    if month == 1:
        return year - 1, 12, 2
    return year, month - 1, 2


def _resolve_mineral_id_map(db: Session) -> Dict[str, str]:
    '''
    Builds {normalized_name: mineral_id} for the official catalog. Minerals
    missing from the catalog are simply absent from the map; callers must
    handle that case by emitting a fallback row.
    '''
    return {
        _normalize_name(record.name): record.mineral_id
        for record in list_minerals(db = db)
    }


def _empty_daily_row(catalog: Dict[str, str], ref_date: date) -> Dict[str, Any]:
    '''
    Returns a placeholder row used when no price exists for the mineral at all.
    '''
    return {
        'mineral': catalog['name'],
        'chemical_symbol': catalog['chemical_symbol'],
        'unit': catalog['unit'],
        'quoted_in': catalog['quoted_in'],
        'price_low': 0.0,
        'price_high': 0.0,
        'price_date': ref_date,
        'previous_price_low': 0.0,
        'previous_price_date': None,
        'change_pct': 0.0,
        'is_fallback': True,
    }


@handle_service_errors('MINING_ANALYSIS')
async def get_daily_report_service(
    db: Session,
    ref_date: date
) -> Dict[str, Any]:
    '''
    Builds the daily mineral report (template Minerales_01).

    For every mineral in OFFICIAL_MINERALS, picks the most recent t_mining_prices
    row whose date is <= ref_date. `is_fallback` is True when no entry exists on
    ref_date itself and an older record was used.

    Args:
        db (Session): Database session.
        ref_date (date): Reference date for the report (typically "today").

    Returns:
        Dict[str, Any]: Payload matching DailyReportResponse shape.
    '''
    mineral_ids = _resolve_mineral_id_map(db)
    rows: List[Dict[str, Any]] = []

    for catalog in OFFICIAL_MINERALS:
        normalized = _normalize_name(catalog['name'])
        mineral_id = mineral_ids.get(normalized)
        if mineral_id is None:
            rows.append(_empty_daily_row(catalog, ref_date))
            continue

        # Through the store, so the report reads the same on either backend.
        latest_two = latest_prices_before(str(mineral_id), ref_date, 2, db = db)
        if not latest_two:
            rows.append(_empty_daily_row(catalog, ref_date))
            continue

        price = latest_two[0]
        prev = latest_two[1] if len(latest_two) > 1 else None
        price_low = float(price.price_low or 0)
        prev_low = float(prev.price_low or 0) if prev is not None else 0.0
        change_pct = (
            ((price_low - prev_low) / prev_low) * 100
            if prev is not None and prev_low > 0
            else 0.0
        )

        rows.append({
            'mineral': catalog['name'],
            'chemical_symbol': catalog['chemical_symbol'],
            'unit': catalog['unit'],
            'quoted_in': catalog['quoted_in'],
            'price_low': price_low,
            'price_high': float(price.price_high or price.price_low or 0),
            'price_date': price.date,
            'previous_price_low': prev_low,
            'previous_price_date': prev.date if prev is not None else None,
            'change_pct': round(change_pct, CHANGE_DECIMALS),
            'is_fallback': price.date != ref_date,
        })

    return {
        'status': MiningStatus.SUCCESS,
        'result': MiningResult.DAILY_REPORT_GENERATED,
        'ref_date': ref_date,
        'rows': rows,
    }


def _compute_biweekly_average(
    db: Session,
    mineral_id: int,
    period_start: date,
    period_end: date
) -> Optional[Tuple[float, int]]:
    '''
    Returns (avg_price_low, sample_size) for the mineral within the window,
    or None when no day has data inside the period.

    sample_size is the number of distinct days with a non-null price_low; the
    mean divides by that exact count, matching the spec "se aplica el promedio
    para ese número de días".
    '''
    # Delegated to the store so the same rule holds on either backend: the
    # relational one aggregates with SQL, DynamoDB reads the partition and
    # averages in Python. This function no longer knows which is active.
    return average_low(str(mineral_id), period_start, period_end, db = db)


# How far back the report looks for the last published quotation of a mineral,
# in biweekly periods. Two years is generous for "el del periodo anterior que se
# tenga" and still bounds the search on a mineral that was never quoted.
_MAX_FALLBACK_PERIODS: int = ENV_VARS['MAX_FALLBACK_PERIODS']


@dataclass(frozen = True)
class _BiweeklyAverage:
    '''
    One mineral's figure for a biweekly report, and which window produced it.

    `is_fallback` is True when the number does not belong to the requested
    period: either the mineral is absent from the catalogue, or the report had
    to walk back to an earlier period to find a quotation. The UI marks those
    rows so a reader never takes an old price for a current one.
    '''
    avg_price_low: float
    sample_size: int
    period_start: date
    period_end: date
    is_fallback: bool

    def as_row(self) -> Dict[str, Any]:
        '''
        Renders the figure as the keys the report payload carries.

        Returns:
            Dict[str, Any]: Fields merged into the mineral's row.
        '''
        return {
            'avg_price_low': self.avg_price_low,
            'sample_size': self.sample_size,
            'period_start': self.period_start,
            'period_end': self.period_end,
            'is_fallback': self.is_fallback,
        }


def _average_with_fallback(
    db: Session,
    mineral_id: Optional[str],
    period: Tuple[int, int, int]
) -> _BiweeklyAverage:
    '''
    Returns the mineral's average for the requested period, or the most recent
    earlier one when that period has no data.

    Args:
        db (Session): Database session.
        mineral_id (str | None): Mineral identifier, None when the catalogue
            has no such mineral.
        period (tuple[int, int, int]): Requested (year, month, half).

    Returns:
        _BiweeklyAverage: The figure and the window it actually came from.
    '''
    year, month, half = period
    start, end = _biweekly_period_bounds(year, month, half)

    if mineral_id is None:
        return _BiweeklyAverage(0.0, 0, start, end, is_fallback = True)

    calc = _compute_biweekly_average(db, mineral_id, start, end)
    if calc is not None:
        return _BiweeklyAverage(calc[0], calc[1], start, end, is_fallback = False)

    current = period
    for _ in range(_MAX_FALLBACK_PERIODS):
        current = _prev_biweekly_period(*current)
        past_start, past_end = _biweekly_period_bounds(*current)
        calc = _compute_biweekly_average(db, mineral_id, past_start, past_end)
        if calc is not None:
            return _BiweeklyAverage(
                calc[0], calc[1], past_start, past_end, is_fallback = True
            )

    return _BiweeklyAverage(0.0, 0, start, end, is_fallback = True)


@handle_service_errors('MINING_ANALYSIS')
async def get_biweekly_report_service(
    db: Session,
    year: int,
    month: int,
    half: int
) -> Dict[str, Any]:
    '''
    Builds the biweekly official report (template Minerales_02).

    Period halves are fixed: half=1 → days 1-15, half=2 → days 16-end. Returns
    the simple mean of price_low over the days that have data inside the
    window. When a mineral has no data in the requested period, walks back one
    biweekly period at a time looking for the most recent value (matching
    "se muestra el del periodo anterior que se tenga"). The lookback is capped
    at 24 periods (~1 year) to avoid pathological scans.

    Args:
        db (Session): Database session.
        year (int): Calendar year of the report.
        month (int): Month (1-12) of the report.
        half (int): 1 for days 1-15, 2 for 16-end.

    Returns:
        Dict[str, Any]: Payload matching BiweeklyReportResponse shape.
    '''
    period_start, period_end = _biweekly_period_bounds(year, month, half)
    mineral_ids = _resolve_mineral_id_map(db)
    rows: List[Dict[str, Any]] = [
        {
            'mineral': catalog['name'],
            'chemical_symbol': catalog['chemical_symbol'],
            'unit': catalog['unit'],
            'quoted_in': catalog['quoted_in'],
            **_average_with_fallback(
                db,
                mineral_ids.get(_normalize_name(catalog['name'])),
                (year, month, half)
            ).as_row()
        }
        for catalog in OFFICIAL_MINERALS
    ]

    return {
        'status': MiningStatus.SUCCESS,
        'result': MiningResult.BIWEEKLY_REPORT_GENERATED,
        'year': year,
        'month': month,
        'half': half,
        'period_start': period_start,
        'period_end': period_end,
        'rows': rows,
    }


def _iter_biweekly_periods(period_from: date, period_to: date):
    '''
    Yields (year, month, half) tuples covering every biweekly period between
    `period_from` and `period_to` (inclusive) in chronological order.
    '''
    year, month = period_from.year, period_from.month
    half = 1 if period_from.day <= 15 else 2
    end_year, end_month = period_to.year, period_to.month
    end_half = 1 if period_to.day <= 15 else 2

    while (year, month, half) <= (end_year, end_month, end_half):
        yield year, month, half
        if half == 1:
            half = 2
        else:
            half = 1
            if month == 12:
                month = 1
                year += 1
            else:
                month += 1


@handle_service_errors('MINING_ANALYSIS')
async def get_biweekly_history_service(
    db: Session,
    period_from: Optional[date] = None,
    period_to: Optional[date] = None,
) -> Dict[str, Any]:
    '''
    Returns every biweekly period inside the requested window that has at
    least one cotización for any official mineral.

    When `period_from`/`period_to` are omitted, the bounds are derived from
    the MIN/MAX dates in t_mining_prices so the caller automatically sees the
    full history.

    Args:
        db (Session): Database session.
        period_from (Optional[date]): Inclusive lower bound. Defaults to the
            earliest cotización in storage.
        period_to (Optional[date]): Inclusive upper bound. Defaults to the
            latest cotización in storage.

    Returns:
        Dict[str, Any]: Payload matching BiweeklyHistoryResponse shape.
    '''
    oldest, newest = date_bounds(db = db)
    if oldest is None:
        today = date.today()
        return {
            'status': MiningStatus.SUCCESS,
            'result': MiningResult.BIWEEKLY_HISTORY_GENERATED,
            'period_from': period_from or today,
            'period_to': period_to or today,
            'periods': [],
        }

    period_from = period_from or oldest
    period_to = period_to or newest
    if period_from > period_to:
        raise InvalidInputError(detail = 'period_from must be <= period_to.')

    periods: List[Dict[str, Any]] = []
    for year, month, half in _iter_biweekly_periods(period_from, period_to):
        snapshot = await get_biweekly_report_service(db, year, month, half)
        # Skip purely-fallback snapshots — they carry no information about
        # the requested period itself, only about a recovered prior one.
        if all(row['is_fallback'] for row in snapshot['rows']):
            continue
        periods.append({
            'year': year,
            'month': month,
            'half': half,
            'period_start': snapshot['period_start'],
            'period_end': snapshot['period_end'],
            'rows': snapshot['rows'],
        })

    return {
        'status': MiningStatus.SUCCESS,
        'result': MiningResult.BIWEEKLY_HISTORY_GENERATED,
        'period_from': period_from,
        'period_to': period_to,
        'periods': periods,
    }


def ensure_official_minerals(db: Session) -> int:
    '''
    Idempotent seed: inserts any official mineral missing from t_minerals.

    Returns the number of rows actually inserted. Existing rows are left
    untouched to preserve any operator-curated metadata.
    '''
    existing = {_normalize_name(r.name) for r in db.query(Mineral.name).all()}
    inserted = 0
    for catalog in OFFICIAL_MINERALS:
        if _normalize_name(catalog['name']) in existing:
            continue
        db.add(Mineral(
            name = catalog['name'],
            unit = catalog['unit'],
            chemical_symbol = catalog['chemical_symbol'],
            quoted_in = catalog['quoted_in'],
            method = None,
        ))
        inserted += 1
    if inserted:
        db.commit()
    return inserted
