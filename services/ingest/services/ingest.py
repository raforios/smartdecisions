'''
    The sales ingest pipeline: reads the uploaded file, maps its headers to the
    canonical contract, validates it, derives identifiers and totals, and
    produces the summary metrics. Partial acceptance is the rule: invalid rows
    are set aside with their reason codes and the rest is loaded.

    The contract machinery (lookups, schemas, validation) lives in
    `ingest_contract`; the file boundary (reading uploads, writing the
    normalized CSV) in `ingest_files`. This module is the sales pipeline that
    puts them together; the payments, stock and visits pipelines reuse the
    same pieces over their own sheets.
'''
from dataclasses import dataclass
from typing import Final

import pandas as pd

from schemas.ingest import (
    COLLECTION_COLUMNS,
    SALES_COLUMNS,
    STOCK_COLUMNS,
    VISIT_COLUMNS,
    IngestSummary,
    ValidationIssue,
    ValidationRule
)
from services.ingest_contract import (
    SALES_HEADER_LOOKUP,
    map_columns,
    normalize_header,
    validate
)
from services.ingest_files import read_file
from services.logger_config import custom_logger as logger


# ---------------------------------------------------------------------------
# Parsing pipeline
# ---------------------------------------------------------------------------

@dataclass(frozen = True)
class ParseResult:
    '''
        Outcome of ingesting one file.

        A dataclass rather than the tuple this used to return: callers read
        `result.summary` instead of `result[2]`, and adding a field no longer
        silently shifts every caller's indexes. It is not a Pydantic model
        because it carries DataFrames, which are not serializable.
    '''
    accepted: pd.DataFrame
    rejected: pd.DataFrame
    issues: list[ValidationIssue]
    summary: IngestSummary


# Column added to the rejected-rows file. It carries ValidationRule codes,
# not sentences: whoever shows them (frontend today, interpretation layer
# tomorrow) owns the wording.
_RULE_CODES_COLUMN: Final[str] = 'rule_codes'

_ID_COLUMNS = ('order_id', 'pos_id', 'product_id')


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


def _coerce_dates(values: pd.Series) -> pd.Series:
    '''
        Converts a date column to datetime, choosing between ISO and day-first
        parsing by which one actually reads the data.

        Both conventions reach us: Excel exports write real datetimes or
        dd/mm/aaaa (Bolivia), while a CSV produced by any system writes
        aaaa-mm-dd. Forcing day-first on ISO text is not merely ambiguous — it
        makes pandas infer '%Y-%d-%m' from the first value, so every date past
        the 12th of the month silently becomes NaT and the row is rejected.
        Whichever parse resolves more dates wins; ISO breaks the tie because a
        string starting with a 4-digit year is not a day-first date.

        Args:
            values (pd.Series): Raw date column (text or datetime).

        Returns:
            pd.Series: Parsed datetimes, NaT where genuinely unreadable.
    '''
    if pd.api.types.is_datetime64_any_dtype(values):
        return values

    iso = pd.to_datetime(values, format = 'ISO8601', errors = 'coerce')
    if iso.notna().all():
        return iso

    day_first = pd.to_datetime(values, dayfirst = True, errors = 'coerce')
    return day_first if day_first.notna().sum() > iso.notna().sum() else iso


# Every date column of every contract, not just the sale's: the due date and
# the payment date arrive in the same formats and through the same door.
_DATE_COLUMNS: Final[tuple[str, ...]] = tuple(dict.fromkeys(
    column.canonical
    for column in SALES_COLUMNS + COLLECTION_COLUMNS + STOCK_COLUMNS + VISIT_COLUMNS
    if column.dtype.startswith('datetime64')
))

# Closed-option columns are normalized before validating, because an ERP writes
# 'Crédito', 'credito' or 'CRÉDITO' for the same thing and rejecting the row
# over an accent would be rejecting correct data.
_OPTION_COLUMNS: Final[tuple[str, ...]] = tuple(dict.fromkeys(
    column.canonical
    for column in SALES_COLUMNS + COLLECTION_COLUMNS + STOCK_COLUMNS + VISIT_COLUMNS
    if column.rules.allowed is not None
))


def _parse_dates(dataframe: pd.DataFrame) -> pd.DataFrame:
    '''
        Coerces every contract date column to datetime. Unparseable dates
        become NaT so the validator flags (and the partial pipeline rejects)
        those rows.

        Args:
            dataframe (pd.DataFrame): Mapped DataFrame.

        Returns:
            pd.DataFrame: Same frame with its date columns as datetime64.
    '''
    for column in _DATE_COLUMNS:
        if column in dataframe.columns:
            dataframe[column] = _coerce_dates(dataframe[column])
    return dataframe


def _normalize_options(dataframe: pd.DataFrame) -> pd.DataFrame:
    '''
        Brings closed-option columns to the contract's spelling: uppercase, no
        accents, trimmed, and words joined by underscore the way the codes are
        written ('sin venta' and 'Sin-Venta' both read SIN_VENTA). A blank
        stays blank so the column remains optional.

        Args:
            dataframe (pd.DataFrame): Mapped DataFrame.

        Returns:
            pd.DataFrame: Same frame with its option columns normalized.
    '''
    for column in _OPTION_COLUMNS:
        if column not in dataframe.columns:
            continue
        dataframe[column] = dataframe[column].map(
            lambda value: pd.NA if pd.isna(value) or not str(value).strip()
            else normalize_header(value).upper().replace(' ', '_')
        )
    return dataframe


def fill_product_ids(dataframe: pd.DataFrame) -> pd.DataFrame:
    '''
        Derives `product_id` from the product name, the same way the sales
        pipeline does.

        Public because the stock contract needs exactly this and nothing else:
        the client writes 'Producto' and the service derives the code, so a
        snapshot marries the catalogue by the same identifier the sales rows
        were given.

        Args:
            dataframe (pd.DataFrame): Frame with canonical column names.

        Returns:
            pd.DataFrame: Same frame with `product_id` ensured.
    '''
    return _fill_from_name(dataframe, 'product_id', 'product_name')


def fill_pos_ids(dataframe: pd.DataFrame) -> pd.DataFrame:
    '''
        Derives `pos_id` from the client name, the same way the sales pipeline
        does. Public because the visits contract marries the client catalogue
        by the identifier the sales rows were given.

        Args:
            dataframe (pd.DataFrame): Frame with canonical column names.

        Returns:
            pd.DataFrame: Same frame with `pos_id` ensured.
    '''
    return _fill_from_name(dataframe, 'pos_id', 'pos_name')


def _fill_from_name(
    dataframe: pd.DataFrame,
    id_column: str,
    name_column: str
) -> pd.DataFrame:
    '''
        Fills one identifier column from its name column.

        Args:
            dataframe (pd.DataFrame): Frame with canonical column names.
            id_column (str): Identifier to ensure.
            name_column (str): Name it is derived from.

        Returns:
            pd.DataFrame: Same frame with the identifier ensured.
    '''
    if name_column not in dataframe.columns:
        return dataframe
    if id_column not in dataframe.columns:
        dataframe[id_column] = dataframe[name_column]
    else:
        missing = dataframe[id_column].isna()
        dataframe.loc[missing, id_column] = dataframe.loc[missing, name_column]
    return dataframe


def _fill_ids_from_names(dataframe: pd.DataFrame) -> pd.DataFrame:
    '''
        Uses the client/product NAME as its identifier when no explicit code is
        provided. The friendly template only asks for 'Cliente' and 'Producto'
        (mapped to pos_name / product_name), so the required id columns are
        filled from those names; a raw ERP export that already carries codes is
        left untouched.

        Args:
            dataframe (pd.DataFrame): DataFrame with canonical column names.

        Returns:
            pd.DataFrame: Same frame with pos_id / product_id ensured.
    '''
    for id_column, name_column in (
        ('pos_id', 'pos_name'),
        ('product_id', 'product_name'),
    ):
        dataframe = _fill_from_name(dataframe, id_column, name_column)
    return dataframe


_GEO_COLUMNS: Final[tuple[str, str]] = ('latitude', 'longitude')


def sanitize_geo(dataframe: pd.DataFrame) -> pd.DataFrame:
    '''
        Nulls out unusable coordinate pairs so the route map never plots a
        placeholder as a real location. Public because the visits contract
        carries the same pair and gets the same placeholders.

        ERP exports fill missing GPS readings with a literal 0, which would
        otherwise render as a valid point off the coast of Africa and drag the
        whole map away from the client's city. An exact 0 is treated as "no
        data" because a genuine reading always carries decimals. Both members
        of the pair are cleared together: half a coordinate is not a location.

        Args:
            dataframe (pd.DataFrame): Mapped DataFrame, before validation.

        Returns:
            pd.DataFrame: Same frame with unusable coordinates set to NA.
    '''
    if not all(column in dataframe.columns for column in _GEO_COLUMNS):
        return dataframe

    latitude = pd.to_numeric(dataframe['latitude'], errors = 'coerce')
    longitude = pd.to_numeric(dataframe['longitude'], errors = 'coerce')
    unusable = (
        latitude.isna() | longitude.isna()
        | (latitude == 0) | (longitude == 0)
        | ~latitude.between(-90, 90) | ~longitude.between(-180, 180)
    )

    dataframe['latitude'] = latitude.mask(unusable)
    dataframe['longitude'] = longitude.mask(unusable)

    dropped = int(unusable.sum())
    if dropped:
        message = f'Sanitized {dropped} row(s) with unusable coordinates.'
        logger.info(message)
    return dataframe


def _derive_total_amount(dataframe: pd.DataFrame) -> pd.DataFrame:
    '''
        Fills missing 'total_amount' as quantity * unit_price when both
        operands are available; leaves NaN otherwise.

        Args:
            dataframe (pd.DataFrame): Validated DataFrame.

        Returns:
            pd.DataFrame: Same frame with 'total_amount' completed where possible.
    '''
    if 'total_amount' not in dataframe.columns:
        dataframe['total_amount'] = pd.NA

    # Derivation requires both operands; when unit_price is absent there
    # is nothing to multiply, so total_amount stays as-is (typically NA).
    if 'unit_price' not in dataframe.columns or 'quantity' not in dataframe.columns:
        return dataframe

    has_inputs = dataframe['quantity'].notna() & dataframe['unit_price'].notna()
    missing_total = dataframe['total_amount'].isna() & has_inputs
    dataframe.loc[missing_total, 'total_amount'] = (
        dataframe.loc[missing_total, 'quantity']
        * dataframe.loc[missing_total, 'unit_price']
    )
    return dataframe


def _summarize(
    dataframe: pd.DataFrame,
    error_rows: int
) -> IngestSummary:
    '''
        Computes the IngestSummary metrics from a validated DataFrame.

        Args:
            dataframe (pd.DataFrame): The validated DataFrame.
            error_rows (int): Number of rows flagged as invalid.

        Returns:
            IngestSummary: The metrics describing what was ingested.
    '''
    total = int(len(dataframe))
    start, end = None, None
    if 'date' in dataframe.columns and dataframe['date'].notna().any():
        parsed = pd.to_datetime(dataframe['date'], errors = 'coerce')
        start = parsed.min().date().isoformat()
        end = parsed.max().date().isoformat()

    return IngestSummary(
        total_rows = total,
        valid_rows = max(total - error_rows, 0),
        error_rows = error_rows,
        unique_points_of_sale = (
            int(dataframe['pos_id'].nunique())
            if 'pos_id' in dataframe else 0
        ),
        unique_products = (
            int(dataframe['product_id'].nunique())
            if 'product_id' in dataframe else 0
        ),
        date_range_start = start,
        date_range_end = end
    )


def normalize_frame(
    dataframe: pd.DataFrame,
    lookup: dict[str, str]
) -> pd.DataFrame:
    '''
        Brings a raw frame to a canonical contract: headers, ids, dates and
        closed options.

        Shared by both contracts on purpose. What the sales pipeline adds on top
        —deriving ids from names and sanitizing coordinates— belongs only to it.

        Args:
            dataframe (pd.DataFrame): Raw frame parsed from the user's file.
            lookup (dict[str, str]): Contract header lookup.

        Returns:
            pd.DataFrame: The mapped, cleaned frame.
    '''
    mapped = map_columns(dataframe, lookup)
    mapped = _stringify_ids(mapped)
    mapped = _parse_dates(mapped)
    return _normalize_options(mapped)


def _normalize(
    file_bytes: bytes,
    filename: str
) -> pd.DataFrame:
    '''
        Reads the file and brings it to the canonical column contract.

        Args:
            file_bytes (bytes): Raw uploaded file content.
            filename (str): Original filename (drives format detection).

        Returns:
            pd.DataFrame: Mapped frame with clean ids, dates and coordinates.
    '''
    # Map the published template's headers to the canonical names before
    # validating, then clean numeric codes and fill the required id columns
    # from the client and product names, which is all the template carries.
    mapped = normalize_frame(read_file(file_bytes, filename), SALES_HEADER_LOOKUP)
    mapped = _fill_ids_from_names(mapped)
    return sanitize_geo(mapped)


def parse_and_validate(
    file_bytes: bytes,
    filename: str
) -> ParseResult:
    '''
        End-to-end ingest pipeline: read, validate, derive, summarize.

        Rejects the file as a whole when anything fails; use
        `parse_and_validate_partial` to keep the usable rows instead.

        Args:
            file_bytes (bytes): Raw uploaded file content.
            filename (str): Original filename (drives format detection).

        Returns:
            ParseResult: Accepted rows, issues and summary. `rejected` is empty.

        Raises:
            ValueError: On unsupported extension or unreadable content.
    '''
    mapped = _normalize(file_bytes, filename)
    validation = validate(mapped)

    accepted = validation.frame
    if validation.is_valid:
        accepted = _derive_total_amount(accepted)

    summary = _summarize(accepted, error_rows = len(validation.issues))
    message = (
        f'Ingest pipeline processed file "{filename}": '
        f'{summary.valid_rows}/{summary.total_rows} rows valid, '
        f'{summary.error_rows} issue(s).'
    )
    logger.info(message)

    return ParseResult(
        accepted = accepted,
        rejected = mapped.iloc[0:0],
        issues = validation.issues,
        summary = summary
    )


_FILE_LEVEL_RULES: Final[tuple[ValidationRule, ...]] = (
    ValidationRule.MISSING_COLUMN,
    ValidationRule.UNKNOWN_COLUMN,
)


def _whole_file_rejection(
    mapped: pd.DataFrame,
    issues: list[ValidationIssue]
) -> ParseResult:
    '''
        Builds the result for a file that cannot be processed at all.

        Args:
            mapped (pd.DataFrame): The normalized frame, rejected in full.
            issues (list[ValidationIssue]): What went wrong.

        Returns:
            ParseResult: Nothing accepted, everything rejected.
    '''
    rejected = mapped.copy()
    rejected[_RULE_CODES_COLUMN] = '; '.join(
        sorted({issue.rule_code.value for issue in issues})
    )
    summary = _summarize(mapped.iloc[0:0], error_rows = 0)
    return ParseResult(
        accepted = mapped.iloc[0:0],
        rejected = rejected,
        issues = issues,
        summary = summary.model_copy(update = {
            'total_rows': len(rejected),
            'valid_rows': 0,
            'error_rows': len(rejected),
        })
    )


def _codes_by_row(issues: list[ValidationIssue]) -> dict[int, list[str]]:
    '''
        Groups the failed columns and their rule codes by DataFrame index.

        Args:
            issues (list[ValidationIssue]): Cell-level issues; `row` is the
                Excel row number, which is the frame index plus two.

        Returns:
            dict[int, list[str]]: 'column=CODE' pairs per frame index.
    '''
    codes: dict[int, list[str]] = {}
    for issue in issues:
        index = issue.row - 2
        if index >= 0:
            codes.setdefault(index, []).append(f'{issue.column}={issue.rule_code.value}')
    return codes


def parse_and_validate_partial(
    file_bytes: bytes,
    filename: str
) -> ParseResult:
    '''
        Partial-acceptance pipeline: keeps the usable rows and sets the rest
        aside so the client can fix and re-upload just those.

        A missing required column fails the whole file — no row can be saved.
        Otherwise every row with a cell-level issue moves to `rejected`, carrying
        a Spanish reason, because that frame is downloaded as a CSV.

        Args:
            file_bytes (bytes): Raw uploaded file content.
            filename (str): Original filename (drives format detection).

        Returns:
            ParseResult: Accepted rows, rejected rows with their reason, the
                issues found and the summary over the whole file.
    '''
    mapped = _normalize(file_bytes, filename)
    issues = validate(mapped).issues

    if any(issue.rule_code in _FILE_LEVEL_RULES for issue in issues):
        return _whole_file_rejection(mapped, issues)

    codes = _codes_by_row(issues)
    bad_index = [index for index in codes if index in mapped.index]

    accepted = _derive_total_amount(
        validate(mapped.drop(index = bad_index, errors = 'ignore')).frame
    )
    rejected = mapped.loc[bad_index].copy()
    rejected[_RULE_CODES_COLUMN] = ['; '.join(codes[index]) for index in bad_index]

    summary = _summarize(accepted, error_rows = 0).model_copy(update = {
        'total_rows': len(accepted) + len(rejected),
        'valid_rows': len(accepted),
        'error_rows': len(rejected),
    })
    message = (
        f'Partial ingest of "{filename}": {len(accepted)} accepted, '
        f'{len(rejected)} rejected.'
    )
    logger.info(message)

    return ParseResult(
        accepted = accepted, rejected = rejected, issues = issues, summary = summary
    )
