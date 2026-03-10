'''
    ETL Services for Mining Royalties (Data Engineering)
'''
import io
from typing import Dict, Any, Tuple
import pandas as pd
from sqlalchemy.orm import Session
from models.mining_analysis import Department, Municipality, RoyaltyPayment
from services.logger_config import custom_logger as logger
from services.exceptions import InvalidInputError # Integración del Boilerplate

def _load_dimensions(db: Session, df_deptos: pd.DataFrame, df_munis: pd.DataFrame) -> None:
    ''' Helper: Carga catálogos de departamentos y municipios (Dimensiones). '''
    with db.begin_nested():
        for _, row in df_deptos.iterrows():
            dept_id = int(row['No_Departamento'])
            dept_name = str(row['Departamento']).strip().upper()
            if not db.query(Department).filter(Department.id == dept_id).first():
                db.add(Department(id=dept_id, name=dept_name))
        db.flush() # Guardamos para tener los IDs disponibles

        for _, row in df_munis.iterrows():
            off_code = int(row['Cod. Muni. Prod.'])
            if not db.query(Municipality).filter(Municipality.official_code == off_code).first():
                muni = Municipality(
                    official_code=off_code,
                    name=str(row['Municipio Productor']).strip(),
                    province=str(row['Provincia']).strip(),
                    department_id=int(row['N_Dpto'])
                )
                db.add(muni)
        db.flush()

def _load_facts(db: Session, df_facts: pd.DataFrame) -> Tuple[int, int]:
    ''' Helper: Carga los hechos transaccionales de regalías. '''
    processed, skipped = 0, 0
    df_facts['Mes/Año '] = pd.to_datetime(df_facts['Mes/Año ']).dt.date
    num_cols = ['Total Recaudado', 'Comisión', 'Subtotal', 'Gob. Deptal.', 'Gob. Municipal']

    for col in num_cols:
        df_facts[col] = pd.to_numeric(df_facts[col], errors='coerce').fillna(0.0)

    with db.begin_nested():
        for _, row in df_facts.iterrows():
            off_code = int(row['Cod. Muni. Prod.'])
            period = row['Mes/Año ']

            muni = db.query(Municipality).filter(Municipality.official_code == off_code).first()
            if not muni:
                error_msg = f'Municipio no encontrado: {off_code}'
                logger.warning(error_msg)
                continue

            existing = db.query(RoyaltyPayment).filter(
                RoyaltyPayment.municipality_id == muni.id,
                RoyaltyPayment.period_date == period
            ).first()

            if not existing:
                fact = RoyaltyPayment(
                    municipality_id=muni.id, period_date=period,
                    total_collected=row['Total Recaudado'], commission=row['Comisión'],
                    subtotal=row['Subtotal'], gov_dept=row['Gob. Deptal.'],
                    gov_muni=row['Gob. Municipal']
                )
                db.add(fact)
                processed += 1
            else:
                skipped += 1
        db.flush()
    return processed, skipped

async def process_royalties_excel_service(db: Session, file_content: bytes) -> Dict[str, Any]:
    ''' Extracts, transforms and loads multi-sheet Excel data into the Star Schema. '''
    try:
        excel_data = pd.ExcelFile(io.BytesIO(file_content), engine='openpyxl')
        df_deptos = pd.read_excel(excel_data, sheet_name='Detalle_Dptos')
        df_munis = pd.read_excel(excel_data, sheet_name='Detalle_Div-Pol')
        df_facts = pd.read_excel(excel_data, sheet_name='Coparticipación_Bs')
    except Exception as e:
        error_msg = f'Error al procesar el archivo Excel: {str(e)}'
        logger.error(error_msg, exc_info=True)
        # Boilerplate: Lanzamos excepción personalizada en lugar de devolver dict
        raise InvalidInputError(
            detail = 'El archivo no es válido o faltan hojas requeridas.'
        ) from e

    # Refactorización: Dividido en helpers para evitar "Too many locals" (R0914)
    _load_dimensions(db, df_deptos, df_munis)
    processed, skipped = _load_facts(db, df_facts)

    db.commit() # Commit final de toda la transacción

    message = f'ETL de Regalías finalizado. Procesados: {processed}. Omitidos: {skipped}.'
    logger.info(message)

    return {
        'status': 'success',
        'message': message,
        'processed_records': processed,
        'skipped_records': skipped
    }
