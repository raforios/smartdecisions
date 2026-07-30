'''
    Excel ingestion pipeline: reads the uploaded file, runs validation, and
    derives the summary metrics that feed the IngestResponse.

    Supports .xlsx (via openpyxl) and .csv. Auto-computes 'monto_total' when
    missing but both 'cantidad' and 'precio_unitario' are available, matching
    the rule documented in SMARTDECISIONS.md §5.
'''
import csv
from io import BytesIO
from typing import Final
import pandas as pd

from services.column_mapper import map_columns
from services.excel_validator import validate as validate_schema
from services.logger_config import custom_logger as logger


SUPPORTED_EXTENSIONS: Final[tuple[str, ...]] = ('.xlsx', '.csv')

# Delimiters a Latin-American CSV export may use. Excel in es-locale defaults to
# ';' (because ',' is the decimal separator), so we auto-detect rather than
# assume ','.
_CSV_DELIMITERS: Final[str] = ',;\t|'


def _read_csv(file_bytes: bytes) -> pd.DataFrame:
    '''
        Reads a CSV auto-detecting its delimiter (comma, semicolon, tab or pipe)
        so es-locale exports work without the user picking one. When the
        delimiter is ';' the decimal separator is assumed to be ',' (the typical
        Excel-in-Spanish combination), so numbers like "10,89" parse correctly.
    '''
    sample = file_bytes[:65536].decode('utf-8-sig', errors = 'replace')
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters = _CSV_DELIMITERS).delimiter
    except csv.Error:
        delimiter = ','
    decimal = ',' if delimiter == ';' else '.'
    message = f'CSV delimiter detected: {delimiter!r} (decimal={decimal!r}).'
    logger.info(message)
    return pd.read_csv(
        BytesIO(file_bytes), sep = delimiter, decimal = decimal, encoding = 'utf-8-sig'
    )


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
        return _read_csv(file_bytes)

    raise ValueError(
        f'Formato de archivo no soportado: "{filename}". Use {", ".join(SUPPORTED_EXTENSIONS)}.'
    )


_ID_COLUMNS = ('id_pedido', 'id_punto_venta', 'id_producto')


def _clean_id(value: object) -> object:
    '''
        Normalizes a single identifier to a clean string. Numeric codes read as
        floats (e.g. 20101122965.0) become their integer string ('20101122965')
        so the str_length contract holds and grouping stays consistent; blanks
        become NA so the validator flags them.
    '''
    if pd.isna(value):
        return pd.NA
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(value).strip()
    return text or pd.NA


def _stringify_ids(dataframe: pd.DataFrame) -> pd.DataFrame:
    '''
        Coerces the identifier columns to clean strings. ERP exports often carry
        numeric codes (float/int dtype); without this, pandera's str_length check
        receives raw numbers and rejects otherwise-valid rows.
    '''
    for column in _ID_COLUMNS:
        if column in dataframe.columns:
            dataframe[column] = dataframe[column].map(_clean_id)
    return dataframe


def _parse_dates(dataframe: pd.DataFrame) -> pd.DataFrame:
    '''
        Coerces the 'fecha' column to datetime using day-first parsing (Bolivia
        writes dd/mm/aaaa). CSV dates arrive as strings; without this they stay
        text and, worse, ambiguous dates like 12/01/2026 would be misread as
        December instead of January. Unparseable dates become NaT so the
        validator flags (and the partial pipeline rejects) those rows.
    '''
    if 'fecha' in dataframe.columns:
        dataframe['fecha'] = pd.to_datetime(
            dataframe['fecha'], dayfirst = True, errors = 'coerce'
        )
    return dataframe


def _fill_ids_from_names(dataframe: pd.DataFrame) -> pd.DataFrame:
    '''
        Uses the client/product NAME as its identifier when no explicit code is
        provided. The friendly template only asks for 'Cliente' and 'Producto'
        (mapped to nombre_pdv / nombre_producto), so the required id columns are
        filled from those names; a raw ERP export that already carries codes is
        left untouched.

        Args:
            dataframe (pd.DataFrame): DataFrame with canonical column names.

        Returns:
            pd.DataFrame: Same frame with id_punto_venta / id_producto ensured.
    '''
    for id_column, name_column in (
        ('id_punto_venta', 'nombre_pdv'),
        ('id_producto', 'nombre_producto'),
    ):
        if name_column not in dataframe.columns:
            continue
        if id_column not in dataframe.columns:
            dataframe[id_column] = dataframe[name_column]
        else:
            missing = dataframe[id_column].isna()
            dataframe.loc[missing, id_column] = dataframe.loc[missing, name_column]
    return dataframe


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
        'unique_points_of_sale': (
            int(dataframe['id_punto_venta'].nunique())
            if 'id_punto_venta' in dataframe else 0
        ),
        'unique_products': (
            int(dataframe['id_producto'].nunique())
            if 'id_producto' in dataframe else 0
        ),
        'date_range_start': None,
        'date_range_end': None,
    }

    if 'fecha' in dataframe.columns and dataframe['fecha'].notna().any():
        fechas = pd.to_datetime(dataframe['fecha'], errors = 'coerce')
        summary['date_range_start'] = fechas.min().date().isoformat()
        summary['date_range_end'] = fechas.max().date().isoformat()

    return summary


def serialize_dataframe(dataframe: pd.DataFrame, filename: str) -> bytes:
    '''
        Serializes a (normalized) DataFrame back to bytes, matching the original
        file's format so the object stored in S3 keeps its extension. This lets
        downstream services (analytics, forecast, routes) read the canonical
        columns directly — normalization happens once, here at ingest.

        Args:
            dataframe (pd.DataFrame): The validated, canonical-column DataFrame.
            filename (str): Original filename (drives the output format).

        Returns:
            bytes: The serialized file content.
    '''
    if filename.lower().endswith('.csv'):
        return dataframe.to_csv(index = False).encode('utf-8')
    buffer = BytesIO()
    dataframe.to_excel(buffer, index = False, engine = 'openpyxl')
    return buffer.getvalue()


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
    # Map real-world headers (e.g. 'Numero Factura', 'Codigo Sap') to the
    # canonical template names before validating, so raw ERP exports ingest too.
    mapped = map_columns(raw)
    # Clean numeric ERP codes to strings first, then fill the required id columns
    # from the client/product names when no explicit code is present (the
    # friendly template only carries names).
    mapped = _stringify_ids(mapped)
    mapped = _fill_ids_from_names(mapped)
    mapped = _parse_dates(mapped)
    validated, errors = validate_schema(mapped)

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


_COLUMN_LEVEL_RULES = ('column_in_dataframe', 'column_in_schema')


def parse_and_validate_partial(
    file_bytes: bytes, filename: str
) -> tuple[pd.DataFrame, pd.DataFrame, list[dict], dict]:
    '''
        Partial-acceptance pipeline: keeps the valid rows and sets the invalid
        ones aside so the client can fix and re-upload them.

        A missing REQUIRED COLUMN is a whole-file failure (no row can be kept);
        otherwise every row with a cell-level error is dropped from the accepted
        set and collected into the rejected frame with a 'motivo' column stating
        why it failed.

        Args:
            file_bytes (bytes): Raw uploaded file content.
            filename (str): Original filename (drives format detection).

        Returns:
            tuple[pd.DataFrame, pd.DataFrame, list[dict], dict]:
                - valid_df: coerced accepted rows (empty on whole-file failure).
                - rejected_df: rejected rows plus a 'motivo' column.
                - errors: structured error list (row/column/value/rule/message).
                - summary: IngestSummary over the whole file (total/valid/error).
    '''
    raw = _read_dataframe(file_bytes, filename)
    mapped = _parse_dates(_fill_ids_from_names(_stringify_ids(map_columns(raw))))
    _, errors = validate_schema(mapped)

    # A missing required column means the whole file cannot be processed.
    if any(err['rule'] in _COLUMN_LEVEL_RULES for err in errors):
        empty = mapped.iloc[0:0]
        rejected = mapped.copy()
        rejected['motivo'] = 'Falta una columna obligatoria en el archivo.'
        summary = _summarize(empty, error_rows = 0)
        summary['total_rows'] = len(rejected)
        summary['valid_rows'] = 0
        summary['error_rows'] = len(rejected)
        return empty, rejected, errors, summary

    # Cell-level errors: the reported row is the Excel row (index + 2).
    reasons: dict[int, list[str]] = {}
    for err in errors:
        idx = err['row'] - 2
        if idx >= 0:
            reasons.setdefault(idx, []).append(f'{err["column"]}: {err["message"]}')

    bad_index = [i for i in reasons if i in mapped.index]
    valid_df, _ = validate_schema(mapped.drop(index = bad_index, errors = 'ignore'))
    valid_df = _derive_monto_total(valid_df)

    rejected_df = mapped.loc[bad_index].copy()
    rejected_df['motivo'] = ['; '.join(reasons[i]) for i in bad_index]

    summary = _summarize(valid_df, error_rows = 0)
    summary['total_rows'] = len(valid_df) + len(rejected_df)
    summary['valid_rows'] = len(valid_df)
    summary['error_rows'] = len(rejected_df)

    message = (
        f'Partial ingest of "{filename}": {len(valid_df)} accepted, '
        f'{len(rejected_df)} rejected.'
    )
    logger.info(message)
    return valid_df, rejected_df, errors, summary
