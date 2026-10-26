'''
    Shared test fixtures: in-memory SQLite session bound to the SQLAlchemy
    models. Avoids touching the production MySQL configured in .env.
'''
import importlib.util
from pathlib import Path

import boto3
import pytest
from moto import mock_aws
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from services.environment import load_and_validate_env_vars

# The business values live in the service's parameters table and the modules
# read them on import: moto holds that table, seeded from the
# `mining_analysis` rows of docs/parametros.md (the rows the real table is
# seeded from), while the modules are imported, and stops once the tests are
# collected.
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
    'mining_analysis')

# The services are imported only once moto holds their parameters table, so
# they cannot be grouped with the environment reader above.
# pylint: disable=wrong-import-position,ungrouped-imports
# Importing the models module ensures Base.metadata knows every table before
# create_all runs. The import also triggers services.db_connection (which
# instantiates a MySQL engine), but the engine is lazy — no connection is
# actually opened until we exercise it, so this is safe for unit tests.
from services import prices_store  # noqa: E402
from services.db_connection_sql import Base  # noqa: E402
from services.utils import load_parameters  # noqa: E402
import models.mining_analysis  # noqa: F401,E402  pylint: disable=unused-import
# pylint: enable=wrong-import-position,ungrouped-imports
# Imported for its side effect only: it registers every table on Base.metadata
# before create_all runs. Removing it leaves the test database empty.

load_parameters({})


def pytest_collection_finish(session: pytest.Session) -> None:  # pylint: disable=unused-argument
    '''
        Every module read its values while the tests were collected: moto
        stops here, so each test starts its own as it always did.
    '''
    _PARAMETERS_MOCK.stop()


@pytest.fixture(autouse = True)
def _sql_backend(monkeypatch):
    '''
        Pins the suite to the relational backend, whatever .env selects.

        The fixtures below build a SQLite database, so the tests only mean
        something against the SQL path. Without this the suite follows
        PERSISTENCE_BACKEND: once .env switched to DynamoDB for the AWS
        deployment, the same tests started reaching out to real tables in AWS
        and failing there. A test suite must not depend on deployment
        configuration, and must never touch the cloud.
    '''
    monkeypatch.setattr(prices_store, 'BACKEND', prices_store.SQL_BACKEND)


@pytest.fixture()
def db_session():
    '''
    Yields a fresh in-memory SQLite session per test, with all SQLAlchemy
    tables created. Foreign key checks are enabled to mirror MySQL behavior.
    '''
    engine = create_engine('sqlite:///:memory:', future = True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind = engine, autocommit = False, autoflush = False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
