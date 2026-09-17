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
from typing import Optional

import pandas as pd

from schemas.ingest import STOCK_SHEET, StockSummary, ValidationIssue, ValidationRule
from services.ingest import (
    STOCK_HEADER_LOOKUP,
    STOCK_SCHEMA,
    fill_product_ids,
    normalize_frame,
    read_file,
    read_workbook,
    validate
)
from services.logger_config import custom_logger as logger

_PRODUCT = 'product_id'
_ON_HAND = 'on_hand'
_SNAPSHOT_DATE = 'snapshot_date'


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


def read_stock(file_bytes: bytes, filename: str,
               auto: bool = False) -> Optional[pd.DataFrame]:
    '''
        Reads the stock rows out of an upload.

        Args:
            file_bytes (bytes): Raw uploaded file content.
            filename (str): Original filename; drives format detection.
            auto (bool): True when scanning a sales upload for a stock sheet,
                so a file without one comes back empty and silent.

        Returns:
            pd.DataFrame | None: The raw frame, or None when there is nothing
                to read.

        Raises:
            ValueError: On an unsupported extension or unreadable content.
    '''
    if filename.lower().endswith('.xlsx'):
        for name, frame in read_workbook(file_bytes).items():
            if str(name).strip().lower() == STOCK_SHEET.lower():
                return frame
        return None if auto else read_file(file_bytes, filename)
    return None if auto else read_file(file_bytes, filename)


def _unknown_issues(stock: pd.DataFrame, catalogue: set) -> list[ValidationIssue]:
    '''
        Flags snapshot rows whose product is not in the sales catalogue.

        Args:
            stock (pd.DataFrame): Validated snapshot rows.
            catalogue (set): Product ids known by the dataset.

        Returns:
            list[ValidationIssue]: One issue per unknown product row.
    '''
    unknown = stock.loc[~stock[_PRODUCT].isin(catalogue)]
    return [
        ValidationIssue(
            row = int(position) + 2,
            column = _PRODUCT,
            value = str(row[_PRODUCT]),
            rule_code = ValidationRule.UNKNOWN_PRODUCT
        )
        for position, row in unknown.iterrows()
    ]


def _summarize(stock: pd.DataFrame, catalogue: set, error_rows: int) -> StockSummary:
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
        units_on_hand = round(float(stock[_ON_HAND].sum()), 2),
        snapshot_start = dates.min().date().isoformat() if not dates.empty else None,
        snapshot_end = dates.max().date().isoformat() if not dates.empty else None
    )


def parse_and_validate(file_bytes: bytes, filename: str, sales: pd.DataFrame,
                       auto: bool = False) -> StockResult:
    '''
        End-to-end stock pipeline: read, validate, marry, summarize.

        Args:
            file_bytes (bytes): Raw uploaded file content.
            filename (str): Original filename; drives format detection.
            sales (pd.DataFrame): The normalized sales frame of the dataset the
                snapshot belongs to, which holds the product catalogue.
            auto (bool): True when scanning a sales upload for a stock sheet.

        Returns:
            StockResult: Accepted rows, issues and summary.

        Raises:
            ValueError: On an unsupported extension or unreadable content.
    '''
    raw = read_stock(file_bytes, filename, auto = auto)
    if raw is None or raw.empty:
        message = f'No stock rows found in "{filename}".'
        logger.info(message)
        return StockResult(
            accepted = pd.DataFrame(), issues = [], summary = StockSummary()
        )

    mapped = fill_product_ids(normalize_frame(raw, STOCK_HEADER_LOOKUP))
    validation = validate(mapped, STOCK_SCHEMA)
    issues = list(validation.issues)
    accepted = validation.frame if validation.is_valid else mapped.iloc[0:0]

    catalogue = set(
        sales[_PRODUCT].dropna().astype(str)
    ) if _PRODUCT in sales.columns else set()

    if not accepted.empty and catalogue:
        issues.extend(_unknown_issues(accepted, catalogue))

    summary = _summarize(accepted, catalogue, error_rows = len(validation.issues))
    message = (f'Stock pipeline processed "{filename}": {summary.valid_rows} row(s) over '
               f'{summary.products} product(s), {summary.unknown_products} unknown, '
               f'{len(issues)} issue(s).')
    logger.info(message)

    return StockResult(accepted = accepted, issues = issues, summary = summary)
