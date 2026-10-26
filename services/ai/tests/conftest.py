'''
    Shared test configuration.

    The CI of GitHub Actions runs the base services' tests with no .env (see
    .github/workflows/python-package.yml). The tests that need the service
    configured —its tables, EVENTS— are left out there and run
    locally and in tools/verification/verify_service.py; the pure ones (the
    schemas and their rules) run everywhere.
'''
import os
from pathlib import Path

# The service reads its configuration from .env or the environment; without
# either, importing services.utils stops the collection.
CONFIGURED = ((Path(__file__).resolve().parents[1] / '.env').exists()
              or 'TARGET_TIMEZONE' in os.environ)
collect_ignore = [] if CONFIGURED else [
    'test_ai.py', 'test_controllers.py', 'test_error_contract.py', 'test_security_roles.py',
    'test_health_route.py', 'test_health.py'
]


if CONFIGURED:
    # The business values live in the service's parameters table and are read
    # the first time a module asks: moto holds that table, seeded from the
    # `ai` rows of docs/parametros.md (the rows the real table is seeded
    # from), and they are read here, before any test starts its own moto.
    # pylint: disable=wrong-import-position,ungrouped-imports
    import importlib.util  # noqa: E402

    import boto3  # noqa: E402
    # moto is in services/requirements-dev.txt: the GitHub CI installs only
    # requirements.txt and never reaches this block (no .env there).
    from moto import mock_aws  # noqa: E402 pylint: disable=import-error

    from services.environment import load_and_validate_env_vars  # noqa: E402
    # pylint: enable=wrong-import-position,ungrouped-imports

    _DOCUMENT_READER = (Path(__file__).resolve().parents[3] / 'tools' / 'seeds'
                        / 'parameters_document.py')
    _SPEC = importlib.util.spec_from_file_location('parameters_document', _DOCUMENT_READER)
    _DOCUMENT = importlib.util.module_from_spec(_SPEC)
    _SPEC.loader.exec_module(_DOCUMENT)
    with mock_aws():
        _DOCUMENT.create_and_seed(
            boto3.resource('dynamodb', region_name = 'us-east-1'),
            load_and_validate_env_vars({'DYNAMODB_TABLE_NAME_SERVICE_PARAMETERS': str})[
                'DYNAMODB_TABLE_NAME_SERVICE_PARAMETERS'],
            'ai')
        # pylint: disable-next=wrong-import-position
        from services.utils import load_parameters  # noqa: E402
        load_parameters({})
