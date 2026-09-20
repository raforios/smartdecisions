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
from typing import Final, Optional

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

    if lower.endswith('.xlsx'):
        sheets = read_workbook(file_bytes)
        return next(iter(sheets.values())) if sheets else pd.DataFrame()
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
def read_workbook(file_bytes: bytes) -> dict[str, pd.DataFrame]:
    '''
        Opens an .xlsx once and returns every sheet by name.

        The sales, payments and stock pipelines each look for their own sheet
        in the same workbook, and opening a 2.6 MB book with openpyxl takes
        about ten seconds: three opens blew the 30 s Lambda budget. Keyed on
        the content, so the three reads of one upload share a single parse.

        Args:
            file_bytes (bytes): Raw .xlsx content.

        Returns:
            dict[str, pd.DataFrame]: Sheets in workbook order.
    '''
    return pd.read_excel(BytesIO(file_bytes), sheet_name = None, engine = 'openpyxl')


def read_sheet(
    file_bytes: bytes,
    filename: str,
    sheet_name: str,
    auto: bool = False
) -> Optional[pd.DataFrame]:
    '''
        Reads one companion contract out of an upload: the sheet of that name
        inside a workbook, or the whole file when it was uploaded on its own.

        `auto` is the difference between "this file IS a payments/stock/visits
        file" and "look inside this sales workbook in case it also brings that
        sheet". It matters: read in auto mode, a sales CSV would be parsed as
        payments and reported as a broken contract, when the client simply
        sells cash.

        Args:
            file_bytes (bytes): Raw uploaded file content.
            filename (str): Original filename; drives format detection.
            sheet_name (str): Sheet the contract lives on, matched ignoring
                case and surrounding blanks.
            auto (bool): True when scanning a sales upload, so a file without
                the sheet comes back empty and silent.

        Returns:
            pd.DataFrame | None: The raw frame, or None when there is nothing
                to read.

        Raises:
            ValueError: On an unsupported extension or unreadable content.
    '''
    if filename.lower().endswith('.xlsx'):
        for name, frame in read_workbook(file_bytes).items():
            if str(name).strip().lower() == sheet_name.lower():
                return frame
    # A file uploaded AS the contract may name its sheet anything, or be a
    # CSV; one being scanned in passing may not.
    return None if auto else read_file(file_bytes, filename)


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
