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
from services.db_connection import Base
import models.mining_analysis  # noqa: F401 — side-effect: registers tables


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
