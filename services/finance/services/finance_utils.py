'''
    FINANCE support: DynamoDB plumbing the boilerplate CRUD does not cover.

    Keeps finance.py free of it. Nothing here decides anything about the
    business; it stores and reads what the domain asks for.
'''
import decimal
from typing import Any

from boto3.resources.base import ServiceResource


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


def scan_all(
    dynamodb_resource: ServiceResource,
    table_name: str
) -> list[dict[str, Any]]:
    '''
        Every item of a small global table, following the pages DynamoDB cuts.

        Only for the catalog and the law parameters: a few dozen rows that
        every client reads whole. A table keyed by client is queried, never
        scanned.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            table_name (str): Target table.

        Returns:
            list[dict[str, Any]]: The items, in no particular order.
    '''
    table = dynamodb_resource.Table(table_name)
    response = table.scan()
    items = response.get('Items', [])
    while 'LastEvaluatedKey' in response:
        response = table.scan(ExclusiveStartKey = response['LastEvaluatedKey'])
        items.extend(response.get('Items', []))
    return items
