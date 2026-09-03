'''
    ETL Services for Mining Royalties (Data Engineering)
'''
import io
import zipfile
import unicodedata
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, Tuple, List
import pandas as pd
from sqlalchemy.orm import Session
from models.mining_analysis import (
    Municipality, RoyaltyPayment, Company, RoyaltyTransaction
)
from schemas.mining_analysis import MiningResult, MiningStatus
from services.utils import handle_service_errors
from services.logger_config import custom_logger as logger


def normalize_string(
    val: Any
) -> str:
    ''' Removes accents, special characters, and converts to uppercase. '''
    if not isinstance(val, str) or pd.isna(val):
        return ""
    normalized = unicodedata.normalize('NFD', str(val)).encode('ascii', 'ignore').decode('utf-8')
    return normalized.upper().strip()


def excel_date_to_py_date(
    excel_date: Any
) -> date:
    ''' Converts an Excel serial date number or string into a Python date. '''
    if pd.isna(excel_date):
        return date.today()
    if isinstance(excel_date, (datetime, pd.Timestamp)):
        return excel_date.date()
    if isinstance(excel_date, str):
        try:
            return pd.to_datetime(excel_date).date()
        except (ValueError, TypeError):
            pass
    try:
        delta_days = pd.to_timedelta(float(excel_date), unit='D')
        return (pd.to_datetime('1899-12-30') + delta_days).date()
    except (ValueError, TypeError) as exc:
        error_msg = f'Failed to parse Excel date {excel_date}: {exc}'
        logger.warning(error_msg)
        return date.today()


def build_municipality_maps(
    db_session: Session,
    summary_df: pd.DataFrame
) -> Tuple[Dict[int, int], List[Dict[str, Any]]]:
    '''
        Builds an in-memory alias map mapping SIN Excel codes to Official Municipality IDs.
        STRICT MATCHING: Only matches by official_code to prevent homonym collisions 
        (e.g., matching the wrong 'San Pedro').
    '''
    munis = db_session.query(Municipality).all()
    # Aseguramos que el código en el diccionario sea un entero para evitar
    # fallos de cruce 'str' vs 'int'
    code_map = {}
    for m in munis:
        try:
            code_map[int(m.official_code)] = m.id
        except (ValueError, TypeError):
            continue

    alias_map = {}
    rejected_records = []
    excluded_kws = ['SUB TOTAL', 'TOTAL', 'GAD', 'MINISTERIO']

    for _, row in summary_df.iterrows():
        raw_name = str(row.get('Municipio Productor', '')).strip().upper()
        if pd.isna(row.get('Cod. Muni. Prod.')) or any(kw in raw_name for kw in excluded_kws):
            continue

        try:
            sin_code = int(row['Cod. Muni. Prod.'])
        except (ValueError, TypeError):
            continue

        if sin_code in code_map:
            alias_map[sin_code] = code_map[sin_code]
        else:
            # RECHAZO ESTRICTO: Eliminamos la búsqueda difusa por nombre para evitar colisiones.
            rejected_records.append({
                'Codigo_SIN': sin_code,
                'Municipio_SIN': raw_name,
                'Motivo': f'Cruce estricto fallido. El código oficial {
                    sin_code} no existe en la tabla t_municipalities.'
            })

    return alias_map, rejected_records


def get_or_create_companies(
    db_session: Session,
    details_df: pd.DataFrame
) -> Dict[str, int]:
    ''' Caches existing companies and creates new ones. Returns a NIT -> ID mapping. '''
    nit_map = {}
    with db_session.begin_nested():
        companies = db_session.query(Company).all()
        for comp in companies:
            nit_map[comp.nit] = comp.id

        companies_df = details_df[['Nit', 'Razon Social']].drop_duplicates().dropna(subset=['Nit'])

        for _, row in companies_df.iterrows():
            try:
                nit_value = str(int(row['Nit'])).strip()
            except ValueError:
                nit_value = str(row['Nit']).strip()

            comp_name = str(row['Razon Social']).strip()

            if nit_value and nit_value.lower() != 'nan' and 'TOTAL' not in comp_name.upper():
                if nit_value not in nit_map:
                    new_comp = Company(nit=nit_value, name=comp_name)
                    db_session.add(new_comp)
                    db_session.flush()
                    nit_map[nit_value] = new_comp.id
    return nit_map


def load_transactions(
    db_session: Session,
    details_df: pd.DataFrame,
    exchange_rate: Decimal,
    nit_map: Dict[str, int],
    alias_map: Dict[int, int]
) -> int:
    ''' Loads individual transactions leveraging in-memory mapping. '''
    processed_count = 0

    with db_session.begin_nested():
        for _, row in details_df.iterrows():
            if pd.isna(row.get('Nit')) or pd.isna(row.get('Mun. Prod.')):
                continue

            try:
                nit_val = str(int(row['Nit'])).strip()
                sin_code = int(row['Mun. Prod.'])
            except (ValueError, TypeError):
                continue

            if 'TOTAL' in str(row.get('Razon Social', '')).upper():
                continue

            comp_id = nit_map.get(nit_val)
            muni_id = alias_map.get(sin_code)

            if not comp_id or not muni_id:
                continue

            amt_bob = Decimal(str(row.get('Monto Pagado', 0))).quantize(Decimal('1.0000'),
                    rounding=ROUND_HALF_UP)

            db_session.add(RoyaltyTransaction(
                company_id = comp_id,
                municipality_id = muni_id,
                order_number = str(row.get('Numero de Orden', '')).strip(),
                form_code = str(row.get('Cod Form.', '')).strip(),
                bank_code = str(row.get('Código Banco', '')).strip(),
                payment_date = excel_date_to_py_date(row['Fecha Doc.']),
                year = int(row['Año']) if not pd.isna(row['Año']) else date.today().year,
                month = int(row['Periodo']) if not pd.isna(row['Periodo']) else date.today().month,
                amount_paid_bob = amt_bob,
                amount_paid_usd = amt_bob / exchange_rate
            ))
            processed_count += 1
        db_session.flush()
    return processed_count


def load_summary(
    db_session: Session,
    summary_df: pd.DataFrame,
    exchange_rate: Decimal,
    period_date: date,
    alias_map: Dict[int, int]
) -> Tuple[int, int]:
    ''' Loads the monthly summary using the alias map. '''
    counts = {'processed': 0, 'updated': 0}
    seen_munis = set()

    def to_decimal(value: Any) -> Decimal:
        return Decimal(str(value or 0)).quantize(Decimal('1.0000'), rounding=ROUND_HALF_UP)

    with db_session.begin_nested():
        for _, row in summary_df.iterrows():
            try:
                sin_code = int(row['Cod. Muni. Prod.'])
            except (ValueError, TypeError, KeyError):
                continue

            muni_id = alias_map.get(sin_code)
            if not muni_id or muni_id in seen_munis:
                continue

            seen_munis.add(muni_id)

            fact_record = db_session.query(RoyaltyPayment).filter(
                RoyaltyPayment.municipality_id == muni_id, RoyaltyPayment.period_date == period_date
            ).first()

            if not fact_record:
                fact_record = RoyaltyPayment(
                    municipality_id = muni_id,
                    period_date = period_date,
                    year = period_date.year,
                    month = period_date.month,
                    day = 1
                )
                db_session.add(fact_record)
                counts['processed'] += 1
            else:
                counts['updated'] += 1

            fact_record.total_collected_bob = to_decimal(row['Total Recaudado'])
            fact_record.commission_bob = to_decimal(row['Comisión'])
            fact_record.subtotal_bob = to_decimal(row['Subtotal'])
            fact_record.gov_dept_bob = to_decimal(row['Gob. Deptal.'])
            fact_record.gov_muni_bob = to_decimal(row['Gob. Municipal'])

            fact_record.total_collected_usd = fact_record.total_collected_bob / exchange_rate
            fact_record.commission_usd = fact_record.commission_bob / exchange_rate
            fact_record.subtotal_usd = fact_record.subtotal_bob / exchange_rate
            fact_record.gov_dept_usd = fact_record.gov_dept_bob / exchange_rate
            fact_record.gov_muni_usd = fact_record.gov_muni_bob / exchange_rate

        db_session.flush()
    return counts['processed'], counts['updated']


@handle_service_errors('MINING_ANALYSIS')
async def process_royalties_excel_service(
    db_session: Session,
    file_content: bytes,
    exchange_rate: Decimal
) -> Dict[str, Any]:
    ''' Extracts, transforms and loads the source files natively matching official records. '''
    try:
        excel_data = pd.ExcelFile(io.BytesIO(file_content), engine='openpyxl')
    except (ValueError, zipfile.BadZipFile) as exc:
        error_msg = f'Failed to read as xlsx, trying xls engine. Details: {exc}'
        logger.warning(error_msg)
        excel_data = pd.ExcelFile(io.BytesIO(file_content), engine='xlrd')

    sheet_det = next((s for s in excel_data.sheet_names if 'DETALLE' in s.upper()), None)
    sheet_sum = next((s for s in excel_data.sheet_names if 'COPARTICIPACI' in s.upper()), None)

    if not sheet_det or not sheet_sum:
        raise ValueError('The file does not contain the required sheets.')

    details_df = pd.read_excel(excel_data, sheet_name = sheet_det, skiprows=6).dropna(
        subset = ['Nit', 'Año', 'Periodo'])
    summary_df = pd.read_excel(excel_data, sheet_name = sheet_sum, skiprows=6)

    period = date(int(details_df['Año'].mode()[0]), int(details_df['Periodo'].mode()[0]), 1)

    # --- AUTO-LIMPIEZA ---
    with db_session.begin_nested():
        db_session.query(RoyaltyTransaction).filter(
            RoyaltyTransaction.year == period.year, RoyaltyTransaction.month == period.month
        ).delete(synchronize_session=False)
        db_session.query(RoyaltyPayment).filter(
            RoyaltyPayment.year == period.year, RoyaltyPayment.month == period.month
        ).delete(synchronize_session=False)
        db_session.flush()

    alias_res = build_municipality_maps(db_session, summary_df)

    txn_count = load_transactions(
        db_session,
        details_df,
        exchange_rate,
        get_or_create_companies(db_session, details_df),
        alias_res[0]
    )
    sum_res = load_summary(db_session, summary_df, exchange_rate, period, alias_res[0])

    db_session.commit()
    logger.info('ETL completed. %s transactions and %s summaries saved.', txn_count, sum_res[0])

    return {
        'status': MiningStatus.SUCCESS,
        'result': MiningResult.ROYALTIES_ETL_COMPLETED,
        'processed_transactions': txn_count,
        'processed_summaries': sum_res[0],
        'rejected_records': alias_res[1]
    }
