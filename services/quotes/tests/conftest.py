'''
    Shared test configuration.

    The CI of GitHub Actions runs the base services' tests with no .env (see
    .github/workflows/python-package.yml). The tests that need the service
    configured —its tables, its business values, EVENTS— are left out there
    and run locally and in tools/verification/verify_service.py, with the
    fixtures of tests/fixtures.py; the pure ones (the schemas and their rules)
    run everywhere.
'''
import os
from pathlib import Path

# The service reads its configuration from .env or the environment; without
# either, importing services.utils stops the collection.
CONFIGURED = ((Path(__file__).resolve().parents[1] / '.env').exists()
              or 'TARGET_TIMEZONE' in os.environ)
collect_ignore = [] if CONFIGURED else [
    'fixtures.py', 'test_controllers.py', 'test_error_contract.py', 'test_factors.py',
    'test_handler.py', 'test_health_route.py', 'test_health.py', 'test_quotes.py',
    'test_security_roles.py', 'test_service_parameters.py'
]

if CONFIGURED:
    # pytest registers a fixture by finding it in this module, so they are
    # brought here by name (they are not otherwise used in this file).
    from tests.fixtures import (  # noqa: F401 pylint: disable=unused-import
        _midweek,
        _seeded_store,
        _store,
        factor_store_fixture,
        ml_functions
    )
