'''
    Shared DynamoDB (moto) helpers for the Mining Summit test suite.

    Centralizes the table-provisioning boilerplate so each test fixture only
    declares the tables it needs and its seed data.
'''
from typing import Iterable, Tuple

import boto3


def build_resource(table_specs: Iterable[Tuple[str, str]]):
    '''
        Creates a mocked DynamoDB resource with the given single-hash-key tables.

        Must be called inside an active ``moto.mock_aws()`` context.

        Args:
            table_specs (Iterable[Tuple[str, str]]): (table_name, partition_key)
                pairs to provision.

        Returns:
            The boto3 DynamoDB resource with every requested table created.
    '''
    resource = boto3.resource('dynamodb', region_name = 'us-east-1')
    for name, key in table_specs:
        resource.create_table(
            TableName = name,
            KeySchema = [{'AttributeName': key, 'KeyType': 'HASH'}],
            AttributeDefinitions = [{'AttributeName': key, 'AttributeType': 'S'}],
            BillingMode = 'PAY_PER_REQUEST'
        )
    return resource
