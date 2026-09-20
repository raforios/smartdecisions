'''
    The ingest contracts as machinery: header mapping, DataFrame schemas and
    validation for every sheet the product reads (sales, payments, stock,
    visits).

    Everything here is derived from the column declarations in
    schemas/ingest.py, which is the single definition of each format: the
    header lookup, the pandera schema and the rule codes come from the same
    tuple, so a contract is stated once and cannot drift between layers.

    Failures are reported as stable CODES, never as sentences: the wording the
    user reads belongs to whoever renders it.
'''
import re
import unicodedata
from dataclasses import dataclass
from typing import Final, Optional

import pandas as pd
import pandera.pandas as pa
from pandera.errors import SchemaErrors

from schemas.ingest import (
    COLLECTION_COLUMNS,
    OPTIONAL_COLUMNS,
    REQUIRED_COLUMNS,
    SALES_COLUMNS,
    STOCK_COLUMNS,
    VISIT_COLUMNS,
    TEMPLATE_VERSION,
    SalesColumn,
    ValidationIssue,
    ValidationRule
)
from services.logger_config import custom_logger as logger


# ---------------------------------------------------------------------------
# Header mapping
# ---------------------------------------------------------------------------

def normalize_header(header: object) -> str:
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


def _build_header_lookup(columns: tuple[SalesColumn, ...]) -> dict[str, str]:
    '''
        Builds the {normalized header: canonical name} lookup of a contract.

        Both the template header the client fills in and the canonical name
        itself are accepted, so a file already using the contract's names also
        ingests.

        Args:
            columns (tuple[SalesColumn, ...]): The contract to read.

        Returns:
            dict[str, str]: Lookup used by map_columns.
    '''
    lookup: dict[str, str] = {}
    for column in columns:
        lookup[normalize_header(column.header)] = column.canonical
        lookup[normalize_header(column.canonical)] = column.canonical
    return lookup


SALES_HEADER_LOOKUP: Final[dict[str, str]] = _build_header_lookup(SALES_COLUMNS)
COLLECTION_HEADER_LOOKUP: Final[dict[str, str]] = _build_header_lookup(COLLECTION_COLUMNS)
STOCK_HEADER_LOOKUP: Final[dict[str, str]] = _build_header_lookup(STOCK_COLUMNS)
VISIT_HEADER_LOOKUP: Final[dict[str, str]] = _build_header_lookup(VISIT_COLUMNS)


def map_columns(
    dataframe: pd.DataFrame,
    lookup: Optional[dict[str, str]] = None
) -> pd.DataFrame:
    '''
        Renames the source columns to the canonical contract names.

        Columns outside the contract are left as-is; the schema's
        `strict='filter'` drops them afterwards. If two source columns map to
        the same canonical name the first wins, so nothing is silently
        overwritten.

        Args:
            dataframe (pd.DataFrame): Raw frame parsed from the user's file.
            lookup (dict[str, str] | None): Contract lookup; the sales one by
                default, so every existing caller keeps its behaviour.

        Returns:
            pd.DataFrame: The same frame with recognized columns renamed.
    '''
    headers = lookup if lookup is not None else SALES_HEADER_LOOKUP
    rename_map: dict[object, str] = {}
    already_taken: set[str] = set()
    for original in dataframe.columns:
        canonical = headers.get(normalize_header(original))
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
    if rules.allowed is not None:
        checks.append(pa.Check.isin(rules.allowed))
    return checks


def _build_schema(
    columns: tuple[SalesColumn, ...],
    description: str
) -> pa.DataFrameSchema:
    '''
        Builds the DataFrame schema of a contract.

        Args:
            columns (tuple[SalesColumn, ...]): The contract to enforce.
            description (str): What the schema is, for the error report.

        Returns:
            pa.DataFrameSchema: Schema in 'filter' mode, so unknown columns are
                dropped instead of failing the whole file.
    '''
    declared = {
        column.canonical: pa.Column(
            dtype = column.dtype,
            nullable = not column.required,
            required = column.required,
            coerce = True,
            checks = _checks_for(column)
        )
        for column in columns
    }
    return pa.DataFrameSchema(
        columns = declared,
        strict = 'filter',
        coerce = True,
        ordered = False,
        description = description
    )


SCHEMA: Final[pa.DataFrameSchema] = _build_schema(
    SALES_COLUMNS,
    f'SmartDecisions sales contract {TEMPLATE_VERSION}. Required: '
    f'{", ".join(REQUIRED_COLUMNS)}. Optional: {", ".join(OPTIONAL_COLUMNS)}.'
)

# The other contracts are validated with the same machinery: they are the
# same kind of declaration read over a different sheet.
COLLECTIONS_SCHEMA: Final[pa.DataFrameSchema] = _build_schema(
    COLLECTION_COLUMNS,
    f'SmartDecisions collections contract {TEMPLATE_VERSION}. Required: '
    f'{", ".join(column.canonical for column in COLLECTION_COLUMNS if column.required)}.'
)

STOCK_SCHEMA: Final[pa.DataFrameSchema] = _build_schema(
    STOCK_COLUMNS,
    f'SmartDecisions stock contract {TEMPLATE_VERSION}. Required: '
    f'{", ".join(column.canonical for column in STOCK_COLUMNS if column.required)}.'
)

VISITS_SCHEMA: Final[pa.DataFrameSchema] = _build_schema(
    VISIT_COLUMNS,
    f'SmartDecisions visits contract {TEMPLATE_VERSION}. Required: '
    f'{", ".join(column.canonical for column in VISIT_COLUMNS if column.required)}.'
)

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


def validate(
    dataframe: pd.DataFrame,
    schema: Optional[pa.DataFrameSchema] = None
) -> ValidationResult:
    '''
        Validates a DataFrame against a published contract.

        Lazy mode: collects all errors instead of failing on the first.

        Args:
            dataframe (pd.DataFrame): Raw DataFrame parsed from the user's file.
            schema (pa.DataFrameSchema | None): Contract to enforce; the sales
                one by default.

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

    contract = schema if schema is not None else SCHEMA
    try:
        return ValidationResult(frame = contract.validate(dataframe, lazy = True), issues = [])
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
            f'Validation of "{contract.description}" found {len(issues)} issue(s) '
            f'across {failure_cases["column"].nunique()} column(s).'
        )
        logger.info(message)
        return ValidationResult(frame = dataframe, issues = issues)


def unknown_value_issues(
    frame: pd.DataFrame,
    column: str,
    known: set,
    rule: ValidationRule
) -> list[ValidationIssue]:
    '''
        Flags the rows whose value in one column is not in a catalogue the
        dataset knows: a product not in the sales, a client never invoiced, a
        seller the file never names. Reported and never dropped — deciding
        what an unknown means is not this service's call.

        Args:
            frame (pd.DataFrame): Validated rows of a companion contract.
            column (str): Column to check.
            known (set): Values the dataset knows, as text.
            rule (ValidationRule): Code to report.

        Returns:
            list[ValidationIssue]: One issue per unknown row.
    '''
    unknown = frame.loc[~frame[column].astype(str).isin(known)]
    return [
        ValidationIssue(
            row = int(position) + 2,
            column = column,
            value = str(row[column]),
            rule_code = rule
        )
        for position, row in unknown.iterrows()
    ]
