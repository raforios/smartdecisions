'''
    DynamoDB item definition for the parameters.
'''
from typing import TypedDict


class ParameterItem(TypedDict, total = False):
    '''
        One parameter of one scope.

        Table: parameters_values
        Partition Key: scope (String) — `global` or the service that reads it,
                       so a service reads all of its own with one Query.
        Sort Key: code (String).
    '''
    scope: str
    code: str
    value_type: str
    value: float | str | list[str]
    description: str
    updated_at: str
