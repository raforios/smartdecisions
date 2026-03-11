'''
    ETL Services for Mining Royalties (Data Engineering)
'''
import io
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, Tuple
import pandas as pd
from sqlalchemy.orm import Session
from models.mining_analysis import Department, Municipality, RoyaltyPayment
from services.utils import handle_service_errors
from services.logger_config import custom_logger as logger

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

def _load_facts(
    db: Session,
    df_facts: pd.DataFrame,
    exchange_rate: Decimal = Decimal('6.96')
) -> Tuple[int, int]:
    ''' Helper: Carga los hechos transaccionales de regalías con conversión a USD. '''
    processed, updated = 0, 0
    df_facts['Mes/Año '] = pd.to_datetime(df_facts['Mes/Año ']).dt.date

    def to_dec(value: Any) -> Decimal:
        ''' Helper interno para asegurar precisión decimal. '''
        return Decimal(str(value or 0)).quantize(Decimal('1.0000'), rounding = ROUND_HALF_UP)

    with db.begin_nested():
        for _, row in df_facts.iterrows():
            off_code = int(row['Cod. Muni. Prod.'])
            period = row['Mes/Año ']

            muni = db.query(Municipality).filter(Municipality.official_code == off_code).first()
            if not muni:
                error_msg = f'Municipio no encontrado: {off_code}'
                logger.warning(error_msg)
                continue

            # Implementación de Upsert para evitar el error de duplicados
            fact = db.query(RoyaltyPayment).filter(
                RoyaltyPayment.municipality_id == muni.id,
                RoyaltyPayment.period_date == period
            ).first()

            if not fact:
                fact = RoyaltyPayment(municipality_id = muni.id, period_date = period)
                db.add(fact)
                processed += 1
            else:
                updated += 1

            # Asignación de valores BOB
            fact.total_collected_bob = to_dec(row['Total Recaudado'])
            fact.commission_bob = to_dec(row['Comisión'])
            fact.subtotal_bob = to_dec(row['Subtotal'])
            fact.gov_dept_bob = to_dec(row['Gob. Deptal.'])
            fact.gov_muni_bob = to_dec(row['Gob. Municipal'])

            # Cálculo y asignación de valores USD
            fact.total_collected_usd = fact.total_collected_bob / exchange_rate
            fact.commission_usd = fact.commission_bob / exchange_rate
            fact.subtotal_usd = fact.subtotal_bob / exchange_rate
            fact.gov_dept_usd = fact.gov_dept_bob / exchange_rate
            fact.gov_muni_usd = fact.gov_muni_bob / exchange_rate

        db.flush()
    return processed, updated

@handle_service_errors('MINING_ANALYSIS')
async def process_royalties_excel_service(
    db: Session,
    file_content: bytes,
    exchange_rate: Decimal = Decimal('6.96')
) -> Dict[str, Any]:
    ''' Extracts, transforms and loads multi-sheet Excel data with currency conversion. '''
    excel_data = pd.ExcelFile(io.BytesIO(file_content), engine='openpyxl')
    df_deptos = pd.read_excel(excel_data, sheet_name='Detalle_Dptos')
    df_munis = pd.read_excel(excel_data, sheet_name='Detalle_Div-Pol')
    df_facts = pd.read_excel(excel_data, sheet_name='Coparticipación_Bs')
    excel_data = pd.ExcelFile(io.BytesIO(file_content), engine = 'openpyxl')
    df_deptos = pd.read_excel(excel_data, sheet_name = 'Detalle_Dptos')
    df_munis = pd.read_excel(excel_data, sheet_name = 'Detalle_Div-Pol')
    df_facts = pd.read_excel(excel_data, sheet_name = 'Coparticipación_Bs')

    _load_dimensions(db, df_deptos, df_munis)
    processed, updated = _load_facts(db, df_facts, exchange_rate)

    db.commit()

    message = f'ETL de Regalías finalizado. Procesados: {processed}. Actualizados: {updated}.'
    logger.info(message)

    return {
        'status': 'success',
        'message': message,
        'processed_records': processed,
        'updated_records': updated
    }
