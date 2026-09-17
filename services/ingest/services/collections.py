'''
    Collections ingest — the payments contract that marries an existing sales
    dataset.

    It is a separate contract and not more columns of the sales file because of
    when each thing is known: the sale carries its terms the day it is issued,
    while an invoice at 90 days is collected three months after the file that
    registered it, and in instalments. Forcing both into one sheet would mean
    re-uploading the whole sales history every time somebody pays.

    The marriage is by `order_id`, which the sales contract already requires.
    In the sales sheet an invoice spans several rows — one per product line — so
    the receivable is built at invoice level: the sum of `total_amount` per
    `order_id`. Payments are imputed against that total.

    Two rules that are the point of this module:
        * An invoice with no payment rows is an OPEN BALANCE, not an error.
          That is what lets a client load sales today and payments tomorrow.
        * A payment whose invoice is not in the dataset is reported as an
          issue with a code — never dropped in silence.
'''
from dataclasses import dataclass
from typing import Final, Optional

import pandas as pd

from schemas.ingest import (
    COLLECTIONS_SHEET,
    CollectionsSummary,
    ValidationIssue,
    ValidationRule
)
from services.ingest import (
    COLLECTION_HEADER_LOOKUP,
    COLLECTIONS_SCHEMA,
    normalize_frame,
    read_file,
    read_workbook,
    validate
)
from services.logger_config import custom_logger as logger

_ORDER = 'order_id'
_PAID = 'paid_amount'
_PAYMENT_DATE = 'payment_date'
_AMOUNT = 'total_amount'

# Tolerance when comparing what was collected against what was billed. A
# payment can arrive a cent off because of the ERP's rounding, and treating that
# as an overpayment would be inventing an issue.
_OVERPAYMENT_TOLERANCE: Final[float] = 0.01


@dataclass(frozen = True)
class CollectionsResult:
    '''
        Outcome of ingesting one collections file.

        A dataclass and not a Pydantic model because it carries a DataFrame,
        which is not serializable.
    '''
    accepted: pd.DataFrame
    issues: list[ValidationIssue]
    summary: CollectionsSummary


def _collections_sheet(file_bytes: bytes) -> Optional[pd.DataFrame]:
    '''
        Returns the collections sheet of a workbook, if it has one.

        Args:
            file_bytes (bytes): Raw .xlsx content.

        Returns:
            pd.DataFrame | None: The sheet, or None when the workbook does not
                carry one.
    '''
    for name, frame in read_workbook(file_bytes).items():
        if str(name).strip().lower() == COLLECTIONS_SHEET.lower():
            return frame
    return None


def read_collections(file_bytes: bytes, filename: str,
                     auto: bool = False) -> Optional[pd.DataFrame]:
    '''
        Reads the payments rows out of an upload.

        `auto` is the difference between "this file IS a collections file" and
        "look inside this sales workbook in case it also brings payments". It
        matters: read in auto mode, a sales CSV would be parsed as payments and
        reported as a broken collections contract, when the client simply sells
        cash.

        Args:
            file_bytes (bytes): Raw uploaded file content.
            filename (str): Original filename; drives format detection.
            auto (bool): True when scanning a sales upload for a payments
                sheet; False when the caller uploaded a payments file.

        Returns:
            pd.DataFrame | None: The raw frame, or None when there is nothing
                to read.

        Raises:
            ValueError: On an unsupported extension or unreadable content.
    '''
    if filename.lower().endswith('.xlsx'):
        sheet = _collections_sheet(file_bytes)
        if sheet is not None:
            return sheet
        # A file uploaded AS a collections file may name its sheet something
        # else; one being scanned in passing may not.
        return None if auto else read_file(file_bytes, filename)
    return None if auto else read_file(file_bytes, filename)


def _normalize(dataframe: pd.DataFrame) -> pd.DataFrame:
    '''
        Brings a raw collections frame to the canonical contract.

        Args:
            dataframe (pd.DataFrame): Raw frame as read from the file.

        Returns:
            pd.DataFrame: Mapped frame with clean ids, dates and options.
    '''
    return normalize_frame(dataframe, COLLECTION_HEADER_LOOKUP)


def _unmatched_issues(payments: pd.DataFrame,
                      invoices: pd.Series) -> list[ValidationIssue]:
    '''
        Flags payments whose invoice is not in the sales dataset.

        Args:
            payments (pd.DataFrame): Validated payment rows.
            invoices (pd.Series): Invoiced amount per `order_id`.

        Returns:
            list[ValidationIssue]: One issue per orphan payment row.
    '''
    orphans = payments.loc[~payments[_ORDER].isin(invoices.index)]
    return [
        ValidationIssue(
            row = int(position) + 2,
            column = _ORDER,
            value = str(row[_ORDER]),
            rule_code = ValidationRule.UNKNOWN_INVOICE
        )
        for position, row in orphans.iterrows()
    ]


def _overpaid_issues(payments: pd.DataFrame,
                     invoices: pd.Series) -> list[ValidationIssue]:
    '''
        Flags invoices collected for more than they were issued for.

        It is reported and kept, not corrected: the excess is a fact of the
        client's data — a duplicated payment, a credit note recorded as a
        collection — and deciding what it means is not this service's call.

        Args:
            payments (pd.DataFrame): Validated payment rows.
            invoices (pd.Series): Invoiced amount per `order_id`.

        Returns:
            list[ValidationIssue]: One issue per over-collected invoice.
    '''
    matched = payments.loc[payments[_ORDER].isin(invoices.index)]
    collected = matched.groupby(_ORDER)[_PAID].sum()
    excess = collected - invoices.reindex(collected.index)
    over = excess.loc[excess > _OVERPAYMENT_TOLERANCE]
    return [
        ValidationIssue(
            row = 0, column = _PAID, value = f'{float(amount):.2f}',
            rule_code = ValidationRule.OVERPAID_INVOICE
        )
        for _, amount in over.items()
    ]


def _summarize(payments: pd.DataFrame, invoices: pd.Series,
               error_rows: int) -> CollectionsSummary:
    '''
        Derives the summary of a collections load.

        Args:
            payments (pd.DataFrame): Accepted payment rows.
            invoices (pd.Series): Invoiced amount per `order_id`.
            error_rows (int): How many rows were reported as issues.

        Returns:
            CollectionsSummary: Counts, amounts and the covered date range.
    '''
    matched = payments.loc[payments[_ORDER].isin(invoices.index)]
    dates = payments[_PAYMENT_DATE].dropna() if _PAYMENT_DATE in payments else pd.Series(
        dtype = 'datetime64[ns]'
    )

    return CollectionsSummary(
        total_rows = int(len(payments)) + error_rows,
        valid_rows = int(len(payments)),
        error_rows = error_rows,
        matched_invoices = int(matched[_ORDER].nunique()) if not matched.empty else 0,
        unmatched_rows = int(len(payments) - len(matched)),
        collected_amount = round(float(matched[_PAID].sum()), 2) if not matched.empty else 0.0,
        payment_date_start = dates.min().date().isoformat() if not dates.empty else None,
        payment_date_end = dates.max().date().isoformat() if not dates.empty else None
    )


def parse_and_validate(file_bytes: bytes, filename: str, sales: pd.DataFrame,
                       auto: bool = False) -> CollectionsResult:
    '''
        End-to-end collections pipeline: read, validate, marry, summarize.

        Rows that fail the contract are set aside with their code and the rest
        is kept — same partial acceptance as the sales pipeline, for the same
        reason: one badly typed date must not cost the client the whole load.

        Args:
            file_bytes (bytes): Raw uploaded file content.
            filename (str): Original filename; drives format detection.
            sales (pd.DataFrame): The normalized sales frame of the dataset the
                payments belong to.
            auto (bool): True when scanning a sales upload for a payments
                sheet, so a file without one comes back empty and silent.

        Returns:
            CollectionsResult: Accepted payments, issues and summary.

        Raises:
            ValueError: On an unsupported extension or unreadable content.
    '''
    raw = read_collections(file_bytes, filename, auto = auto)
    if raw is None or raw.empty:
        message = f'No collections rows found in "{filename}".'
        logger.info(message)
        return CollectionsResult(
            accepted = pd.DataFrame(),
            issues = [],
            summary = CollectionsSummary()
        )

    mapped = _normalize(raw)
    validation = validate(mapped, COLLECTIONS_SCHEMA)
    issues = list(validation.issues)

    # With the contract broken there is nothing to marry: no row is valid, and
    # the caller decides whether to reject the file or just report it.
    accepted = validation.frame if validation.is_valid else mapped.iloc[0:0]

    invoices = (
        sales.groupby(_ORDER)[_AMOUNT].sum()
        if _ORDER in sales.columns and _AMOUNT in sales.columns
        else pd.Series(dtype = 'float64')
    )

    if not accepted.empty:
        issues.extend(_unmatched_issues(accepted, invoices))
        issues.extend(_overpaid_issues(accepted, invoices))

    summary = _summarize(accepted, invoices, error_rows = len(validation.issues))
    message = (
        f'Collections pipeline processed "{filename}": {summary.valid_rows} payment(s) '
        f'over {summary.matched_invoices} invoice(s), {summary.unmatched_rows} unmatched, '
        f'{len(issues)} issue(s).'
    )
    logger.info(message)

    return CollectionsResult(accepted = accepted, issues = issues, summary = summary)
