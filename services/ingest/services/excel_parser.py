'''
    Excel ingestion pipeline: reads the uploaded file, runs validation, and
    derives the summary metrics that feed the IngestResponse.

    Supports .xlsx (via openpyxl) and .csv. Auto-computes 'monto_total' when
    missing but both 'cantidad' and 'precio_unitario' are available, matching
    the rule documented in SMARTDECISIONS.md §5.
'''
from io import BytesIO
from typing import Final
import pandas as pd

from services.excel_validator import validate as validate_schema
from services.logger_config import custom_logger as logger


SUPPORTED_EXTENSIONS: Final[tuple[str, ...]] = ('.xlsx', '.csv')


def _read_dataframe(file_bytes: bytes, filename: str) -> pd.DataFrame:
    '''
        Reads the uploaded file into a pandas DataFrame based on its extension.

        Args:
            file_bytes (bytes): Raw file content received from the upload.
            filename (str): Original filename, used to detect format by extension.

        Returns:
            pd.DataFrame: Raw DataFrame (no validation yet).

        Raises:
            ValueError: If the file extension is not supported.
    '''
    lower = filename.lower()
    buffer = BytesIO(file_bytes)

    if lower.endswith('.xlsx'):
        return pd.read_excel(buffer, engine = 'openpyxl')
    if lower.endswith('.csv'):
        return pd.read_csv(buffer)

    raise ValueError(
        f'Formato de archivo no soportado: "{filename}". Use {", ".join(SUPPORTED_EXTENSIONS)}.'
    )


def _derive_monto_total(dataframe: pd.DataFrame) -> pd.DataFrame:
    '''
        Fills missing 'monto_total' as cantidad * precio_unitario when both
        operands are available; leaves NaN otherwise.

        Args:
            dataframe (pd.DataFrame): Validated DataFrame.

        Returns:
            pd.DataFrame: Same frame with 'monto_total' completed where possible.
    '''
    if 'monto_total' not in dataframe.columns:
        dataframe['monto_total'] = pd.NA

    # Derivation requires both operands; when precio_unitario is absent there
    # is nothing to multiply, so monto_total stays as-is (typically NA).
    if 'precio_unitario' not in dataframe.columns or 'cantidad' not in dataframe.columns:
        return dataframe

    has_inputs = dataframe['cantidad'].notna() & dataframe['precio_unitario'].notna()
    missing_total = dataframe['monto_total'].isna() & has_inputs
    dataframe.loc[missing_total, 'monto_total'] = (
        dataframe.loc[missing_total, 'cantidad']
        * dataframe.loc[missing_total, 'precio_unitario']
    )
    return dataframe


def _summarize(dataframe: pd.DataFrame, error_rows: int) -> dict:
    '''
        Computes the IngestSummary metrics from a validated DataFrame.

        Args:
            dataframe (pd.DataFrame): The validated DataFrame.
            error_rows (int): Number of rows flagged as invalid.

        Returns:
            dict: Keys match IngestSummary fields.
    '''
    total = int(len(dataframe))
    summary = {
        'total_rows': total,
        'valid_rows': max(total - error_rows, 0),
        'error_rows': error_rows,
        'unique_points_of_sale': int(dataframe['id_punto_venta'].nunique()) if 'id_punto_venta' in dataframe else 0,
        'unique_products': int(dataframe['id_producto'].nunique()) if 'id_producto' in dataframe else 0,
        'date_range_start': None,
        'date_range_end': None,
    }

    if 'fecha' in dataframe.columns and dataframe['fecha'].notna().any():
        fechas = pd.to_datetime(dataframe['fecha'], errors = 'coerce')
        summary['date_range_start'] = fechas.min().date().isoformat()
        summary['date_range_end'] = fechas.max().date().isoformat()

    return summary


def parse_and_validate(file_bytes: bytes, filename: str) -> tuple[pd.DataFrame, list[dict], dict]:
    '''
        End-to-end ingest pipeline: read, validate, derive, summarize.

        Args:
            file_bytes (bytes): Raw uploaded file content.
            filename (str): Original filename (drives format detection).

        Returns:
            tuple[pd.DataFrame, list[dict], dict]:
                - The processed DataFrame (validated + monto_total derived).
                - List of structured errors (empty when valid).
                - Summary dict matching IngestSummary.

        Raises:
            ValueError: On unsupported extension or unreadable content.
    '''
    raw = _read_dataframe(file_bytes, filename)
    validated, errors = validate_schema(raw)

    if not errors:
        validated = _derive_monto_total(validated)

    summary = _summarize(validated, error_rows = len(errors))

    message = (
        f'Ingest pipeline processed file "{filename}": '
        f'{summary["valid_rows"]}/{summary["total_rows"]} rows valid, '
        f'{summary["error_rows"]} error(s).'
    )
    logger.info(message)

    return validated, errors, summary
