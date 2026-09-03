'''
    Shared test fixtures: in-memory SQLite session bound to the SQLAlchemy
    models. Avoids touching the production MySQL configured in .env.
'''
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Importing the models module ensures Base.metadata knows every table before
# create_all runs. The import also triggers services.db_connection (which
# instantiates a MySQL engine), but the engine is lazy — no connection is
# actually opened until we exercise it, so this is safe for unit tests.
from services import prices_store
from services.db_connection import Base
import models.mining_analysis  # noqa: F401  pylint: disable=unused-import
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
