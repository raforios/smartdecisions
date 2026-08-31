'''
    Ingest business logic: reads the uploaded sales file, maps its headers to
    the canonical contract, validates it and derives the summary metrics.

    Everything here is driven by SALES_COLUMNS in schemas/ingest.py, which is
    the single definition of the format: the header mapping, the DataFrame
    schema and the required/optional split are all derived from it, so the
    contract is stated once and cannot drift between layers.

    Supports .xlsx (via openpyxl) and .csv. Failures are reported as stable
    CODES, never as sentences: the wording the user reads belongs to whoever
    renders it.
'''
import csv
import re
import unicodedata
from dataclasses import dataclass
from io import BytesIO
from typing import Final, Optional

import pandas as pd
import pandera.pandas as pa
from pandera.errors import SchemaErrors

from schemas.ingest import (
    REQUIRED_COLUMNS,
    OPTIONAL_COLUMNS,
    SALES_COLUMNS,
    TEMPLATE_VERSION,
    IngestSummary,
    SalesColumn,
    ValidationIssue,
    ValidationRule
)
from services.logger_config import custom_logger as logger


# ---------------------------------------------------------------------------
# Header mapping
# ---------------------------------------------------------------------------

def _normalize_header(header: object) -> str:
    '''
        Lowercases, strips accents and asterisks, and collapses whitespace so a
        header matches regardless of formatting (e.g. 'Código SAP *' ->
        'codigo sap').

        Args:
            header (object): Raw header as written in the source file.

        Returns:
            str: Normalized form used for matching.
    '''
    text = unicodedata.normalize('NFKD', str(header))
    text = ''.join(char for char in text if not unicodedata.combining(char))
    text = text.lower().replace('*', ' ')
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', text)).strip()


def _build_header_lookup() -> dict[str, str]:
    '''
        Builds the {normalized header: canonical name} lookup from the contract.

        Both the template header the client fills in and the canonical name
        itself are accepted, so a file already using the contract's names also
        ingests.

        Returns:
            dict[str, str]: Lookup used by map_columns.
    '''
    lookup: dict[str, str] = {}
    for column in SALES_COLUMNS:
        lookup[_normalize_header(column.header)] = column.canonical
        lookup[_normalize_header(column.canonical)] = column.canonical
    return lookup


_HEADER_LOOKUP: Final[dict[str, str]] = _build_header_lookup()


def map_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    '''
        Renames the source columns to the canonical contract names.

        Columns outside the contract are left as-is; the schema's
        `strict='filter'` drops them afterwards. If two source columns map to
        the same canonical name the first wins, so nothing is silently
        overwritten.

        Args:
            dataframe (pd.DataFrame): Raw frame parsed from the user's file.

        Returns:
            pd.DataFrame: The same frame with recognized columns renamed.
    '''
    rename_map: dict[object, str] = {}
    already_taken: set[str] = set()
    for original in dataframe.columns:
        canonical = _HEADER_LOOKUP.get(_normalize_header(original))
        if canonical and canonical not in already_taken:
            rename_map[original] = canonical
            already_taken.add(canonical)
    return dataframe.rename(columns = rename_map)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _checks_for(column: SalesColumn) -> list[pa.Check]:
    '''
        Translates the contract's value rules into pandera checks.

        Args:
            column (SalesColumn): Contract definition of the column.

        Returns:
            list[pa.Check]: Checks to attach to the pandera column.
    '''
    rules = column.rules
    checks: list[pa.Check] = []
    if rules.max_length is not None:
        checks.append(pa.Check.str_length(min_value = 1, max_value = rules.max_length))
    if rules.exclusive_minimum is not None:
        checks.append(pa.Check.greater_than(rules.exclusive_minimum))
    if rules.minimum is not None:
        checks.append(pa.Check.greater_than_or_equal_to(rules.minimum))
    if rules.value_range is not None:
        checks.append(pa.Check.in_range(*rules.value_range))
    return checks


def _build_schema() -> pa.DataFrameSchema:
    '''
        Builds the DataFrame schema from the contract.

        Returns:
            pa.DataFrameSchema: Schema in 'filter' mode, so unknown columns are
                dropped instead of failing the whole file.
    '''
    columns = {
        column.canonical: pa.Column(
            dtype = column.dtype,
            nullable = not column.required,
            required = column.required,
            coerce = True,
            checks = _checks_for(column)
        )
        for column in SALES_COLUMNS
    }
    return pa.DataFrameSchema(
        columns = columns,
        strict = 'filter',
        coerce = True,
        ordered = False,
        description = (
            f'SmartDecisions sales contract {TEMPLATE_VERSION}. Required: '
            f'{", ".join(REQUIRED_COLUMNS)}. Optional: {", ".join(OPTIONAL_COLUMNS)}.'
        )
    )


SCHEMA: Final[pa.DataFrameSchema] = _build_schema()

# Pandera reports parameterized check names ("greater_than(0)",
# "coerce_dtype('datetime64[ns]')"). They map to a stable code by prefix; the
# wording the user reads lives in the frontend catalogue.
_RULE_CODES: Final[tuple[tuple[str, ValidationRule], ...]] = (
    ('not_nullable', ValidationRule.REQUIRED_VALUE),
    ('coerce_dtype', ValidationRule.INVALID_TYPE),
    ('dtype', ValidationRule.INVALID_TYPE),
    ('str_length', ValidationRule.TEXT_LENGTH),
    ('greater_than_or_equal_to', ValidationRule.BELOW_MINIMUM),
    ('greater_than', ValidationRule.BELOW_MINIMUM),
    ('in_range', ValidationRule.OUT_OF_RANGE),
    ('column_in_schema', ValidationRule.UNKNOWN_COLUMN),
    ('column_in_dataframe', ValidationRule.MISSING_COLUMN),
)


@dataclass(frozen = True)
class ValidationResult:
    '''
        Outcome of validating a sales frame: the coerced rows and every issue
        found. A dataclass rather than a tuple so callers read `result.issues`
        instead of `result[1]`, and rather than a Pydantic model because it
        carries a DataFrame, which is not serializable.
    '''
    frame: pd.DataFrame
    issues: list[ValidationIssue]

    @property
    def is_valid(self) -> bool:
        '''
            Whether the frame passed the contract with no issues.

            Returns:
                bool: True when nothing failed validation.
        '''
        return not self.issues


def _rule_code(check_name: Optional[str]) -> ValidationRule:
    '''
        Maps a pandera check name to the stable code the API exposes.

        Args:
            check_name (str | None): Pandera check identifier.

        Returns:
            ValidationRule: The matching code, or INVALID_VALUE as a fallback.
    '''
    if not check_name:
        return ValidationRule.INVALID_VALUE
    for prefix, code in _RULE_CODES:
        if check_name.startswith(prefix):
            return code
    return ValidationRule.INVALID_VALUE


def validate(dataframe: pd.DataFrame) -> ValidationResult:
    '''
        Validates a sales DataFrame against the v1 template contract.

        Lazy mode: collects all errors instead of failing on the first.

        Args:
            dataframe (pd.DataFrame): Raw DataFrame parsed from the user's Excel.

        Returns:
            ValidationResult: The coerced frame (or the original on full
                failure) and every issue found, empty when the file is valid.
    '''
    issues: list[ValidationIssue] = []

    if dataframe.empty:
        issues.append(ValidationIssue(
            row = 0, column = '', value = None,
            rule_code = ValidationRule.EMPTY_FILE
        ))
        return ValidationResult(frame = dataframe, issues = issues)

    try:
        return ValidationResult(frame = SCHEMA.validate(dataframe, lazy = True), issues = [])
    except SchemaErrors as schema_errors:
        failure_cases = schema_errors.failure_cases
        for _, failure in failure_cases.iterrows():
            row_idx = failure.get('index')
            row_number = int(row_idx) + 2 if pd.notna(row_idx) else 0
            check_name = failure.get('check') or 'unknown'
            raw_failure_value = failure.get('failure_case')
            # Schema-level checks (e.g. missing/extra column) carry the
            # offending column name in `failure_case`, not in `column`.
            if check_name in ('column_in_dataframe', 'column_in_schema'):
                column_name = str(raw_failure_value)
                value_repr = None
            else:
                column_name = str(failure.get('column') or '(global)')
                value_repr = None if pd.isna(raw_failure_value) else str(raw_failure_value)
            issues.append(ValidationIssue(
                row = row_number,
                column = column_name,
                value = value_repr,
                rule_code = _rule_code(str(check_name))
            ))

        message = (
            f'Excel validation found {len(issues)} issue(s) across '
            f'{failure_cases["column"].nunique()} column(s).'
        )
        logger.info(message)
        return ValidationResult(frame = dataframe, issues = issues)


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


SUPPORTED_EXTENSIONS: Final[tuple[str, ...]] = ('.xlsx', '.csv')

# Column added to the rejected-rows file. It carries ValidationRule codes,
# not sentences: whoever shows them (frontend today, interpretation layer
# tomorrow) owns the wording.
_RULE_CODES_COLUMN: Final[str] = 'rule_codes'

# Delimiters a Latin-American CSV export may use. Excel in es-locale defaults to
# ';' (because ',' is the decimal separator), so we auto-detect rather than
# assume ','.
_CSV_DELIMITERS: Final[str] = ',;\t|'


def _detect_decimal(sample: str, delimiter: str) -> str:
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


def _parse_dates(dataframe: pd.DataFrame) -> pd.DataFrame:
    '''
        Coerces the 'date' column to datetime. Unparseable dates become NaT so
        the validator flags (and the partial pipeline rejects) those rows.

        Args:
            dataframe (pd.DataFrame): Mapped DataFrame.

        Returns:
            pd.DataFrame: Same frame with 'date' as datetime64.
    '''
    if 'date' in dataframe.columns:
        dataframe['date'] = _coerce_dates(dataframe['date'])
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
        if name_column not in dataframe.columns:
            continue
        if id_column not in dataframe.columns:
            dataframe[id_column] = dataframe[name_column]
        else:
            missing = dataframe[id_column].isna()
            dataframe.loc[missing, id_column] = dataframe.loc[missing, name_column]
    return dataframe


_GEO_COLUMNS: Final[tuple[str, str]] = ('latitude', 'longitude')


def _sanitize_geo(dataframe: pd.DataFrame) -> pd.DataFrame:
    '''
        Nulls out unusable coordinate pairs so the route map never plots a
        placeholder as a real location.

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


def _summarize(dataframe: pd.DataFrame, error_rows: int) -> IngestSummary:
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


def _normalize(file_bytes: bytes, filename: str) -> pd.DataFrame:
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
    mapped = map_columns(_read_dataframe(file_bytes, filename))
    mapped = _stringify_ids(mapped)
    mapped = _fill_ids_from_names(mapped)
    mapped = _parse_dates(mapped)
    return _sanitize_geo(mapped)


def parse_and_validate(file_bytes: bytes, filename: str) -> ParseResult:
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


def _whole_file_rejection(mapped: pd.DataFrame,
                          issues: list[ValidationIssue]) -> ParseResult:
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


def parse_and_validate_partial(file_bytes: bytes, filename: str) -> ParseResult:
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
