'''
    Shared test fixtures: in-memory SQLite session bound to the SQLAlchemy
    models. Avoids touching the production MySQL configured in .env.
'''
import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


_DOCUMENT_READER = (Path(__file__).resolve().parents[3] / 'tools' / 'seeds'
                    / 'parameters_document.py')
_SPEC = importlib.util.spec_from_file_location('parameters_document', _DOCUMENT_READER)
_DOCUMENT = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_DOCUMENT)

# The business values live in the service's parameters table. The tests load
# the same rows in memory, from docs/parametros.md, before any module reads
# them on import: no AWS and no simulated table. That is why the service's
# modules are imported here, after the values, and not with the others.
# pylint: disable=wrong-import-position,ungrouped-imports
from services import utils as _utils  # noqa: E402

_utils._SERVICE_PARAMETERS.update(_DOCUMENT.values('mining_analysis'))  # pylint: disable=protected-access

from services import prices_store  # noqa: E402
from services.db_connection_sql import Base  # noqa: E402
import models.mining_analysis  # noqa: F401,E402  pylint: disable=unused-import
# pylint: enable=wrong-import-position,ungrouped-imports
# Imported for its side effect only: it registers every table on Base.metadata
# before create_all runs. Removing it leaves the test database empty.


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
