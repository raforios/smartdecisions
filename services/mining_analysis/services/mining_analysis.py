'''
    Mining Analysis Business Logic Services
'''
import io
from typing import Dict, Any, List
import pandas as pd
from sqlalchemy.orm import Session, joinedload
from models.mining_analysis import Mineral, MiningPrice
from services.logger_config import custom_logger as logger

def clean_currency_pro(value: Any) -> float:
    '''
        Handles mixed currency formats (26.500,00 and 218,632) and nulls.
    '''
    if pd.isna(value) or str(value).strip() in ['-', '']:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)

    str_val = str(value).strip().replace('.', '').replace(',', '.')
    # Caso especial para decimales de 4 posiciones tras coma latina
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
    '''
        Optimized ETL logic using Pandas with duplicate tracking.
    '''
    try:
        # Cargamos el dataframe
        df = pd.read_csv(io.BytesIO(file_content), sep=delimiter)

        # Limpieza y normalización de tipos
        df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst=True).dt.date
        df['Baja'] = df['Baja'].apply(clean_currency_pro)
        df['Alta'] = df['Alta'].apply(clean_currency_pro)

    except Exception as e: # pylint: disable=broad-exception-caught
        error_msg = f'Error processing CSV: {e}'
        logger.error(error_msg, exc_info=True)
        return {
            'status': 'error',
            'message': error_msg,
            'processed_records': 0,
            'skipped_records': 0
        }

    processed, skipped = 0, 0
    for _, row in df.iterrows():
        # Lógica de Minerales
        mineral = db.query(Mineral).filter(Mineral.name == row['Mineral']).first()
        if not mineral:
            mineral = Mineral(name=row['Mineral'], unit=row['Unidad'])
            db.add(mineral)
            db.commit()
            db.refresh(mineral)

        # Validación de Duplicados (Evita el error en la segunda subida)
        existing = db.query(MiningPrice).filter(
            MiningPrice.mineral_id == mineral.id,
            MiningPrice.date == row['Fecha']
        ).first()

        if not existing:
            new_price = MiningPrice(
                mineral_id=mineral.id,
                date=row['Fecha'],
                price_low=row['Baja'],
                price_high=row['Alta']
            )
            db.add(new_price)
            processed += 1
        else:
            skipped += 1

    db.commit()

    # IMPORTANTE: Devolver todas las llaves requeridas por el Schema
    return {
        'status': 'success',
        'message': f'ETL finished: {processed} new records, {skipped} skipped.',
        'processed_records': processed,
        'skipped_records': skipped
    }

async def get_all_prices_service(db: Session) -> List[MiningPrice]:
    '''
        Retrieves all mineral prices with their associated mineral metadata.
    '''
    return db.query(MiningPrice).options(joinedload(MiningPrice.mineral)).all()
