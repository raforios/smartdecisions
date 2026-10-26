'''
    What every BILLING test needs before anything is imported: its business
    values. They live in the service's parameters table and the modules read
    them on import; moto holds that table, seeded from the `billing` rows of
    docs/parametros.md (the rows the real table is seeded from), while the
    modules are imported, and stops once the tests are collected.
'''
import importlib.util
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

from services.environment import load_and_validate_env_vars

_DOCUMENT_READER = (Path(__file__).resolve().parents[3] / 'tools' / 'seeds'
                    / 'parameters_document.py')
_SPEC = importlib.util.spec_from_file_location('parameters_document', _DOCUMENT_READER)
_DOCUMENT = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_DOCUMENT)
_PARAMETERS_MOCK = mock_aws()
_PARAMETERS_MOCK.start()
_DOCUMENT.create_and_seed(
    boto3.resource('dynamodb', region_name = 'us-east-1'),
    load_and_validate_env_vars({'DYNAMODB_TABLE_NAME_SERVICE_PARAMETERS': str})[
        'DYNAMODB_TABLE_NAME_SERVICE_PARAMETERS'],
    'billing')

# The services are imported only once moto holds their parameters table, so
# they cannot be grouped with the environment reader above.
# pylint: disable=wrong-import-position,ungrouped-imports
from services.utils import load_parameters  # noqa: E402
# pylint: enable=wrong-import-position,ungrouped-imports

load_parameters({})


def pytest_collection_finish(session: pytest.Session) -> None:  # pylint: disable=unused-argument
    '''
        Every module read its values while the tests were collected: moto
        stops here, so each test starts its own as it always did.
    '''
    _PARAMETERS_MOCK.stop()
