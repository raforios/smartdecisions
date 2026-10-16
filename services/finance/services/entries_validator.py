'''
    The one validator of what a client loads, for the file and for the API.

    Each row gets the first rule it breaks as a code and is set aside; the rest
    goes in. Nothing here is inferred: a missing date, a missing invoice flag
    or a negative amount is refused, never filled in (Rafael: «no podemos
    inferir»).

    The checks that need stored data —a period already loaded with another
    periodicity— receive it as a function, so the rules stay pure and are
    tested without a database.
'''
import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from schemas.entries import (
    PERIODICITY_LABELS,
    YES_NO_LABELS,
    EntryRowSchema,
    LoadError,
    Periodicity,
    RejectedRowSchema
)
from schemas.finance import AccountType

# The date each periodicity carries, as the contract writes it.
_DATE_PATTERNS: dict[Periodicity, re.Pattern] = {
    Periodicity.DAILY: re.compile(r'^\d{4}-\d{2}-\d{2}$'),
    Periodicity.MONTHLY: re.compile(r'^\d{4}-\d{2}$'),
    Periodicity.ANNUAL: re.compile(r'^\d{4}$'),
}


@dataclass(frozen = True)
class ValidEntry:
    '''
        A row that passed every rule, normalized.
    '''
    periodicity: Periodicity
    date: str
    account_code: str
    amount: float
    invoiced: bool | None
    taxes_included: bool | None
    note: str | None

    @property
    def key(self) -> str:
        '''
            The sort key it is stored under: "<periodicity>#<date>#<account>".

            Returns:
                str: The key.
        '''
        return entry_key(self.periodicity, self.date, self.account_code)


class RowRejected(Exception):
    '''
        A row broke a rule. Carries the code and the value that broke it.
    '''
    def __init__(
        self,
        code: LoadError,
        value: object = None
    ) -> None:
        super().__init__(code.value)
        self.code = code
        self.value = None if value is None else str(value)


def entry_key(
    periodicity: Periodicity,
    day: str,
    account_code: str
) -> str:
    '''
        The sort key of an amount.

        Args:
            periodicity (Periodicity): How often it was taken.
            day (str): Its date, as the periodicity writes it.
            account_code (str): The account.

        Returns:
            str: "<periodicity>#<date>#<account_code>".
    '''
    return f'{periodicity.value}#{day}#{account_code}'


def conflicting_prefixes(
    periodicity: Periodicity,
    day: str
) -> list[str]:
    '''
        The key prefixes that, if loaded, would mix two periodicities in one
        period: a month with days refuses a monthly row, and a year loaded as
        such refuses its months and days.

        Args:
            periodicity (Periodicity): The periodicity of the row.
            day (str): Its date.

        Returns:
            list[str]: The prefixes that must hold nothing.
    '''
    year, month = day[:4], day[:7]
    if periodicity is Periodicity.DAILY:
        return [f'{Periodicity.MONTHLY.value}#{month}#', f'{Periodicity.ANNUAL.value}#{year}#']
    if periodicity is Periodicity.MONTHLY:
        return [f'{Periodicity.DAILY.value}#{month}-', f'{Periodicity.ANNUAL.value}#{year}#']
    return [f'{Periodicity.MONTHLY.value}#{year}-', f'{Periodicity.DAILY.value}#{year}-']


def _blank(value: object) -> bool:
    '''
        Whether a cell is empty. A spreadsheet reader gives NaN for an empty
        number cell, so NaN counts as empty too.

        Args:
            value (object): The raw value.

        Returns:
            bool: True when there is nothing in it.
    '''
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return isinstance(value, str) and not value.strip()


def _text(value: object) -> str:
    '''
        A cell as text. A year typed in a number cell arrives as 2026.0.

        Args:
            value (object): The raw value.

        Returns:
            str: The text, trimmed.
    '''
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def parse_periodicity(value: object) -> Periodicity:
    '''
        The periodicity, from the API value or the word in the template.

        Args:
            value (object): DAILY/MONTHLY/ANNUAL or Diaria/Mensual/Anual.

        Returns:
            Periodicity: The periodicity.

        Raises:
            RowRejected: INVALID_PERIODICITY.
    '''
    if _blank(value):
        raise RowRejected(LoadError.INVALID_PERIODICITY)
    text = _text(value).upper()
    if text in Periodicity.__members__:
        return Periodicity[text]
    if text in PERIODICITY_LABELS:
        return PERIODICITY_LABELS[text]
    raise RowRejected(LoadError.INVALID_PERIODICITY, value)


def period_start(
    periodicity: Periodicity,
    day: str
) -> date:
    '''
        The first day of a period.

        Args:
            periodicity (Periodicity): How the period is written.
            day (str): Its date, already matched to the periodicity.

        Returns:
            date: The first day.

        Raises:
            ValueError: The digits do not make a date (month 13, day 31 of June).
    '''
    if periodicity is Periodicity.DAILY:
        return date.fromisoformat(day)
    if periodicity is Periodicity.MONTHLY:
        return date.fromisoformat(f'{day}-01')
    return date(int(day), 1, 1)


def parse_date(
    value: object,
    periodicity: Periodicity,
    today: date
) -> str:
    '''
        The date of a row, checked against its periodicity and against today.

        Args:
            value (object): The raw date.
            periodicity (Periodicity): The periodicity of the row.
            today (date): Today, in the client's timezone.

        Returns:
            str: The date as the periodicity writes it.

        Raises:
            RowRejected: MISSING_DATE, DATE_PERIODICITY_MISMATCH or FUTURE_PERIOD.
    '''
    if _blank(value):
        raise RowRejected(LoadError.MISSING_DATE)
    text = _text(value)
    # A day cell read from a spreadsheet keeps its midnight: «2026-03-05 00:00:00».
    if periodicity is Periodicity.DAILY and len(text) > 10 and text[10] in ' T':
        text = text[:10]
    if not _DATE_PATTERNS[periodicity].match(text):
        raise RowRejected(LoadError.DATE_PERIODICITY_MISMATCH, value)
    try:
        start = period_start(periodicity, text)
    except ValueError as error:
        raise RowRejected(LoadError.DATE_PERIODICITY_MISMATCH, value) from error
    if start > today:
        raise RowRejected(LoadError.FUTURE_PERIOD, value)
    return text


def parse_amount(value: object) -> float:
    '''
        The amount, in bolivianos. Never negative: the accounts that subtract
        carry their own mark (Rafael, 16-oct).

        Args:
            value (object): The raw amount.

        Returns:
            float: The amount.

        Raises:
            RowRejected: INVALID_AMOUNT or NEGATIVE_AMOUNT.
    '''
    if _blank(value) or isinstance(value, bool):
        raise RowRejected(LoadError.INVALID_AMOUNT, value)
    try:
        amount = float(value)
    except (TypeError, ValueError) as error:
        raise RowRejected(LoadError.INVALID_AMOUNT, value) from error
    if math.isnan(amount) or math.isinf(amount):
        raise RowRejected(LoadError.INVALID_AMOUNT, value)
    if amount < 0:
        raise RowRejected(LoadError.NEGATIVE_AMOUNT, value)
    return amount


def parse_flag(value: object) -> bool:
    '''
        A Yes/No cell of an income row. Mandatory: an empty one is refused,
        never assumed.

        Args:
            value (object): True/False, or Sí/No as the template writes it.

        Returns:
            bool: The flag.

        Raises:
            RowRejected: MISSING_INVOICE_FLAGS.
    '''
    if isinstance(value, bool):
        return value
    if _blank(value) or _text(value).upper() not in YES_NO_LABELS:
        raise RowRejected(LoadError.MISSING_INVOICE_FLAGS, value)
    return YES_NO_LABELS[_text(value).upper()]


def validate_row(
    row: EntryRowSchema,
    catalog: dict[str, dict],
    today: date
) -> ValidEntry:
    '''
        Every rule a single row must keep on its own.

        Args:
            row (EntryRowSchema): The row as it arrived.
            catalog (dict[str, dict]): The accounts, by code.
            today (date): Today, in the client's timezone.

        Returns:
            ValidEntry: The row, normalized.

        Raises:
            RowRejected: The first rule it breaks.
    '''
    code = '' if _blank(row.account_code) else _text(row.account_code)
    account = catalog.get(code)
    if account is None:
        raise RowRejected(LoadError.UNKNOWN_ACCOUNT, row.account_code)
    if not account.get('group_code'):
        raise RowRejected(LoadError.ACCOUNT_IS_GROUP, code)
    periodicity = parse_periodicity(row.periodicity)
    day = parse_date(row.date, periodicity, today)
    amount = parse_amount(row.amount)
    invoiced = taxes_included = None
    # The invoice flags only mean something on income; elsewhere they are ignored.
    if account['account_type'] == AccountType.INCOME.value:
        invoiced = parse_flag(row.invoiced)
        taxes_included = parse_flag(row.taxes_included)
    note = None if _blank(row.note) else _text(row.note)
    return ValidEntry(periodicity = periodicity, date = day, account_code = code,
                      amount = amount, invoiced = invoiced,
                      taxes_included = taxes_included, note = note)


def validate_rows(
    rows: list[EntryRowSchema],
    catalog: dict[str, dict],
    today: date,
    stored_has: Callable[[str], bool],
    first_row: int
) -> tuple[list[ValidEntry], list[RejectedRowSchema]]:
    '''
        A whole load: the rules of each row, then the ones between rows and
        against what is already stored.

        Args:
            rows (list[EntryRowSchema]): The rows as they arrived.
            catalog (dict[str, dict]): The accounts, by code.
            today (date): Today, in the client's timezone.
            stored_has (Callable[[str], bool]): Whether the client already has
                anything under a key prefix.
            first_row (int): The number the first row is reported with: 1 for
                the API, 2 for a file, whose row 1 is the header.

        Returns:
            tuple[list[ValidEntry], list[RejectedRowSchema]]: What goes in and
                what is set aside.
    '''
    valid: list[ValidEntry] = []
    rejected: list[RejectedRowSchema] = []
    seen: set[str] = set()
    for number, row in enumerate(rows, start = first_row):
        try:
            entry = validate_row(row, catalog, today)
            if entry.key in seen:
                raise RowRejected(LoadError.DUPLICATE_ROW, entry.key)
            prefixes = conflicting_prefixes(entry.periodicity, entry.date)
            if any(stored_has(prefix) or any(key.startswith(prefix) for key in seen)
                   for prefix in prefixes):
                raise RowRejected(LoadError.PERIODICITY_CONFLICT, entry.date)
        except RowRejected as refusal:
            rejected.append(RejectedRowSchema(row = number, code = refusal.code,
                                              value = refusal.value))
            continue
        seen.add(entry.key)
        valid.append(entry)
    return valid, rejected
