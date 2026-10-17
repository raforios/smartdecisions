'''
    Pydantic V2 DTOs for the parameters every service reads.

    A parameter is a business value that may change without a release: a
    number of decimals, a unit, the account a report treats as sales. It
    lives here and not in the `.env`, which is only for the environment
    (Rafael, 17-oct-2026). Each one belongs to a scope: `global` for what more
    than one service uses, or the name of the service that reads it.
'''
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class ParameterError(str, Enum):
    '''
        Why a request on the parameters was refused.
    '''
    PARAMETER_NOT_FOUND = 'PARAMETER_NOT_FOUND'
    VALUE_TYPE_MISMATCH = 'VALUE_TYPE_MISMATCH'


class ValueType(str, Enum):
    '''
        What kind of value a parameter holds, so the reader can trust it.
    '''
    NUMBER = 'NUMBER'
    TEXT = 'TEXT'
    LIST = 'LIST'


class ParameterSchema(BaseModel):
    '''
        The value of a parameter and what it governs.
    '''
    value_type: ValueType
    value: float | str | list[str]
    description: str = Field(..., min_length = 1, max_length = 500,
                             description = 'What the value governs, and why that value.')

    @field_validator('value', mode = 'before')
    @classmethod
    def no_booleans(
        cls,
        value: Any
    ) -> Any:
        '''
            A yes/no is not a number: Pydantic would turn True into 1.0
            before the type check could see it.

            Args:
                value (Any): The value as it arrived.

            Returns:
                Any: The same value.

            Raises:
                ValueError: VALUE_TYPE_MISMATCH.
        '''
        if isinstance(value, bool):
            raise ValueError(ParameterError.VALUE_TYPE_MISMATCH.value)
        return value

    @model_validator(mode = 'after')
    def value_matches_its_type(self) -> 'ParameterSchema':
        '''
            A NUMBER holds a number, a TEXT a text, a LIST a list of texts:
            a reader that asks for a number must never get a word.

            Returns:
                ParameterSchema: The parameter, unchanged.

            Raises:
                ValueError: VALUE_TYPE_MISMATCH.
        '''
        expected = {ValueType.NUMBER: (int, float), ValueType.TEXT: str, ValueType.LIST: list}
        if not isinstance(self.value, expected[self.value_type]):
            raise ValueError(ParameterError.VALUE_TYPE_MISMATCH.value)
        return self


class ParameterResponseSchema(ParameterSchema):
    '''
        A parameter as it is stored.
    '''
    scope: str
    code: str
    updated_at: str


class ParameterListResponseSchema(BaseModel):
    '''
        The parameters of a scope, or of every scope, ordered by scope and code.
    '''
    parameters: list[ParameterResponseSchema]
    total: int
