'''
    Tests for the one validator of the loads.

    What they defend: nothing is inferred. A missing date, a missing invoice
    flag or a negative amount is refused with its code, never filled in, and
    one period never mixes two periodicities.
'''
from datetime import date

import pytest

from schemas.entries import EntryRowSchema, LoadError, Periodicity
from services.entries_validator import (
    RowRejected,
    conflicting_prefixes,
    validate_row,
    validate_rows
)

TODAY = date(2026, 10, 16)
CATALOG = {
    '4.1': {'account_code': '4.1', 'account_type': '4', 'group_code': None},
    '4.1.01': {'account_code': '4.1.01', 'account_type': '4', 'group_code': '4.1'},
    '6.1.03': {'account_code': '6.1.03', 'account_type': '6', 'group_code': '6.1'},
}
RENT = {'date': '2026-03', 'periodicity': 'Mensual', 'account_code': '6.1.03', 'amount': 3500}
SALES = {'date': '2026-03', 'periodicity': 'MONTHLY', 'account_code': '4.1.01',
         'amount': 98000.5, 'invoiced': 'Sí', 'taxes_included': 'No'}


def _code(**fields) -> LoadError:
    '''
        The code a single row is refused with.

        Returns:
            LoadError: The code.
    '''
    with pytest.raises(RowRejected) as refusal:
        validate_row(EntryRowSchema(**fields), CATALOG, TODAY)
    return refusal.value.code


def test_a_good_row_is_normalized():
    '''The Spanish word and the API value mean the same periodicity.'''
    entry = validate_row(EntryRowSchema(**SALES), CATALOG, TODAY)
    assert (entry.periodicity, entry.key) == (Periodicity.MONTHLY, 'MONTHLY#2026-03#4.1.01')
    assert (entry.invoiced, entry.taxes_included) == (True, False)
    assert validate_row(EntryRowSchema(**RENT), CATALOG, TODAY).periodicity is Periodicity.MONTHLY


@pytest.mark.parametrize(('change', 'code'), [
    ({'account_code': '9.9.99'}, LoadError.UNKNOWN_ACCOUNT),
    ({'account_code': None}, LoadError.UNKNOWN_ACCOUNT),
    ({'account_code': '4.1'}, LoadError.ACCOUNT_IS_GROUP),
    ({'date': None}, LoadError.MISSING_DATE),
    ({'periodicity': 'Semanal'}, LoadError.INVALID_PERIODICITY),
    ({'date': '2026-03-05'}, LoadError.DATE_PERIODICITY_MISMATCH),
    ({'date': '2026-13'}, LoadError.DATE_PERIODICITY_MISMATCH),
    ({'date': '2099-01'}, LoadError.FUTURE_PERIOD),
    ({'amount': 'mil'}, LoadError.INVALID_AMOUNT),
    ({'amount': None}, LoadError.INVALID_AMOUNT),
    ({'amount': -1}, LoadError.NEGATIVE_AMOUNT),
])
def test_each_rule_has_its_code(
    change,
    code
):
    '''Every broken rule answers with its own code.'''
    assert _code(**{**RENT, **change}) is code


@pytest.mark.parametrize('flags', [
    {'invoiced': None}, {'taxes_included': ''}, {'invoiced': 'Tal vez'}
])
def test_income_rows_need_both_invoice_flags(flags):
    '''«No podemos inferir»: an empty or unknown flag is refused, not assumed.'''
    assert _code(**{**SALES, **flags}) is LoadError.MISSING_INVOICE_FLAGS


def test_the_flags_are_ignored_outside_income():
    '''On an expense they mean nothing and are not stored.'''
    entry = validate_row(EntryRowSchema(**{**RENT, 'invoiced': 'Sí'}), CATALOG, TODAY)
    assert entry.invoiced is None


def test_spreadsheet_shapes_are_read_as_written():
    '''A day keeps its midnight and a year arrives as 2026.0 from a number cell.'''
    day = validate_row(EntryRowSchema(**{**RENT, 'periodicity': 'Diaria',
                                         'date': '2026-03-05 00:00:00'}), CATALOG, TODAY)
    year = validate_row(EntryRowSchema(**{**RENT, 'periodicity': 'Anual',
                                          'date': 2025.0}), CATALOG, TODAY)
    assert (day.date, year.date) == ('2026-03-05', '2025')


def test_the_current_month_is_not_the_future():
    '''A month in progress can be loaded; the next one cannot.'''
    assert validate_row(EntryRowSchema(**{**RENT, 'date': '2026-10'}), CATALOG, TODAY)
    assert _code(**{**RENT, 'date': '2026-11'}) is LoadError.FUTURE_PERIOD


def test_one_period_never_mixes_periodicities():
    '''A month refuses its days and its year, inside the load and in storage.'''
    assert conflicting_prefixes(Periodicity.MONTHLY, '2026-03') == [
        'DAILY#2026-03-', 'ANNUAL#2026#'
    ]
    rows = [EntryRowSchema(**RENT),
            EntryRowSchema(**{**RENT, 'periodicity': 'Diaria', 'date': '2026-03-05'}),
            EntryRowSchema(**RENT)]
    valid, rejected = validate_rows(rows, CATALOG, TODAY, lambda prefix: False, 2)
    assert len(valid) == 1
    assert [(item.row, item.code) for item in rejected] == [
        (3, LoadError.PERIODICITY_CONFLICT), (4, LoadError.DUPLICATE_ROW)
    ]
    _, rejected = validate_rows([EntryRowSchema(**RENT)], CATALOG, TODAY,
                                lambda prefix: prefix == 'ANNUAL#2026#', 1)
    assert rejected[0].code is LoadError.PERIODICITY_CONFLICT
