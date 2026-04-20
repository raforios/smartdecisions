'''
    Mining Analysis Business Logic Services
'''
from collections import defaultdict
import io
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, Any, List
from fastapi import Request
import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from models.mining_analysis import (
    Company,
    Mineral,
    MiningPrice,
    Department,
    Municipality,
    RoyaltyPayment,
    RoyaltyTransaction
)
from services.utils import handle_service_errors
from services.exceptions import InvalidInputError
from services.logger_config import custom_logger as logger

def clean_currency_pro(value: Any) -> float:
    ''' Handles mixed currency formats (26.500,00 and 218,632) and nulls. '''
    if pd.isna(value) or str(value).strip() in ['-', '']:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)

    str_val = str(value).strip().replace('.', '').replace(',', '.')
    if str_val.count('.') > 1:
        str_val = str_val.replace('.', '', str_val.count('.') - 1)

    try:
        return float(str_val)
    except ValueError:
        return 0.0

async def process_mining_etl_service(
    db: Session,
    file_content: bytes,
    delimiter: str = ','
) -> Dict[str, Any]:
    ''' Optimized ETL logic using Pandas with duplicate tracking and column sanitization. '''
    try:
        df = pd.read_csv(io.BytesIO(file_content), sep = delimiter)
        df.columns = df.columns.str.strip()

        required_columns = ['Fecha', 'Mineral', 'Unidad', 'Baja', 'Alta']
        missing_cols = [col for col in required_columns if col not in df.columns]

        if missing_cols:
            raise ValueError(
                f'Faltan columnas o delimitador "{delimiter}" incorrecto. No se halló: {
                    missing_cols}'
            )

        df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst = True).dt.date
        df['Baja'] = df['Baja'].apply(clean_currency_pro)
        df['Alta'] = df['Alta'].apply(clean_currency_pro)

    except ValueError as ve:
        error_msg = f'Validation Error processing CSV: {ve}'
        logger.error(error_msg, exc_info = True)
        raise InvalidInputError(detail = str(ve)) from ve
    except Exception as e:
        error_msg = f'Error processing CSV: {e}'
        logger.error(error_msg, exc_info = True)
        raise InvalidInputError(
            detail = 'Formato de archivo CSV inválido o corrupto.'
        ) from e

    processed, skipped = 0, 0

    with db.begin_nested():
        for _, row in df.iterrows():
            mineral = db.query(Mineral).filter(Mineral.name == row['Mineral']).first()
            if not mineral:
                mineral = Mineral(name = row['Mineral'], unit = row['Unidad'])
                db.add(mineral)
                db.flush()

            existing = db.query(MiningPrice).filter(
                MiningPrice.mineral_id == mineral.id,
                MiningPrice.date == row['Fecha']
            ).first()

            if not existing:
                new_price = MiningPrice(
                    mineral_id = mineral.id,
                    date = row['Fecha'],
                    price_low = row['Baja'],
                    price_high = row['Alta']
                )
                db.add(new_price)
                processed += 1
            else:
                skipped += 1

    db.commit()

    return {
        'status': 'success',
        'message': f'ETL finished: {processed} new records, {skipped} skipped.',
        'processed_records': processed,
        'skipped_records': skipped
    }

async def get_all_prices_service(db: Session) -> List[MiningPrice]:
    ''' Retrieves all mineral prices with their associated mineral metadata. '''
    return db.query(MiningPrice).options(joinedload(MiningPrice.mineral)).all()

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
        'status': 'success',
        'message': 'Data retrieved successfully',
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
        'status': 'success',
        'message': 'Transactions retrieved successfully',
        'data': formatted_data
    }
