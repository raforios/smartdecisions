'''
    Shared test fixtures.

    The CI of GitHub Actions runs the base services' tests with no .env (see
    .github/workflows/python-package.yml). The tests that need the service
    configured —the table, the routes— are left out there and run locally and
    in tools/verification/verify_service.py; the pure ones (schemas and their
    rules) run everywhere.
'''
import os
from pathlib import Path

import pytest

# The service reads its configuration from .env or the environment; without
# either, importing services.parameters stops the collection.
CONFIGURED = ((Path(__file__).resolve().parents[1] / '.env').exists()
              or 'TARGET_TIMEZONE' in os.environ)
collect_ignore = [] if CONFIGURED else [
    'test_parameters.py', 'test_controllers.py', 'test_health_route.py', 'test_health.py'
]


@pytest.fixture(name = 'parameters_store')
def parameters_store_fixture():
    '''
        The parameters table, mocked.

        Yields:
            ServiceResource: The resource.
    '''
    # Imported here: the CI installs neither moto nor the service's configuration.
    import boto3  # pylint: disable=import-outside-toplevel
    from moto import mock_aws  # pylint: disable=import-outside-toplevel,import-error
    from services import parameters  # pylint: disable=import-outside-toplevel
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
