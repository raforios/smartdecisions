'''
    Tests for what a client loads, stored.

    What they defend: the client is part of every key, a load only replaces
    what it brings, a correction passes the same rules as a load, and an
    account with amounts cannot leave the catalog.
'''
import pytest

from schemas.entries import (
    EntryRowSchema,
    EntryUpdateSchema,
    LoadError,
    LoadFlow,
    Periodicity
)
from schemas.finance import FinanceError
from services import entries, finance
from services.exceptions import InvalidInputError, ResourceNotFoundError

ACME, OTHER, ANA = 'acme', 'otra', 'ana@acme.com'
RENT = {'date': '2026-03', 'periodicity': 'MONTHLY', 'account_code': '6.1.03', 'amount': 3500}
SALES = {'date': '2026-03', 'periodicity': 'MONTHLY', 'account_code': '4.1.01',
         'amount': 98000, 'invoiced': True, 'taxes_included': False}


def _load(
    store,
    *rows: dict
):
    '''
        Loads rows for ACME by API.

        Returns:
            LoadResultSchema: The result.
    '''
    return entries.load_entries(store, ACME, ANA, LoadFlow.PROCESSED,
                                [EntryRowSchema(**row) for row in rows])


def test_a_load_stores_what_passed_and_reports_the_rest(catalog):
    '''The good rows go in with who loaded them; the bad one is set aside.'''
    result = _load(catalog, RENT, SALES, {**RENT, 'amount': -5, 'account_code': '4.1.01'})
    assert (result.accepted, [item.code for item in result.rejected]) == (
        2, [LoadError.NEGATIVE_AMOUNT])
    stored = entries.list_entries(catalog, ACME)
    assert {entry.account_code for entry in stored.entries} == {'6.1.03', '4.1.01'}
    assert stored.entries[0].user == ANA
    history = entries.list_loads(catalog, ACME)
    assert (history.total, history.loads[0].accepted, history.loads[0].rejected) == (1, 2, 1)


def test_a_reload_only_replaces_what_it_brings(catalog):
    '''Loading March's rent again keeps March's sales (Rafael, 16-oct).'''
    _load(catalog, RENT, SALES)
    _load(catalog, {**RENT, 'amount': 3700})
    stored = {entry.account_code: entry.amount
              for entry in entries.list_entries(catalog, ACME).entries}
    assert stored == {'6.1.03': 3700.0, '4.1.01': 98000.0}


def test_another_clients_figures_do_not_exist(catalog):
    '''The client is part of the key: OTHER sees nothing and cannot touch ACME's.'''
    _load(catalog, RENT)
    assert entries.list_entries(catalog, OTHER).total == 0
    with pytest.raises(ResourceNotFoundError):
        entries.delete_entry(catalog, OTHER, (Periodicity.MONTHLY, '2026-03', '6.1.03'))


def test_a_stored_period_refuses_another_periodicity(catalog):
    '''A month loaded as such refuses its days until it is emptied.'''
    _load(catalog, RENT)
    day = {**RENT, 'periodicity': 'DAILY', 'date': '2026-03-05'}
    assert _load(catalog, day).rejected[0].code is LoadError.PERIODICITY_CONFLICT
    removed = entries.delete_period(catalog, ACME, (Periodicity.MONTHLY, '2026-03'))
    assert removed.deleted == 1
    assert _load(catalog, day).accepted == 1


def test_a_correction_changes_the_amount_and_the_date(catalog):
    '''The wrong figure and the wrong month are fixed; who fixed it is recorded.'''
    _load(catalog, RENT)
    fixed = entries.update_entry(catalog, (ACME, 'luis@acme.com'),
                                 (Periodicity.MONTHLY, '2026-03', '6.1.03'),
                                 EntryUpdateSchema(amount = 3600, date = '2026-02'))
    assert (fixed.date, fixed.amount, fixed.user) == ('2026-02', 3600.0, 'luis@acme.com')
    assert [entry.date for entry in entries.list_entries(catalog, ACME).entries] == ['2026-02']


def test_a_correction_keeps_the_rules_of_a_load(catalog):
    '''A date in the future, or onto an amount that already exists, is refused.'''
    _load(catalog, RENT, {**RENT, 'date': '2026-02'})
    target = (Periodicity.MONTHLY, '2026-03', '6.1.03')
    for update, code in ((EntryUpdateSchema(date = '2099-01'), LoadError.FUTURE_PERIOD),
                         (EntryUpdateSchema(date = '2026-02'), LoadError.DUPLICATE_ROW)):
        with pytest.raises(InvalidInputError) as failure:
            entries.update_entry(catalog, (ACME, ANA), target, update)
        assert failure.value.detail == code.value


def test_an_amount_is_removed_one_by_one(catalog):
    '''Deleting one amount leaves the rest of the period.'''
    _load(catalog, RENT, SALES)
    entries.delete_entry(catalog, ACME, (Periodicity.MONTHLY, '2026-03', '6.1.03'))
    left = entries.list_entries(catalog, ACME).entries
    assert [entry.account_code for entry in left] == ['4.1.01']


def test_an_account_with_amounts_cannot_leave_the_catalog(catalog):
    '''Whoever loaded it, a used account stays; an unused one goes.'''
    _load(catalog, RENT)
    with pytest.raises(InvalidInputError) as failure:
        finance.delete_account(catalog, '6.1.03')
    assert failure.value.detail == FinanceError.ACCOUNT_IN_USE.value
    finance.delete_account(catalog, '4.1.01')


def test_a_file_is_read_by_its_headers_and_removed(
    catalog,
    monkeypatch
):
    '''Spanish headers become fields, rows are numbered as in Excel, and the
    staged file is removed through FILES once its rows are in.'''
    removed = []
    monkeypatch.setattr(entries, 'read_file_rows', lambda key, token: [
        {'Fecha': '2026-03', 'Periodicidad': 'Mensual', 'Código de cuenta': '6.1.03',
         'Monto': 3500, 'Nota': float('nan'), 'Columna extra': 'x'},
        {'Fecha': '2026-03', 'Periodicidad': 'Mensual', 'Código de cuenta': '4.1.01',
         'Monto': 1000, 'Con factura': 'Sí', 'Impuestos incluidos': float('nan')},
    ])
    monkeypatch.setattr(entries, 'delete_stored_file', lambda key, token: removed.append(key))
    result = entries.load_entries_from_file(catalog, ACME, ANA,
                                            (LoadFlow.BASE, 'finance/marzo.xlsx'), 'Bearer x')
    assert result.accepted == 1
    assert [(item.row, item.code) for item in result.rejected] == [
        (3, LoadError.MISSING_INVOICE_FLAGS)]
    assert removed == ['finance/marzo.xlsx']


def test_an_empty_file_is_refused(
    catalog,
    monkeypatch
):
    '''A file with no rows is not a load.'''
    monkeypatch.setattr(entries, 'read_file_rows', lambda key, token: [])
    with pytest.raises(InvalidInputError) as failure:
        entries.load_entries_from_file(catalog, ACME, ANA, (LoadFlow.BASE, 'x.xlsx'), 'Bearer x')
    assert failure.value.detail == LoadError.EMPTY_LOAD.value
