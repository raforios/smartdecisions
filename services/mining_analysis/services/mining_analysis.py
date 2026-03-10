'''
    Mining Analysis Business Logic Services
'''
import io
from typing import Dict, Any, List
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


async def get_royalties_summary_service(db: Session) -> List[Dict[str, Any]]:
    '''
        Service to aggregate royalty facts by Year and Department from the database.
        Encapsulates all SQL logic to keep the controller clean.
    '''
    year_column = extract('year', RoyaltyPayment.period_date).label('year')

    results = db.query(
        year_column,
        Department.name.label('department'),
        func.sum(RoyaltyPayment.total_collected).label('total_recaudado'),
        func.sum(RoyaltyPayment.subtotal).label('subtotal'),
        func.sum(RoyaltyPayment.gov_dept).label('gov_dept'),
        func.sum(RoyaltyPayment.gov_muni).label('gov_muni')
    ).join(
        Municipality, RoyaltyPayment.municipality_id == Municipality.id
    ).join(
        Department, Municipality.department_id == Department.id
    ).group_by(
        year_column,
        Department.name
    ).all()

    return [
        {
            'year': int(r.year),
            'department': r.department,
            'total_recaudado': float(r.total_recaudado),
            'subtotal': float(r.subtotal),
            'gov_dept': float(r.gov_dept),
            'gov_muni': float(r.gov_muni)
        } for r in results
    ]
