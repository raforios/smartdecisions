'''
    Script to seed the official catalog of Departments and Municipalities.
'''
import sys
import zipfile
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from services.db_connection import ENGINE
from services.logger_config import custom_logger as logger
from models.mining_analysis import Department, Municipality


def seed_official_locations(excel_path: str) -> None:
    '''
        Loads the official catalog from an Excel file with two sheets.
        Ensures the data quality of the political division.

        Args:
            excel_path (str): The file path to the master locations Excel file.
    '''
    logger.info('Reading master file from: %s', excel_path)

    try:
        df_dept = pd.read_excel(excel_path, sheet_name = 'Departamentos')
        df_muni = pd.read_excel(excel_path, sheet_name = 'Municipios')
    except (ValueError, OSError, zipfile.BadZipFile) as exc:
        logger.error('Failed to read the master Excel file: %s', exc)
        return

    with Session(ENGINE) as db_session:
        try:
            with db_session.begin_nested():
                logger.info('Processing Departments...')
                for _, row in df_dept.iterrows():
                    dept_id = int(row['No_Departamento'])
                    dept_name = str(row['Departamento']).upper().strip()

                    dept = db_session.query(Department).filter(
                        Department.id == dept_id
                    ).first()

                    if not dept:
                        db_session.add(Department(id = dept_id, name = dept_name))
                    else:
                        dept.name = dept_name

                db_session.flush()

                logger.info('Processing Municipalities...')
                for _, row in df_muni.iterrows():
                    muni_code = int(row['Cod. Muni. Prod.'])
                    muni_name = str(row['Municipio Productor']).upper().strip()
                    dept_id = int(row['N_Dpto'])

                    muni = db_session.query(Municipality).filter(
                        Municipality.official_code == muni_code
                    ).first()

                    if not muni:
                        db_session.add(Municipality(
                            official_code = muni_code,
                            name = muni_name,
                            department_id = dept_id
                        ))
                    else:
                        muni.name = muni_name
                        muni.department_id = dept_id

            db_session.commit()
            logger.info('Official locations catalog loaded and committed successfully.')

        except SQLAlchemyError as exc:
            db_session.rollback()
            logger.error('Database error during insertion: %s', exc)
        except (ValueError, TypeError, KeyError) as exc:
            db_session.rollback()
            logger.error('Unexpected data parsing error during insertion: %s', exc)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        logger.error('Usage: python seed_locations.py <path_to_excel_file>')
        sys.exit(1)

    master_file_path = sys.argv[1]
    seed_official_locations(master_file_path)
