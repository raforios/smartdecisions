'''
    Shared test fixtures: the parameters table, mocked, so the suite never
    touches the table configured in .env.
'''
import boto3
import pytest
from moto import mock_aws

from services import parameters


@pytest.fixture(name = 'parameters_store')
def parameters_store_fixture():
    '''
        The parameters table, mocked.

        Yields:
            ServiceResource: The resource.
    '''
    with mock_aws():
        resource = boto3.resource('dynamodb', region_name = 'us-east-1')
        resource.create_table(
            TableName = parameters.VALUES_TABLE,
            KeySchema = [{'AttributeName': 'scope', 'KeyType': 'HASH'},
                         {'AttributeName': 'code', 'KeyType': 'RANGE'}],
            AttributeDefinitions = [{'AttributeName': 'scope', 'AttributeType': 'S'},
                                    {'AttributeName': 'code', 'AttributeType': 'S'}],
            BillingMode = 'PAY_PER_REQUEST'
        )
        yield resource
