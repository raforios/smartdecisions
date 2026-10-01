'''
    Stock ingest — the daily snapshot of what is in the warehouse.

    A snapshot and not a movement ledger: one row per product and day with what
    was there. That is the line this product does not cross. Reading the stock
    and reporting coverage, stockout risk and immobilized capital is analysis;
    holding reservations and deciding what is available to promise is a
    transactional system, and it would make SmartDecisions the owner of a truth
    that lives in the client's ERP.

    `Comprometido` is what the ERP already has committed in orders: it is READ,
    never written. `available = on_hand - committed` is therefore a report of a
    decision somebody else took, not a decision taken here.

    The snapshot marries the sales dataset by product, so the analysis can put
    what is in stock next to what is being sold. A product in the warehouse that
    the catalogue does not know is reported with a code — it is usually the
    wrong file, not a new product.
'''
from dataclasses import dataclass

import pandas as pd

from schemas.ingest import StockDayItem, StockSummary, ValidationIssue, ValidationRule
from services.ingest import fill_product_ids, normalize_frame
from services.ingest_contract import (
    STOCK_HEADER_LOOKUP,
    STOCK_SCHEMA,
    unknown_value_issues,
    validate
)
from services.ingest_files import read_file
from services.ingest_contract import AMOUNT_DECIMALS
from services.logger_config import custom_logger as logger

_PRODUCT = 'product_id'
_ON_HAND = 'on_hand'
_SNAPSHOT_DATE = 'snapshot_date'
_COMMITTED = 'committed'
_PRODUCT_NAME = 'product_name'


@dataclass(frozen = True)
class StockResult:
    '''
        Outcome of ingesting one stock snapshot.

        A dataclass and not a Pydantic model because it carries a DataFrame,
        which is not serializable.
    '''
    accepted: pd.DataFrame
    issues: list[ValidationIssue]
    summary: StockSummary




def _summarize(
    stock: pd.DataFrame,
    catalogue: set,
    error_rows: int
) -> StockSummary:
    '''
        Derives the summary of a snapshot load.

        Args:
            stock (pd.DataFrame): Accepted snapshot rows.
            catalogue (set): Product ids known by the dataset.
            error_rows (int): How many rows failed the contract.

        Returns:
            StockSummary: Counts, units and the dates the snapshot covers.
    '''
    if stock.empty:
        return StockSummary(total_rows = error_rows, error_rows = error_rows)

    dates = stock[_SNAPSHOT_DATE].dropna()
    unknown = int((~stock[_PRODUCT].isin(catalogue)).sum())

    return StockSummary(
        total_rows = int(len(stock)) + error_rows,
        valid_rows = int(len(stock)),
        error_rows = error_rows,
        products = int(stock[_PRODUCT].nunique()),
        unknown_products = unknown,
        units_on_hand = round(float(stock[_ON_HAND].sum()), AMOUNT_DECIMALS),
        snapshot_start = dates.min().date().isoformat() if not dates.empty else None,
        snapshot_end = dates.max().date().isoformat() if not dates.empty else None
    )


def parse_and_validate(
    file_bytes: bytes,
    filename: str,
    sales: pd.DataFrame
) -> StockResult:
    '''
        End-to-end stock pipeline: read, validate, marry, summarize.

        Args:
            file_bytes (bytes): Raw uploaded file content.
            filename (str): Original filename; drives format detection.
            sales (pd.DataFrame): The normalized sales frame of the dataset the
                snapshot belongs to, which holds the product catalogue.

        Returns:
            StockResult: Accepted rows, issues and summary.

        Raises:
            ValueError: On an unsupported extension or unreadable content.
    '''
    raw = read_file(file_bytes, filename)
    if raw is None or raw.empty:
        message = f'No stock rows found in "{filename}".'
        logger.info(message)
        return StockResult(
            accepted = pd.DataFrame(), issues = [], summary = StockSummary()
        )

    return validate_rows(prepare_rows(normalize_frame(raw, STOCK_HEADER_LOOKUP)),
                         sales, filename)


def prepare_rows(frame: pd.DataFrame) -> pd.DataFrame:
    '''
        The identifiers this service derives on its own, over a frame whose
        columns are already canonical.

        Split out so the API path —which receives canonical names from its
        DTOs and needs no header mapping— reaches the validator through
        exactly the same steps as the file.

        Args:
            frame (pd.DataFrame): Canonical stock rows.

        Returns:
            pd.DataFrame: The same rows with the product ids filled in.
    '''
    return fill_product_ids(frame)


def validate_rows(
    mapped: pd.DataFrame,
    sales: pd.DataFrame,
    origin: str
) -> StockResult:
    '''
        Validates a canonical stock frame and marries it to the catalogue.

        Everything after the reading lives here, so the uploaded file and the
        ERP pushing JSON are judged by one contract and answer with one set of
        codes. A second copy of this for the API would drift on the first
        change.

        Args:
            mapped (pd.DataFrame): Canonical stock rows.
            sales (pd.DataFrame): Normalized sales frame holding the catalogue.
            origin (str): Filename or channel, for the log.

        Returns:
            StockResult: Accepted rows, issues and summary.
    '''
    filename = origin
    validation = validate(mapped, STOCK_SCHEMA)
    issues = list(validation.issues)
    accepted = validation.frame if validation.is_valid else mapped.iloc[0:0]

    catalogue = set(
        sales[_PRODUCT].dropna().astype(str)
    ) if _PRODUCT in sales.columns else set()

    if not accepted.empty and catalogue:
        issues.extend(unknown_value_issues(accepted, _PRODUCT, catalogue,
                                           ValidationRule.UNKNOWN_PRODUCT))

    summary = _summarize(accepted, catalogue, error_rows = len(validation.issues))
    message = (f'Stock pipeline processed "{filename}": {summary.valid_rows} row(s) over '
               f'{summary.products} product(s), {summary.unknown_products} unknown, '
               f'{len(issues)} issue(s).')
    logger.info(message)

    return StockResult(accepted = accepted, issues = issues, summary = summary)


def parse_frame(
    frame: pd.DataFrame,
    sales: pd.DataFrame,
    origin: str
) -> StockResult:
    '''
        The same pipeline, over the rows FILES handed back instead of bytes.

        FILES owns the bucket and its reader answers with one flat table, so a
        stored object arrives already parsed. What is left —mapping the client's
        headers to the contract, deriving the identifiers and validating— is
        exactly what the uploaded file goes through.

        Args:
            frame (pd.DataFrame): Rows as stored, with the client's headers.
            sales (pd.DataFrame): Normalized sales frame of the dataset.
            origin (str): Filename or channel, for the log.

        Returns:
            StockResult: Accepted rows, issues and summary.
    '''
    return validate_rows(prepare_rows(normalize_frame(frame, STOCK_HEADER_LOOKUP)), sales, origin)


def stock_of_day(
    stored: pd.DataFrame,
    day: str
) -> list[StockDayItem]:
    '''
        The products of the stored snapshot on one day, with what is free to sell.

        The stored file comes back through FILES as text, so dates and numbers
        are parsed here before filtering. A product with several rows that day
        —one per warehouse— is summed: the route sells from the company's
        stock, not from one shelf.

        Args:
            stored (pd.DataFrame): Every snapshot row the dataset holds.
            day (str): The day asked for, YYYY-MM-DD.

        Returns:
            list[StockDayItem]: One item per product, empty when that day was
                never loaded.
    '''
    if stored.empty or _SNAPSHOT_DATE not in stored.columns:
        return []

    columns = [_SNAPSHOT_DATE, _PRODUCT, _PRODUCT_NAME, _ON_HAND, _COMMITTED]
    frame = stored.reindex(columns = columns)
    frame = frame[pd.to_datetime(frame[_SNAPSHOT_DATE], errors = 'coerce')
                  .dt.strftime('%Y-%m-%d') == day]
    if frame.empty:
        return []

    grouped = frame.assign(
        on_hand = pd.to_numeric(frame[_ON_HAND], errors = 'coerce').fillna(0.0),
        committed = pd.to_numeric(frame[_COMMITTED], errors = 'coerce').fillna(0.0)
    ).groupby(_PRODUCT, sort = True).agg(
        product_name = (_PRODUCT_NAME, 'first'),
        on_hand = (_ON_HAND, 'sum'),
        committed = (_COMMITTED, 'sum')
    )
    return [
        StockDayItem(
            product_id = str(product_id),
            product_name = None if pd.isna(row.product_name) else str(row.product_name),
            on_hand = round(float(row.on_hand), AMOUNT_DECIMALS),
            committed = round(float(row.committed), AMOUNT_DECIMALS),
            available = round(max(float(row.on_hand) - float(row.committed), 0.0),
                              AMOUNT_DECIMALS)
        )
        for product_id, row in grouped.iterrows()
    ]
