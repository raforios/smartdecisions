'''
    Test package bootstrap.

    The database settings must be in place before any test module imports
    the service, because core.db_connection builds its engine on import. The
    tests run on an in-memory SQLite database shared by every session: no
    PostgreSQL and no network. Doing it here, the package initializer that
    Python always runs first, lets every test module keep its imports at the
    top of the file; a real `.env` is never read for these values.
'''
import os

for _name, _value in {
    'DB_USER': 'test', 'DB_PASSWORD': 'test', 'DB_HOST': 'localhost',
    'DATABASE': ':memory:', 'DB_PORT': '5432', 'DB_DIALECT': 'sqlite+pysqlite',
    'DB_POOL_SIZE': '1', 'DB_MAX_OVERFLOW': '0', 'DB_SSLMODE': 'disable'
}.items():
    os.environ[_name] = _value
