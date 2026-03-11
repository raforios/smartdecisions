'''
    Mining Analysis Business Logic Services
'''
from decimal import ROUND_HALF_UP, Decimal
import io
from typing import Dict, Any, List
from fastapi import Request
import pandas as pd
from sqlalchemy import extract, func
from sqlalchemy.orm import Session, joinedload
from models.mining_analysis import (
    Mineral,
    MiningPrice,
    Department,
    Municipality,
    RoyaltyPayment
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
        # Cargamos el dataframe
        df = pd.read_csv(io.BytesIO(file_content), sep=delimiter)

        # 1. SANITIZACIÓN DE CABECERAS: Elimina espacios y saltos de línea ocultos (\n, \r)
        df.columns = df.columns.str.strip()

        # 2. VALIDACIÓN TEMPRANA: Asegurar que las columnas existan tras limpiar o
        # si falló el delimitador
        required_columns = ['Fecha', 'Mineral', 'Unidad', 'Baja', 'Alta']
        missing_cols = [col for col in required_columns if col not in df.columns]

        if missing_cols:
            raise ValueError(
                f'Faltan columnas o delimitador "{delimiter}" incorrecto. No se halló: {
                missing_cols}'
            )

        # Limpieza y normalización de tipos
        df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst = True).dt.date
        df['Baja'] = df['Baja'].apply(clean_currency_pro)
        df['Alta'] = df['Alta'].apply(clean_currency_pro)

    except ValueError as ve:
        error_msg = f'Validation Error processing CSV: {ve}'
        logger.error(error_msg, exc_info = True)
        raise InvalidInputError(detail=str(ve)) from ve
    except Exception as e:
        error_msg = f'Error processing CSV: {e}'
        logger.error(error_msg, exc_info = True)
        raise InvalidInputError(
            detail = 'Formato de archivo CSV inválido o corrupto.'
        ) from e

    processed, skipped = 0, 0

    # Uso de transacciones anidadas para operaciones en bloque
    with db.begin_nested():
        for _, row in df.iterrows():
            mineral = db.query(Mineral).filter(Mineral.name == row['Mineral']).first()
            if not mineral:
                mineral = Mineral(name=row['Mineral'], unit=row['Unidad'])
                db.add(mineral)
                db.flush() # Flush en lugar de commit para mantener la transacción abierta

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
        Internal helper to calculate YoY variations and strategic insights.
    '''
    comparison_map = {
        (d['department'], d['municipality']): d
        for d in prev_data
    }

    total_periodo_bob = Decimal('0')

    for record in data:
        key = (record['department'], record['municipality'])
        prev = comparison_map.get(key)

        actual_val = Decimal(str(record['total_recaudado_bob']))
        total_periodo_bob += actual_val

        record['variacion_monto_bob'] = 0.0
        record['variacion_porcentaje'] = 0.0

        if prev and Decimal(str(prev['total_recaudado_bob'])) > 0:
            pasado_val = Decimal(str(prev['total_recaudado_bob']))
            diff = actual_val - pasado_val
            record['variacion_monto_bob'] = float(diff)
            porc = (diff / pasado_val) * Decimal('100')
            record['variacion_porcentaje'] = float(porc.quantize(Decimal('1.00'),
                                            rounding = ROUND_HALF_UP))

    # KPI Sugerido: Top 5 de crecimiento porcentual
    top_crecimiento = sorted(
        [d for d in data if d['variacion_porcentaje'] > 0],
        key = lambda x: x['variacion_porcentaje'],
        reverse = True
    )[:5]

    return {
        'detailed_records': data,
        'summary_kpis': {
            'total_recaudado_periodo': float(total_periodo_bob),
            'municipios_destacados': top_crecimiento,
            'alerta_caida_critica': [d for d in data if d['variacion_porcentaje'] < -20]
        }
    }

@handle_service_errors('MINING_ANALYSIS')
async def get_royalties_summary_service(
    db: Session,
    year: int = None,
    quarter: int = None,
    request: Request = None, # pylint: disable=unused-argument
    current_user: str = None # pylint: disable=unused-argument
) -> Dict[str, Any]:
    '''
    Aggregates all financial metrics (BOB and USD) directly from the database model.
    '''
    def fetch_data(target_year: int):
        query = db.query(
            extract('year', RoyaltyPayment.period_date).label('year'),
            extract('month', RoyaltyPayment.period_date).label('month'),
            Department.name.label('department'),
            Municipality.name.label('municipality'),
            # Extraemos BOB
            func.sum(RoyaltyPayment.total_collected_bob).label('total_bob'),
            func.sum(RoyaltyPayment.commission_bob).label('comision_bob'),
            func.sum(RoyaltyPayment.subtotal_bob).label('subtotal_bob'),
            func.sum(RoyaltyPayment.gov_dept_bob).label('dept_bob'),
            func.sum(RoyaltyPayment.gov_muni_bob).label('muni_bob'),
            # Extraemos USD nativos de la DB
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
            query = query.filter(extract('year', RoyaltyPayment.period_date) == target_year)

        return query.group_by(
            extract('year', RoyaltyPayment.period_date),
            extract('month', RoyaltyPayment.period_date),
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

    final_response = {
        'status': 'success',
        'message': 'Data retrieved successfully',
        'data': {
            'detailed_records': formatted_data,
            'summary_kpis': {
                'total_recaudado_periodo': sum(d['total_recaudado_bob'] for d in formatted_data),
                'municipios_destacados': [],
                'alerta_caida_critica': []
            }
        }
    }

    if year and not quarter:
        prev_results_raw = fetch_data(year - 1)
        prev_records = [
            {
                'department': r.department,
                'municipality': r.municipality,
                'total_recaudado_bob': float(r.total_bob)
            } for r in prev_results_raw
        ]
        if prev_records:
            final_response['data'] = _calculate_advanced_kpis(formatted_data, prev_records)

    return final_response
