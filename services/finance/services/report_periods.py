'''
    The periods of the report: the client's amounts split into months and
    years, before anything is calculated. A complement of `report.py`, kept
    apart so that file stays under the size limit.
'''
from dataclasses import dataclass, field

from schemas.entries import EntrySchema, Periodicity
from schemas.finance import AccountType

# Account types that are a picture at a date: everything else moves in a period.
_BALANCE_TYPES = (AccountType.ASSET.value, AccountType.LIABILITY.value, AccountType.EQUITY.value)


@dataclass
class Period:
    '''
        The amounts of one month or one year, split into what moved during
        it and the balances at its end.
    '''
    key: str
    origin: Periodicity
    flows: list[EntrySchema] = field(default_factory = list)
    balances: list[EntrySchema] = field(default_factory = list)
    months: int = 1


def is_balance(entry: EntrySchema) -> bool:
    '''
        Whether an amount is a balance (types 1 to 3): its code says it.

        Args:
            entry (EntrySchema): The amount.

        Returns:
            bool: True for assets, liabilities and equity.
    '''
    return entry.account_code[0] in _BALANCE_TYPES


def split_periods(entries: list[EntrySchema]) -> tuple[dict[str, Period], dict[str, Period]]:
    '''
        The months and the years the client has. A month with days takes the
        sum of its days for what moved and the last loaded day for its
        balances; a year loaded as such is used whole, and any other year is
        built from its months — never split into invented ones.

        Args:
            entries (list[EntrySchema]): Every amount of the client.

        Returns:
            tuple[dict[str, Period], dict[str, Period]]: Months and years.
    '''
    months: dict[str, Period] = {}
    years: dict[str, Period] = {}
    last_day: dict[str, str] = {}
    for entry in entries:
        if entry.periodicity is Periodicity.ANNUAL:
            target = years.setdefault(entry.date, Period(entry.date, Periodicity.ANNUAL,
                                                         months = 12))
        else:
            key = entry.date[:7]
            target = months.setdefault(key, Period(key, entry.periodicity))
        (target.balances if is_balance(entry) else target.flows).append(entry)
        if entry.periodicity is Periodicity.DAILY and is_balance(entry):
            last_day[entry.date[:7]] = max(last_day.get(entry.date[:7], ''), entry.date)
    for key, day in last_day.items():
        months[key].balances = [e for e in months[key].balances if e.date == day]
    for key in sorted(months):
        year = years.get(key[:4])
        if year is not None and year.origin is Periodicity.ANNUAL:
            continue
        if year is None:
            year = years[key[:4]] = Period(key[:4], Periodicity.MONTHLY, months = 0)
        add_month(year, months[key])
    return months, years


def add_month(
    year: Period,
    month: Period
) -> None:
    '''
        Adds a month to the year built from its months: what moved adds up,
        the balances are the latest month's.

        Args:
            year (Period): The year being built.
            month (Period): One of its months, taken in order.
    '''
    year.flows += month.flows
    year.months += 1
    if month.balances:
        year.balances = month.balances
