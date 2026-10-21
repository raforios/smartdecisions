'''
    Shared test configuration.

    The CI of GitHub Actions runs the base services' tests with no .env (see
    .github/workflows/python-package.yml). The tests that need the service
    configured —its tables, PARAMETERS, EVENTS— are left out there and run
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
