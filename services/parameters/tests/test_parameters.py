'''
    Tests for the parameters: values that change without a release, typed,
    by scope.
'''
import pytest

from schemas.parameters import ParameterError, ParameterSchema, ValueType
from services import parameters
from services.exceptions import ResourceNotFoundError

DECIMALS = ParameterSchema(value_type = ValueType.NUMBER, value = 2,
                           description = 'Decimales de un monto publicado.')
CASH = ParameterSchema(value_type = ValueType.LIST, value = ['1.1.01', '1.1.02'],
                       description = 'Cuentas de efectivo.')


def test_a_service_reads_only_its_scope(parameters_store):
    '''FINANCE reads finance and global; another scope is not mixed in.'''
    parameters.set_parameter(parameters_store, ('global', 'AMOUNT_DECIMALS'), DECIMALS)
    parameters.set_parameter(parameters_store, ('finance', 'CASH_ACCOUNTS'), CASH)
    finance = parameters.scope_parameters(parameters_store, 'finance')
    assert [(p.code, p.value) for p in finance.parameters] == [
        ('CASH_ACCOUNTS', ['1.1.01', '1.1.02'])]
    number = parameters.scope_parameters(parameters_store, 'global').parameters[0]
    assert (number.value, type(number.value)) == (2.0, float)
    assert parameters.scope_parameters(parameters_store, 'quotes').total == 0


def test_a_change_replaces_the_value(parameters_store):
    '''Setting the same code again is the change that needs no release.'''
    parameters.set_parameter(parameters_store, ('global', 'AMOUNT_DECIMALS'), DECIMALS)
    parameters.set_parameter(parameters_store, ('global', 'AMOUNT_DECIMALS'),
                             ParameterSchema(**{**DECIMALS.model_dump(), 'value': 4}))
    listed = parameters.all_parameters(parameters_store)
    assert (listed.total, listed.parameters[0].value) == (1, 4.0)


def test_a_parameter_is_removed_or_said_missing(parameters_store):
    '''Deleting twice: the second time it does not exist.'''
    parameters.set_parameter(parameters_store, ('global', 'AMOUNT_DECIMALS'), DECIMALS)
    parameters.delete_parameter(parameters_store, ('global', 'AMOUNT_DECIMALS'))
    with pytest.raises(ResourceNotFoundError) as failure:
        parameters.delete_parameter(parameters_store, ('global', 'AMOUNT_DECIMALS'))
    assert failure.value.detail == ParameterError.PARAMETER_NOT_FOUND.value
