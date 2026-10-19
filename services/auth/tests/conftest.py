'''
    Shared test configuration.

    The CI of GitHub Actions runs the base services' tests with no .env (see
    .github/workflows/python-package.yml). The tests that import modules which
    read the configuration on import —the routes, the controllers— are left
    out there and run locally; the pure ones run everywhere.
'''
import os
from pathlib import Path

# The service reads its configuration from .env or the environment; without
# either, importing the routes stops the collection.
CONFIGURED = ((Path(__file__).resolve().parents[1] / '.env').exists()
              or 'TABLE_NAME' in os.environ)
collect_ignore = [] if CONFIGURED else ['test_routes.py']
