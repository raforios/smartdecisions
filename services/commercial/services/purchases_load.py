'''
    Purchases ingest — what came into the warehouse and at what cost.

    A ledger and not a snapshot: one row per product bought, with the supplier,
    the day, the quantity and the unit cost put in the warehouse, in the
    currency it was paid in. The analysis brings that cost to bolivianos at the
    rate of the purchase day and sets it against the previous purchases and
    against today, which is what tells whether to adjust the price and the next
    order (plan phase 6).

    It marries the sales dataset by product, like the stock: a product bought
    that the catalogue does not know is reported with a code — it is usually
    the wrong file, not a new product.
'''
from dataclasses import dataclass

import pandas as pd

from schemas.commercial import PurchasesSummary, ValidationIssue
from services.commercial import fill_product_ids, normalize_frame
from services.load_contract import (
    PURCHASE_HEADER_LOOKUP,
    PURCHASES_SCHEMA,
    validate_by_catalogue
)
from services.load_files import read_file
from services.logger_config import custom_logger as logger

_PRODUCT = 'product_id'
_DATE = 'purchase_date'
_SUPPLIER = 'supplier'


@dataclass(frozen = True)
class PurchasesResult:
    '''
        Outcome of ingesting one purchases file.

        A dataclass and not a Pydantic model because it carries a DataFrame,
        which is not serializable.
    '''
    accepted: pd.DataFrame
    issues: list[ValidationIssue]
    summary: PurchasesSummary


def _summarize(
    purchases: pd.DataFrame,
    catalogue: set,
    error_rows: int
) -> PurchasesSummary:
    '''
        Derives the summary of a purchases load.

        Args:
            purchases (pd.DataFrame): Accepted purchase rows.
            catalogue (set): Product ids known by the dataset.
            error_rows (int): How many rows failed the contract.

        Returns:
            PurchasesSummary: Counts and the dates the load covers.
    '''
    if purchases.empty:
        return PurchasesSummary(total_rows = error_rows, error_rows = error_rows)
    dates = purchases[_DATE].dropna()
    return PurchasesSummary(
        total_rows = int(len(purchases)) + error_rows,
        valid_rows = int(len(purchases)),
        error_rows = error_rows,
        products = int(purchases[_PRODUCT].nunique()),
        suppliers = int(purchases[_SUPPLIER].nunique()),
        unknown_products = int((~purchases[_PRODUCT].isin(catalogue)).sum()),
        date_start = dates.min().date().isoformat() if not dates.empty else None,
        date_end = dates.max().date().isoformat() if not dates.empty else None
    )


def validate_rows(
    mapped: pd.DataFrame,
    sales: pd.DataFrame,
    origin: str
) -> PurchasesResult:
    '''
        Validates a canonical purchases frame and marries it to the catalogue.

        One contract for the file and for the ERP pushing JSON: both reach
        this function and answer with the same codes.

        Args:
            mapped (pd.DataFrame): Canonical purchase rows.
            sales (pd.DataFrame): Normalized sales frame holding the catalogue.
            origin (str): Filename or channel, for the log.

        Returns:
            PurchasesResult: Accepted rows, issues and summary.
    '''
    accepted, issues, catalogue, error_rows = validate_by_catalogue(
        mapped, PURCHASES_SCHEMA, sales)
    summary = _summarize(accepted, catalogue, error_rows = error_rows)
    message = (f'Purchases pipeline processed "{origin}": {summary.valid_rows} row(s) of '
               f'{summary.suppliers} supplier(s), {summary.unknown_products} unknown '
               f'product(s), {len(issues)} issue(s).')
    logger.info(message)
    return PurchasesResult(accepted = accepted, issues = issues, summary = summary)


def parse_frame(
    frame: pd.DataFrame,
    sales: pd.DataFrame,
    origin: str
) -> PurchasesResult:
    '''
        The pipeline over the rows FILES handed back, or over a read file:
        map the client's headers, derive the product ids, validate.

        Args:
            frame (pd.DataFrame): Rows with the client's headers.
            sales (pd.DataFrame): Normalized sales frame of the dataset.
            origin (str): Filename or channel, for the log.

        Returns:
            PurchasesResult: Accepted rows, issues and summary.
    '''
    return validate_rows(fill_product_ids(normalize_frame(frame, PURCHASE_HEADER_LOOKUP)),
                         sales, origin)


def parse_and_validate(
    file_bytes: bytes,
    filename: str,
    sales: pd.DataFrame
) -> PurchasesResult:
    '''
        End-to-end purchases pipeline over an uploaded file.

        Args:
            file_bytes (bytes): Raw uploaded file content.
            filename (str): Original filename; drives format detection.
            sales (pd.DataFrame): The normalized sales frame of the dataset.

        Returns:
            PurchasesResult: Accepted rows, issues and summary.

        Raises:
            ValueError: On an unsupported extension or unreadable content.
    '''
    raw = read_file(file_bytes, filename)
    if raw is None or raw.empty:
        message = f'No purchase rows found in "{filename}".'
        logger.info(message)
        return PurchasesResult(accepted = pd.DataFrame(), issues = [],
                               summary = PurchasesSummary())
    return parse_frame(raw, sales, filename)
