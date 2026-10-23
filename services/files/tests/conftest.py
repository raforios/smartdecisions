'''
    Shared test configuration.

    The CI of GitHub Actions runs the base services' tests with no .env (see
    .github/workflows/python-package.yml). The tests that need the service
    configured —the routes— are left out there and run locally and in
    tools/verification/verify_service.py; the pure ones run everywhere.
'''
import os
from pathlib import Path

# The service reads its configuration from .env or the environment; without
# either, importing the routes stops the collection.
CONFIGURED = ((Path(__file__).resolve().parents[1] / '.env').exists()
              or 'SECRET_KEY' in os.environ)
collect_ignore = [] if CONFIGURED else ['test_read_route.py']
