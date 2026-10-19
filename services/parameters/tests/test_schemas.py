'''
    Tests of the parameter rules that need no configuration: they run in the
    CI of GitHub Actions, which has no .env.
'''
import pytest
from pydantic import ValidationError

from schemas.parameters import ParameterError, ParameterSchema, ValueType


@pytest.mark.parametrize(('value_type', 'value'), [
    (ValueType.NUMBER, 'dos'), (ValueType.TEXT, 2), (ValueType.LIST, 'a'), (ValueType.NUMBER, True)
])
def test_a_value_must_match_its_type(
    value_type,
    value
):
    '''A reader that asks for a number never gets a word.'''
    with pytest.raises(ValidationError, match = ParameterError.VALUE_TYPE_MISMATCH.value):
        ParameterSchema(value_type = value_type, value = value, description = 'x')


def test_each_type_takes_its_value():
    '''A number, a text and a list, each where it belongs.'''
    assert ParameterSchema(value_type = ValueType.NUMBER, value = 2, description = 'x').value == 2
    text = ParameterSchema(value_type = ValueType.TEXT, value = '4.1', description = 'x')
    assert text.value == '4.1'
    assert ParameterSchema(value_type = ValueType.LIST, value = ['a', 'b'],
                           description = 'x').value == ['a', 'b']
