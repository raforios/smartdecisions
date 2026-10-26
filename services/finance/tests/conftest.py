'''
    Shared test fixtures: the FINANCE tables, mocked, so the suite never
    touches the tables configured in .env.

    The domain tests and the route tests need the very same tables: a table
    built differently in one of them would let the suite agree with itself
    and disagree with AWS.
'''
import importlib.util
from pathlib import Path

import boto3
import pytest
from moto import mock_aws


_DOCUMENT_READER = (Path(__file__).resolve().parents[3] / 'tools' / 'seeds'
                    / 'parameters_document.py')
_SPEC = importlib.util.spec_from_file_location('parameters_document', _DOCUMENT_READER)
_DOCUMENT = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_DOCUMENT)

# The business values live in the service's parameters table. The tests load
# the same rows in memory, from docs/parametros.md, before any module reads
# them on import: no AWS and no simulated table. That is why the service's
# modules are imported here, after the values, and not with the others.
# pylint: disable=wrong-import-position,ungrouped-imports
from services import utils as _utils  # noqa: E402

_utils._SERVICE_PARAMETERS.update(_DOCUMENT.values('finance'))  # pylint: disable=protected-access

from schemas.finance import AccountSchema, AccountType  # noqa: E402
from services import business_model, entries, finance, parameters  # noqa: E402
# pylint: enable=wrong-import-position,ungrouped-imports


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
        resource.create_table(
            TableName = parameters.SUGGESTED_TABLE,
            KeySchema = [{'AttributeName': 'parameter_code', 'KeyType': 'HASH'}],
            AttributeDefinitions = [{'AttributeName': 'parameter_code', 'AttributeType': 'S'}],
            BillingMode = 'PAY_PER_REQUEST'
        )
        resource.create_table(
            TableName = parameters.CLIENT_TABLE,
            KeySchema = [{'AttributeName': 'client', 'KeyType': 'HASH'},
                         {'AttributeName': 'parameter_code', 'KeyType': 'RANGE'}],
            AttributeDefinitions = [{'AttributeName': 'client', 'AttributeType': 'S'},
                                    {'AttributeName': 'parameter_code', 'AttributeType': 'S'}],
            BillingMode = 'PAY_PER_REQUEST'
        )
        resource.create_table(
            TableName = business_model.BUSINESS_MODELS_TABLE,
            KeySchema = [{'AttributeName': 'client', 'KeyType': 'HASH'}],
            AttributeDefinitions = [{'AttributeName': 'client', 'AttributeType': 'S'}],
            BillingMode = 'PAY_PER_REQUEST'
        )
        for table in (entries.LOADS_TABLE, entries.ENTRIES_TABLE):
            sort = 'load_id' if table == entries.LOADS_TABLE else 'entry_key'
            extra = {}
            definitions = [{'AttributeName': 'client', 'AttributeType': 'S'},
                           {'AttributeName': sort, 'AttributeType': 'S'}]
            if table == entries.ENTRIES_TABLE:
                # The same index AWS has: whether any client used an account.
                definitions.append({'AttributeName': 'account_code', 'AttributeType': 'S'})
                extra['GlobalSecondaryIndexes'] = [{
                    'IndexName': finance.ACCOUNT_INDEX,
                    'KeySchema': [{'AttributeName': 'account_code', 'KeyType': 'HASH'}],
                    'Projection': {'ProjectionType': 'KEYS_ONLY'}
                }]
            resource.create_table(
                TableName = table,
                KeySchema = [{'AttributeName': 'client', 'KeyType': 'HASH'},
                             {'AttributeName': sort, 'KeyType': 'RANGE'}],
                AttributeDefinitions = definitions,
                BillingMode = 'PAY_PER_REQUEST',
                **extra
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


@pytest.fixture(name = 'catalog')
def catalog_fixture(finance_store):
    '''
        A small catalog: one income account, one expense account and their
        groups — enough for every rule of a load.

        Returns:
            ServiceResource: The resource.
    '''
    for account in (
        AccountSchema(account_code = '4.1', name = 'Ventas', account_type = AccountType.INCOME),
        AccountSchema(account_code = '4.1.01', name = 'Ventas de mercaderías con factura',
                      account_type = AccountType.INCOME, group_code = '4.1', invoiced = True),
        AccountSchema(account_code = '6.1', name = 'Gastos de administración',
                      account_type = AccountType.EXPENSE),
        AccountSchema(account_code = '6.1.03', name = 'Alquileres pagados',
                      account_type = AccountType.EXPENSE, group_code = '6.1'),
    ):
        finance.create_account(finance_store, account)
    return finance_store
