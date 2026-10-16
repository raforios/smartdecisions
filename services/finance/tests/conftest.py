'''
    Shared test fixtures: both FINANCE tables, mocked, so the suite never
    touches the tables configured in .env.

    The domain tests and the route tests need the very same tables: a table
    built differently in one of them would let the suite agree with itself
    and disagree with AWS.
'''
import boto3
import pytest
from moto import mock_aws

from schemas.finance import AccountSchema, AccountType
from services import finance


@pytest.fixture(name = 'finance_store')
def finance_store_fixture():
    '''
        The catalog and the law parameter tables, mocked.

        Yields:
            ServiceResource: The resource.
    '''
    with mock_aws():
        resource = boto3.resource('dynamodb', region_name = 'us-east-1')
        resource.create_table(
            TableName = finance.ACCOUNTS_TABLE,
            KeySchema = [{'AttributeName': 'account_code', 'KeyType': 'HASH'}],
            AttributeDefinitions = [{'AttributeName': 'account_code', 'AttributeType': 'S'}],
            BillingMode = 'PAY_PER_REQUEST'
        )
        resource.create_table(
            TableName = finance.LAW_PARAMETERS_TABLE,
            KeySchema = [{'AttributeName': 'parameter_code', 'KeyType': 'HASH'},
                         {'AttributeName': 'valid_from', 'KeyType': 'RANGE'}],
            AttributeDefinitions = [{'AttributeName': 'parameter_code', 'AttributeType': 'S'},
                                    {'AttributeName': 'valid_from', 'AttributeType': 'S'}],
            BillingMode = 'PAY_PER_REQUEST'
        )
        yield resource


@pytest.fixture(name = 'expenses_group')
def expenses_group_fixture(finance_store):
    '''
        The catalog holding one group: 6.1 Gastos de administración.

        Returns:
            ServiceResource: The resource.
    '''
    finance.create_account(finance_store, AccountSchema(
        account_code = '6.1', name = 'Gastos de administración',
        account_type = AccountType.EXPENSE
    ))
    return finance_store
