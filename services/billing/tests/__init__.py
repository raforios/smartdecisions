'''
    Test package bootstrap.

    Two things must be in place *before* any test module imports the service:

        1. The DB_* environment variables, because services.db_connection
           validates its configuration at import time (the engine itself is
           created lazily and never actually connects during the tests).
        2. The scripts/ directory on sys.path, because the catalog importer is
           a standalone script that lives outside the package.

    Doing both here — the package initializer, which Python always runs first —
    lets every test module keep its imports at the top of the file.
'''
import os
import sys

_SERVICE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault('DB_USER', 'test')
os.environ.setdefault('DB_PASSWORD', 'test')
os.environ.setdefault('DB_HOST', 'localhost')
os.environ.setdefault('DATABASE', 'test')
os.environ.setdefault('DB_PORT', '3306')
os.environ.setdefault('DB_DIALECT', 'mysql+pymysql')

sys.path.insert(0, os.path.join(_SERVICE_DIR, 'scripts'))
