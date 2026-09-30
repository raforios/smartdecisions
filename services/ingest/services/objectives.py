'''
    Objectives ingest — what the company DECIDED each client should buy.

    Every other contract in the product reports something that happened: a
    sale, a payment, a stock count, a visit. This one is the exception, and
    that is the whole reason it exists as its own contract. No amount of
    transactional history implies an objective: it is a decision, taken by the
    commercial team before the month starts, and nothing in a sales file can
    be mined for it.

    It arrives per client and per MONTH because that is the grain the
    commercial team manages, and one objective is then measured twice — once
    against what was invoiced and once against what was actually collected.
    Those are different questions: a client can hit their objective on paper
    and still owe every bolivian of it.

    Two rules that are the point of this module:
        * A load is IDEMPOTENT by client and period. Sending March again
          corrects March instead of leaving two objectives for it — objectives
          get revised mid-quarter, and a second truth for one month makes
          every percentage below it meaningless.
        * An objective for a client the sales dataset never billed is
          REPORTED, never dropped. It is the ordinary case of a client the
          company expects to activate, and it is exactly the row a manager
          needs to see.
'''
from dataclasses import dataclass
from datetime import date, datetime
from typing import Final

import pandas as pd

from schemas.ingest import (
    ObjectivesSummary,
    ValidationIssue,
    ValidationRule
)
from services.ingest import fill_pos_ids, normalize_frame, rows_with_issues
from services.ingest_contract import (
    AMOUNT_DECIMALS,
    OBJECTIVE_HEADER_LOOKUP,
    OBJECTIVES_SCHEMA,
    unknown_value_issues,
    validate
)
from services.ingest_files import read_file
from services.logger_config import custom_logger as logger

_POS = 'pos_id'
_PERIOD = 'period'
_TARGET = 'target_amount'

# A period is a month, written as the ISO date is written so it sorts as text:
# 'YYYY-MM'. Anything else is reported rather than guessed — reading '03/2025'
# as March of 2025 and '2025/03' as the same thing is how a quarter silently
# lands in the wrong column.
_PERIOD_PATTERN: Final[str] = r'^\d{4}-(0[1-9]|1[0-2])$'

# Issues that describe the FILE and not a row. With one of these no row can
# be saved, so partial acceptance does not apply.
_STRUCTURAL_RULES: Final[tuple[ValidationRule, ...]] = (
    ValidationRule.MISSING_COLUMN,
    ValidationRule.EMPTY_FILE
)


@dataclass(frozen = True)
class ObjectivesResult:
    '''
        Outcome of ingesting one objectives file.

        A dataclass and not a Pydantic model because it carries a DataFrame,
        which is not serializable.
    '''
    accepted: pd.DataFrame
    issues: list[ValidationIssue]
    summary: ObjectivesSummary


def _normalize(dataframe: pd.DataFrame) -> pd.DataFrame:
    '''
        Brings a raw objectives frame to the canonical contract.

        Args:
            dataframe (pd.DataFrame): Raw frame parsed from the user's file.

        Returns:
            pd.DataFrame: Canonical objective rows.
    '''
    frame = fill_pos_ids(normalize_frame(dataframe, OBJECTIVE_HEADER_LOOKUP))
    if _PERIOD in frame.columns:
        frame[_PERIOD] = frame[_PERIOD].map(_as_month)
    return frame


def _as_month(value: object) -> object:
    '''
        The month a period cell names, as 'YYYY-MM'.

        Excel turns a cell that looks like a date into a real date, so a
        client who typed 2025-01 can reach us as a Timestamp. Reading that
        back as its own month is not guessing. Anything else is left exactly
        as written, for the pattern check to report — reading '03/2025' as
        March would be guessing, and a quarter in the wrong column is worse
        than a rejected row.

        Args:
            value (object): The cell as it arrived.

        Returns:
            object: 'YYYY-MM', or the value untouched.
    '''
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return f'{value.year:04d}-{value.month:02d}'
    return str(value).strip() if not pd.isna(value) else value


def _malformed_period_issues(frame: pd.DataFrame) -> list[ValidationIssue]:
    '''
        Flags the rows whose period is not a 'YYYY-MM' month.

        Args:
            frame (pd.DataFrame): Validated objective rows.

        Returns:
            list[ValidationIssue]: One issue per malformed row.
    '''
    if _PERIOD not in frame.columns:
        return []
    periods = frame[_PERIOD].astype(str).str.strip()
    malformed = frame.loc[~periods.str.match(_PERIOD_PATTERN)]
    return [
        ValidationIssue(
            row = int(position) + 2,
            column = _PERIOD,
            value = str(row[_PERIOD]),
            rule_code = ValidationRule.INVALID_VALUE
        )
        for position, row in malformed.iterrows()
    ]


def _summarize(
    objectives: pd.DataFrame,
    known_clients: set,
    error_rows: int
) -> ObjectivesSummary:
    '''
        Derives the summary of an objectives load.

        Args:
            objectives (pd.DataFrame): Accepted objective rows.
            known_clients (set): Clients the sales dataset knows, as text.
            error_rows (int): How many rows were reported as issues.

        Returns:
            ObjectivesSummary: Counts, amount and the covered period range.
    '''
    if objectives.empty:
        return ObjectivesSummary(total_rows = error_rows, error_rows = error_rows)

    matched = objectives.loc[objectives[_POS].astype(str).isin(known_clients)]
    periods = objectives[_PERIOD].astype(str).sort_values()

    return ObjectivesSummary(
        total_rows = int(len(objectives)) + error_rows,
        valid_rows = int(len(objectives)),
        error_rows = error_rows,
        clients_with_objective = int(objectives[_POS].nunique()),
        unmatched_rows = int(len(objectives) - len(matched)),
        periods_count = int(periods.nunique()),
        target_amount = round(float(objectives[_TARGET].sum()), AMOUNT_DECIMALS),
        period_start = periods.iloc[0],
        period_end = periods.iloc[-1]
    )


def parse_and_validate(
    file_bytes: bytes,
    filename: str,
    sales: pd.DataFrame
) -> ObjectivesResult:
    '''
        End-to-end objectives pipeline: read, validate, match, summarize.

        Args:
            file_bytes (bytes): Raw uploaded file content.
            filename (str): Original filename; drives format detection.
            sales (pd.DataFrame): The normalized sales frame of the dataset
                the objectives belong to.

        Returns:
            ObjectivesResult: Accepted objectives, issues and summary.

        Raises:
            ValueError: On an unsupported extension or unreadable content.
    '''
    raw = read_file(file_bytes, filename)
    if raw is None or raw.empty:
        message = f'No objective rows found in "{filename}".'
        logger.info(message)
        return ObjectivesResult(
            accepted = pd.DataFrame(),
            issues = [],
            summary = ObjectivesSummary()
        )

    return validate_rows(_normalize(raw), sales, filename)


def validate_rows(
    mapped: pd.DataFrame,
    sales: pd.DataFrame,
    origin: str
) -> ObjectivesResult:
    '''
        Validates a canonical objectives frame against its sales dataset.

        Everything after the reading lives here, so the uploaded file and the
        ERP pushing JSON are judged by one contract and answer with one set of
        codes.

        Args:
            mapped (pd.DataFrame): Canonical objective rows.
            sales (pd.DataFrame): Normalized sales frame naming the clients.
            origin (str): Filename or channel, for the log.

        Returns:
            ObjectivesResult: Accepted objectives, issues and summary.
    '''
    validation = validate(mapped, OBJECTIVES_SCHEMA)
    issues = list(validation.issues)

    # A column the file simply does not have breaks every row at once, so
    # there is nothing to accept partially. Anything else is cell-level: the
    # offending rows are set aside and the rest of the month still loads.
    structural = [issue for issue in issues
                  if issue.rule_code in _STRUCTURAL_RULES]
    if structural:
        accepted = mapped.iloc[0:0]
    else:
        accepted = validation.frame.drop(index = rows_with_issues(issues))
        malformed = _malformed_period_issues(accepted)
        issues.extend(malformed)
        accepted = accepted.drop(index = rows_with_issues(malformed))

    # What the client sent, not what survived: a summary whose total is
    # smaller than their file is a discrepancy nobody can explain later.
    rejected_rows = len(mapped) - len(accepted)

    known_clients = (
        set(sales[_POS].astype(str).unique()) if _POS in sales.columns else set()
    )
    issues.extend(unknown_value_issues(
        accepted, _POS, known_clients, ValidationRule.UNKNOWN_CLIENT
    ))

    summary = _summarize(accepted, known_clients, rejected_rows)
    message = (f'Objectives load from "{origin}": {summary.valid_rows} valid row(s) '
               f'over {summary.periods_count} period(s), {len(issues)} issue(s).')
    logger.info(message)
    return ObjectivesResult(accepted = accepted, issues = issues, summary = summary)


def prepare_rows(rows: pd.DataFrame) -> pd.DataFrame:
    '''
        Brings objective rows to the canonical shape, whatever door they came
        through.

        The API sends a client NAME, like the template does, so the
        identifier is derived here and not left to the caller.

        Args:
            rows (pd.DataFrame): Rows as received.

        Returns:
            pd.DataFrame: Canonical objective rows.
    '''
    return _normalize(rows)


def parse_frame(
    frame: pd.DataFrame,
    sales: pd.DataFrame,
    origin: str
) -> ObjectivesResult:
    '''
        The same pipeline, over the rows FILES handed back instead of bytes.

        Its signature matches the other companions' on purpose: the S3 door
        calls all of them the same way, and a `parse_frame` that took only a
        frame made that door fail on objectives alone.

        Args:
            frame (pd.DataFrame): Rows as FILES returned them.
            sales (pd.DataFrame): Normalized sales frame naming the clients.
            origin (str): Filename or channel, for the log.

        Returns:
            ObjectivesResult: Accepted objectives, issues and summary.
    '''
    return validate_rows(_normalize(frame), sales, origin)
