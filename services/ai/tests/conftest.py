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
    'test_health_route.py', 'test_health.py', 'test_service_parameters.py'
]



if CONFIGURED:
    # The business values live in the service's parameters table. The tests
    # load the same rows in memory, from the `ai` rows of docs/parametros.md,
    # before any module reads them: no AWS and no simulated table.
    import importlib.util  # noqa: E402 pylint: disable=wrong-import-position

    _DOCUMENT_READER = (Path(__file__).resolve().parents[3] / 'tools' / 'seeds'
                        / 'parameters_document.py')
    _SPEC = importlib.util.spec_from_file_location('parameters_document', _DOCUMENT_READER)
    _DOCUMENT = importlib.util.module_from_spec(_SPEC)
    _SPEC.loader.exec_module(_DOCUMENT)
    # pylint: disable-next=wrong-import-position
    from services import utils as _utils  # noqa: E402
    _utils._SERVICE_PARAMETERS.update(_DOCUMENT.values('ai'))  # pylint: disable=protected-access
