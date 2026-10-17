'''
    Tests for the parameters: law rates by date, BearSoft's suggestions and
    the values each client chooses.
'''
from datetime import date

import pytest

from schemas.finance import LawParameterSchema
from schemas.report import ClientParameterSchema, ReportError, SuggestedParameterSchema
from services import finance, parameters
from services.exceptions import ResourceNotFoundError

PROVISION = SuggestedParameterSchema(parameter_code = 'IUE_PROVISION',
                                     name = 'Provisión mensual del IUE', value = 2)


def test_a_month_takes_the_rate_in_force_on_it():
    '''A change of law applies from its day on; the months before keep theirs.'''
    rates = {'IVA': [('1986-07-01', 10.0), ('1992-03-01', 13.0)]}
    assert parameters.rate_on(rates, 'IVA', date(1990, 5, 1)) == 0.10
    assert parameters.rate_on(rates, 'IVA', date(2026, 3, 1)) == 0.13
    for code, day, error in (('IT', date(2026, 3, 1), ReportError.PARAMETER_NOT_FOUND),
                             ('IVA', date(1980, 1, 1), ReportError.NO_RATE_FOR_DATE)):
        with pytest.raises(ResourceNotFoundError) as failure:
            parameters.rate_on(rates, code, day)
        assert failure.value.detail == error.value


def test_law_rates_are_read_by_code_and_date(finance_store):
    '''The stored values come back grouped and in order.'''
    for valid_from, rate in ((date(1992, 3, 1), 13.0), (date(1986, 7, 1), 10.0)):
        finance.set_law_parameter(finance_store, LawParameterSchema(
            parameter_code = 'IVA', name = 'IVA', rate = rate, valid_from = valid_from))
    assert parameters.law_rates(finance_store) == {
        'IVA': [('1986-07-01', 10.0), ('1992-03-01', 13.0)]}


def test_a_client_sees_the_suggestion_until_it_sets_its_own(finance_store):
    '''The suggestion is shown, never applied: the client's value starts empty.'''
    parameters.set_suggested_parameter(finance_store, PROVISION)
    listed = parameters.list_client_parameters(finance_store, 'acme').parameters[0]
    assert (listed.suggested, listed.value) == (2.0, None)
    assert parameters.client_value(finance_store, 'acme', 'IUE_PROVISION') is None

    parameters.set_client_parameter(finance_store, ('acme', 'ana@acme.com'), 'IUE_PROVISION',
                                    ClientParameterSchema(value = 1.5))
    assert parameters.client_value(finance_store, 'acme', 'IUE_PROVISION') == 1.5
    assert parameters.client_value(finance_store, 'otra', 'IUE_PROVISION') is None


def test_only_a_parameter_bearsoft_defined_can_be_set(finance_store):
    '''An unknown code is refused, not created.'''
    with pytest.raises(ResourceNotFoundError) as failure:
        parameters.set_client_parameter(finance_store, ('acme', 'ana@acme.com'), 'INVENTADO',
                                        ClientParameterSchema(value = 1))
    assert failure.value.detail == ReportError.PARAMETER_NOT_FOUND.value
    assert parameters.list_suggested_parameters(finance_store).total == 0
