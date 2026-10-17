'''
    PARAMETERS support: DynamoDB plumbing the boilerplate CRUD does not cover.

    Keeps parameters.py free of it. Nothing here decides anything about the
    business; it stores and reads what the domain asks for.
'''
import decimal
from typing import Any


def to_dynamo(value: Any) -> Any:
    '''
        Converts floats to Decimal, the only numeric type DynamoDB accepts.
        Named as in QUOTES, OPTIMIZATION and INGEST, which solve the same problem.

        Args:
            value (Any): Value, possibly nested, to convert.

        Returns:
            Any: The same structure with every float turned into Decimal.
    '''
    if isinstance(value, float):
        return decimal.Decimal(str(value))
    if isinstance(value, dict):
        return {key: to_dynamo(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_dynamo(item) for item in value]
    return value
