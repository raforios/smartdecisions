'''
    Tests for the chart of accounts and the law parameters.

    What they defend: the catalog is one, an account never changes what it
    does, an account sits in a group of its own type, and a new law rate never
    rewrites the months that were computed with the old one.
'''
from datetime import date

import pytest

from schemas.finance import (
    AccountSchema,
    AccountType,
    AccountUpdateSchema,
    FinanceError,
    LawParameterSchema
)
from services import finance
from services.exceptions import (
    InvalidInputError,
    RegisterAlreadyExistsError,
    ResourceNotFoundError
)

TAXES = AccountSchema(
    account_code = '6.1.07', name = 'Impuestos, tasas y patentes',
    account_type = AccountType.EXPENSE, group_code = '6.1'
)


def test_an_account_joins_an_existing_group(expenses_group):
    '''Created under its group, it comes back with its type and group.'''
    account = finance.create_account(expenses_group, TAXES)
    assert (account.account_code, account.group_code) == ('6.1.07', '6.1')
    assert account.account_type == AccountType.EXPENSE


def test_only_sales_and_purchases_carry_the_invoice_mark():
    '''A purchase can have an invoice; an expense account never carries the mark.'''
    purchases = AccountSchema(account_code = '5.1.02', name = 'Compras con factura',
                              account_type = AccountType.COST, group_code = '5.1',
                              invoiced = True)
    assert purchases.invoiced is True
    with pytest.raises(ValueError, match = 'INVOICE_ONLY_ON_SALES_AND_PURCHASES'):
        AccountSchema(**{**TAXES.model_dump(), 'invoiced': True})


def test_a_code_is_never_repeated(expenses_group):
    '''The second account with the same code is refused with its code.'''
    finance.create_account(expenses_group, TAXES)
    with pytest.raises(RegisterAlreadyExistsError) as failure:
        finance.create_account(expenses_group, TAXES)
    assert failure.value.detail == FinanceError.DUPLICATE_ACCOUNT_CODE.value


def test_an_account_needs_an_existing_group(finance_store):
    '''A group that does not exist is refused, not created on the fly.'''
    with pytest.raises(InvalidInputError) as failure:
        finance.create_account(finance_store, TAXES)
    assert failure.value.detail == FinanceError.GROUP_NOT_FOUND.value


def test_an_account_cannot_sit_in_a_group_of_another_type(expenses_group):
    '''An Ingresos account inside a Gastos group would land on the wrong line.'''
    with pytest.raises(InvalidInputError) as failure:
        finance.create_account(expenses_group, AccountSchema(
            account_code = '6.1.99', name = 'Venta de cursos',
            account_type = AccountType.INCOME, group_code = '6.1'
        ))
    assert failure.value.detail == FinanceError.GROUP_TYPE_MISMATCH.value


def test_the_catalog_is_ordered_as_a_reader_expects(expenses_group):
    '''6.1.10 after 6.1.9, not after 6.1.1 as plain text would put it.'''
    for code in ('6.1.10', '6.1.9'):
        finance.create_account(expenses_group, TAXES.model_copy(update = {'account_code': code}))
    catalog = finance.list_accounts(expenses_group)
    assert [account.account_code for account in catalog.accounts] == ['6.1', '6.1.9', '6.1.10']
    assert catalog.total == 3


def test_renaming_changes_only_the_text(expenses_group):
    '''The name changes; the code, the type and the group stay.'''
    finance.create_account(expenses_group, TAXES)
    renamed = finance.rename_account(expenses_group, '6.1.07',
                                     AccountUpdateSchema(name = 'Impuestos y patentes'))
    assert renamed.name == 'Impuestos y patentes'
    assert (renamed.account_type, renamed.group_code) == (AccountType.EXPENSE, '6.1')


def test_renaming_an_unknown_account_is_refused(finance_store):
    '''An account that does not exist answers ACCOUNT_NOT_FOUND.'''
    with pytest.raises(ResourceNotFoundError) as failure:
        finance.rename_account(finance_store, '9.9.99', AccountUpdateSchema(name = 'X'))
    assert failure.value.detail == FinanceError.ACCOUNT_NOT_FOUND.value


def test_a_group_with_accounts_is_not_deleted(expenses_group):
    '''Deleting the group would leave its accounts pointing at nothing.'''
    finance.create_account(expenses_group, TAXES)
    with pytest.raises(InvalidInputError) as failure:
        finance.delete_account(expenses_group, '6.1')
    assert failure.value.detail == FinanceError.GROUP_HAS_ACCOUNTS.value


def test_an_account_and_then_its_group_are_deleted(expenses_group):
    '''Once empty, the group goes too, and the catalog is left empty.'''
    finance.create_account(expenses_group, TAXES)
    finance.delete_account(expenses_group, '6.1.07')
    finance.delete_account(expenses_group, '6.1')
    assert finance.list_accounts(expenses_group).total == 0
    with pytest.raises(ResourceNotFoundError):
        finance.delete_account(expenses_group, '6.1')


def test_a_new_rate_keeps_the_old_one(finance_store):
    '''A change of law adds a value; the months before keep theirs.'''
    for valid_from, rate in ((date(1992, 1, 1), 13.0), (date(2027, 1, 1), 14.0)):
        finance.set_law_parameter(finance_store, LawParameterSchema(
            parameter_code = 'IVA', name = 'Impuesto al Valor Agregado',
            rate = rate, valid_from = valid_from
        ))
    listed = finance.list_law_parameters(finance_store)
    assert [(item.valid_from.year, item.rate) for item in listed.parameters] == [
        (1992, 13.0), (2027, 14.0)
    ]


def test_the_same_date_corrects_the_rate(finance_store):
    '''Typing the same day again fixes it instead of leaving two rates.'''
    for rate in (3.5, 3.0):
        stored = finance.set_law_parameter(finance_store, LawParameterSchema(
            parameter_code = 'IT', name = 'Impuesto a las Transacciones',
            rate = rate, valid_from = date(1992, 1, 1)
        ))
    assert stored.rate == 3.0
    assert finance.list_law_parameters(finance_store).total == 1
