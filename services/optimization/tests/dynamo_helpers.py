'''
    Shared DynamoDB (moto) helpers for the route-tracking tests.

    The tracking tables are composite-key tables (owner + id); this provisions
    them the way the deploy does so every fixture only declares its seed.
'''
from typing import Iterable, Tuple

import boto3


def build_resource(table_specs: Iterable[Tuple[str, str, str]]):
    '''
        Creates a mocked DynamoDB resource with the given composite-key tables.

        Must be called inside an active ``moto.mock_aws()`` context.

        Args:
            table_specs (Iterable[Tuple[str, str, str]]): (table_name,
                partition_key, sort_key) triples to provision. Keys are strings.

        Returns:
            The boto3 DynamoDB resource with every requested table created.
    '''
    resource = boto3.resource('dynamodb', region_name = 'us-east-1')
    for name, partition_key, sort_key in table_specs:
        resource.create_table(
            TableName = name,
            KeySchema = [
                {'AttributeName': partition_key, 'KeyType': 'HASH'},
                {'AttributeName': sort_key, 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions = [
                {'AttributeName': partition_key, 'AttributeType': 'S'},
                {'AttributeName': sort_key, 'AttributeType': 'S'}
            ],
            BillingMode = 'PAY_PER_REQUEST'
        )
    return resource
