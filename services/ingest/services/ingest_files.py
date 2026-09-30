'''
    Reading and writing the files that cross the ingest boundary: the uploaded
    .xlsx or .csv on the way in, the normalized CSV on the way out.

    A workbook is opened ONCE per upload and every sheet is served from that
    read: the sales, payments, stock and visits pipelines each look for their
    own sheet in the same book, and opening a 2.6 MB file with openpyxl takes
    about ten seconds in Lambda — three opens blew the 30 s budget.
'''
import csv
import re
from functools import lru_cache
from io import BytesIO
from typing import Final

import pandas as pd

from services.logger_config import custom_logger as logger

SUPPORTED_EXTENSIONS: Final[tuple[str, ...]] = ('.xlsx', '.csv')

# Delimiters a Latin-American CSV export may use. Excel in es-locale defaults to
# ';' (because ',' is the decimal separator), so we auto-detect rather than
# assume ','.
_CSV_DELIMITERS: Final[str] = ',;\t|'


def _detect_decimal(
    sample: str,
    delimiter: str
) -> str:
    '''
        Detects the decimal separator FROM THE DATA (not from the delimiter): a
        ';'-delimited file may still use '.' decimals (e.g. an ERP export) or ','
        decimals (Excel es-locale). When the delimiter is ',' the decimal must be
        '.'; otherwise we compare how often digits are separated by ',' vs '.'.
    '''
    if delimiter == ',':
        return '.'
    comma_decimals = len(re.findall(r'\d,\d', sample))
    dot_decimals = len(re.findall(r'\d\.\d', sample))
    return ',' if comma_decimals > dot_decimals else '.'


def _read_csv(file_bytes: bytes) -> pd.DataFrame:
    '''
        Reads a CSV robustly: strips the BOM, auto-detects the delimiter (comma,
        semicolon, tab or pipe) and the decimal separator from the data, and
        skips the odd malformed line instead of failing the whole file.
    '''
    sample = file_bytes[:65536].decode('utf-8-sig', errors = 'replace')
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters = _CSV_DELIMITERS).delimiter
    except csv.Error:
        delimiter = ','
    decimal = _detect_decimal(sample, delimiter)
    message = f'CSV delimiter detected: {delimiter!r} (decimal={decimal!r}).'
    logger.info(message)
    return pd.read_csv(
        BytesIO(file_bytes), sep = delimiter, decimal = decimal,
        encoding = 'utf-8-sig', on_bad_lines = 'skip'
    )


def read_dataframe(
    file_bytes: bytes,
    filename: str
) -> pd.DataFrame:
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

    # One file, one contract: the first sheet IS the contract. The four-sheet
    # workbook this used to scan was our own invention and it is what forced
    # the service to read S3 by itself, because the FILES reader —correctly—
    # returns one flat table.
    if lower.endswith('.xlsx'):
        return pd.read_excel(BytesIO(file_bytes), engine = 'openpyxl')
    if lower.endswith('.csv'):
        return _read_csv(file_bytes)

    raise ValueError(
        f'Formato de archivo no soportado: "{filename}". Use {", ".join(SUPPORTED_EXTENSIONS)}.'
    )



def serialize_dataframe(
    dataframe: pd.DataFrame,
    filename: str
) -> bytes:
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


@lru_cache(maxsize = 1)
def read_file(
    file_bytes: bytes,
    filename: str
) -> pd.DataFrame:
    '''
        Reads an uploaded file into a DataFrame. Public because the collections
        pipeline reads the same formats through the same door.

        Args:
            file_bytes (bytes): Raw uploaded file content.
            filename (str): Original filename; drives format detection.

        Returns:
            pd.DataFrame: Raw DataFrame, no validation yet.

        Raises:
            ValueError: If the file extension is not supported.
    '''
    return read_dataframe(file_bytes, filename)
