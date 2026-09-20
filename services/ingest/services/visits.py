'''
    Visits ingest — what the sales force actually did on the street.

    A visit is the EXECUTED side of a route: which seller stood at which client,
    on which day and —when the client's system knows it— at what hour and with
    what result. The PLANNED side comes from OPTIMIZATION, and putting the two
    together is what turns the route module from a map into a control: who was
    visited, who was skipped, who was visited off-plan, and whether the order
    on the street was the order on paper.

    The sheet is optional like the other companions. Coordinates and the
    outcome are optional inside it: most systems export the visit and not the
    GPS reading, and a comparison of presence alone is still worth having.

    The visit marries the sales dataset by client and by seller. A client or a
    seller the dataset does not know is reported with a code and KEPT: a visit
    to a prospect is a fact, and deciding what it means is not this service's
    call.
'''
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from schemas.ingest import VISITS_SHEET, ValidationIssue, ValidationRule, VisitsSummary
from services.ingest import fill_pos_ids, normalize_frame, sanitize_geo
from services.ingest_contract import (
    VISIT_HEADER_LOOKUP,
    VISITS_SCHEMA,
    unknown_value_issues,
    validate
)
from services.ingest_files import read_sheet
from services.logger_config import custom_logger as logger

_CLIENT = 'pos_id'
_SELLER = 'seller'
_DATE = 'visit_date'
_TIME = 'visit_time'
_OUTCOME = 'outcome'
_LATITUDE = 'latitude'
_LONGITUDE = 'longitude'
# The hour is published as text so the file stays readable in a spreadsheet;
# it is normalized here so OPTIMIZATION never parses it twice.
_TIME_FORMAT = '%H:%M:%S'


@dataclass(frozen = True)
class VisitsResult:
    '''
        Outcome of ingesting one visits load.

        A dataclass and not a Pydantic model because it carries a DataFrame,
        which is not serializable.
    '''
    accepted: pd.DataFrame
    issues: list[ValidationIssue]
    summary: VisitsSummary


def read_visits(
    file_bytes: bytes,
    filename: str,
    auto: bool = False
) -> Optional[pd.DataFrame]:
    '''
        Reads the visit rows out of an upload: the `Visitas` sheet of a
        workbook, or the whole file when it was uploaded as a visits file.

        Args:
            file_bytes (bytes): Raw uploaded file content.
            filename (str): Original filename; drives format detection.
            auto (bool): True when scanning a sales upload for a visits sheet,
                so a file without one comes back empty and silent.

        Returns:
            pd.DataFrame | None: The raw frame, or None when there is nothing
                to read.
    '''
    return read_sheet(file_bytes, filename, VISITS_SHEET, auto = auto)


def _normalize_time(visits: pd.DataFrame) -> pd.DataFrame:
    '''
        Coerces the visit hour to HH:MM:SS text, leaving what cannot be read
        empty rather than inventing a midnight.

        Args:
            visits (pd.DataFrame): Mapped visit rows.

        Returns:
            pd.DataFrame: Same frame with `visit_time` normalized.
    '''
    if _TIME not in visits.columns:
        return visits
    raw = visits[_TIME].astype('string').str.strip()
    parsed = pd.to_datetime(raw, format = 'mixed', errors = 'coerce')
    visits[_TIME] = parsed.dt.strftime(_TIME_FORMAT).where(parsed.notna())
    return visits


def _unknown_count(
    visits: pd.DataFrame,
    column: str,
    known: set
) -> int:
    '''
        How many rows fall outside a catalogue. Without a catalogue nobody is
        unknown: a sales file that names no sellers cannot disown one.

        Args:
            visits (pd.DataFrame): Accepted visit rows.
            column (str): Column to check.
            known (set): Values the dataset knows.

        Returns:
            int: Rows whose value is not in the catalogue.
    '''
    if not known:
        return 0
    return int((~visits[column].astype(str).isin(known)).sum())


def _summarize(
    visits: pd.DataFrame,
    clients: set,
    sellers: set,
    error_rows: int
) -> VisitsSummary:
    '''
        Derives the summary of a visits load.

        Args:
            visits (pd.DataFrame): Accepted visit rows.
            clients (set): Client ids known by the dataset.
            sellers (set): Seller names known by the dataset.
            error_rows (int): How many rows failed the contract.

        Returns:
            VisitsSummary: Counts and the dates the visits cover.
    '''
    if visits.empty:
        return VisitsSummary(total_rows = error_rows, error_rows = error_rows)

    dates = visits[_DATE].dropna()
    has_geo = (
        visits[_LATITUDE].notna() & visits[_LONGITUDE].notna()
        if _LATITUDE in visits.columns and _LONGITUDE in visits.columns
        else pd.Series(False, index = visits.index)
    )
    has_outcome = (
        visits[_OUTCOME].notna() if _OUTCOME in visits.columns
        else pd.Series(False, index = visits.index)
    )

    return VisitsSummary(
        total_rows = int(len(visits)) + error_rows,
        valid_rows = int(len(visits)),
        error_rows = error_rows,
        sellers = int(visits[_SELLER].nunique()),
        clients = int(visits[_CLIENT].nunique()),
        unknown_clients = _unknown_count(visits, _CLIENT, clients),
        unknown_sellers = _unknown_count(visits, _SELLER, sellers),
        with_coordinates = int(has_geo.sum()),
        with_outcome = int(has_outcome.sum()),
        visit_date_start = dates.min().date().isoformat() if not dates.empty else None,
        visit_date_end = dates.max().date().isoformat() if not dates.empty else None
    )


def _known_values(
    sales: pd.DataFrame,
    column: str
) -> set:
    '''
        The distinct values of one sales column, as text.

        Blanks do not count: a sales file whose seller column is empty knows
        no sellers, and must not turn every visit into an unknown one.

        Args:
            sales (pd.DataFrame): Normalized sales frame.
            column (str): Column to read.

        Returns:
            set: Distinct non-blank values, empty when the column is absent.
    '''
    if column not in sales.columns:
        return set()
    values = sales[column].dropna().astype(str).str.strip()
    return set(values[values != ''])


def parse_and_validate(
    file_bytes: bytes,
    filename: str,
    sales: pd.DataFrame,
    auto: bool = False
) -> VisitsResult:
    '''
        End-to-end visits pipeline: read, validate, marry, summarize.

        Args:
            file_bytes (bytes): Raw uploaded file content.
            filename (str): Original filename; drives format detection.
            sales (pd.DataFrame): The normalized sales frame of the dataset the
                visits belong to, which holds the client and seller catalogues.
            auto (bool): True when scanning a sales upload for a visits sheet.

        Returns:
            VisitsResult: Accepted rows, issues and summary.

        Raises:
            ValueError: On an unsupported extension or unreadable content.
    '''
    raw = read_visits(file_bytes, filename, auto = auto)
    if raw is None or raw.empty:
        message = f'No visit rows found in "{filename}".'
        logger.info(message)
        return VisitsResult(
            accepted = pd.DataFrame(), issues = [], summary = VisitsSummary()
        )

    mapped = _normalize_time(
        sanitize_geo(fill_pos_ids(normalize_frame(raw, VISIT_HEADER_LOOKUP)))
    )
    validation = validate(mapped, VISITS_SCHEMA)
    issues = list(validation.issues)
    accepted = validation.frame if validation.is_valid else mapped.iloc[0:0]

    clients = _known_values(sales, _CLIENT)
    sellers = _known_values(sales, _SELLER)
    if not accepted.empty:
        if clients:
            issues.extend(unknown_value_issues(accepted, _CLIENT, clients,
                                          ValidationRule.UNKNOWN_CLIENT))
        if sellers:
            issues.extend(unknown_value_issues(accepted, _SELLER, sellers,
                                          ValidationRule.UNKNOWN_SELLER))

    summary = _summarize(accepted, clients, sellers, error_rows = len(validation.issues))
    message = (f'Visits pipeline processed "{filename}": {summary.valid_rows} row(s) by '
               f'{summary.sellers} seller(s) over {summary.clients} client(s), '
               f'{summary.unknown_clients} unknown client(s), {len(issues)} issue(s).')
    logger.info(message)

    return VisitsResult(accepted = accepted, issues = issues, summary = summary)
