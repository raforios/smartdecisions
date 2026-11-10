'''
    Database Connection

    Taken from LOCALIZATION and TRADE, tested there with MySQL and PostgreSQL
    (Rafael, 10-nov-2026), with three changes for this platform:

        - Lambda: every concurrent execution is its own process with its own
          pool, so the pool size comes from the .env (one connection per
          process until an RDS Proxy sits in front).
        - SSL: the shared instance only accepts encrypted connections; the
          mode comes from the .env so a MySQL service is not forced into it.
        - SQLite (the tests): no pool sizes, and one connection shared by
          every session so an in-memory database lives for the whole run.
'''
from collections.abc import Callable, Generator

from sqlalchemy import URL, create_engine
from sqlalchemy.engine.base import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from core.environment import load_and_validate_env_vars

ENV_VARS = load_and_validate_env_vars(
    {
        'DB_USER': str,
        'DB_PASSWORD': str,
        'DB_HOST': str,
        'DATABASE': str,
        'DB_PORT': int,
        'DB_DIALECT': str,
        'DB_POOL_SIZE': int,
        'DB_MAX_OVERFLOW': int,
        'DB_SSLMODE': str
    }
)


class Base(DeclarativeBase):  # pylint: disable=too-few-public-methods
    '''
        Base class of every SQLAlchemy model of the service.
    '''


def get_database_engine(db_dialect: str) -> Engine:
    '''
        Creates the SQLAlchemy engine for the configured database.

        Args:
            db_dialect (str): The dialect and driver, e.g. 'postgresql+psycopg2',
                'mysql+pymysql' or 'sqlite+pysqlite'.

        Returns:
            Engine: The configured database engine.

        Raises:
            ValueError: If the URL cannot be built from the configuration.
            RuntimeError: For any other error while creating the engine.
    '''
    try:
        if db_dialect.startswith('sqlite'):
            return create_engine(
                URL.create(db_dialect, database = ENV_VARS['DATABASE']),
                connect_args = {'check_same_thread': False},
                poolclass = StaticPool
            )
        url_database = URL.create(
            db_dialect,
            username = ENV_VARS['DB_USER'],
            password = ENV_VARS['DB_PASSWORD'],
            host = ENV_VARS['DB_HOST'],
            database = ENV_VARS['DATABASE'],
            port = ENV_VARS['DB_PORT']
        )
        connect_args = ({'sslmode': ENV_VARS['DB_SSLMODE']}
                        if db_dialect.startswith('postgresql') else {})
        return create_engine(
            url_database,
            connect_args = connect_args,
            pool_pre_ping = True,
            pool_size = ENV_VARS['DB_POOL_SIZE'],
            max_overflow = ENV_VARS['DB_MAX_OVERFLOW'],
            pool_timeout = 30,
            echo = False
        )
    except ValueError as val_e:
        raise ValueError(
            f'Error creating database URL or engine: {val_e}. Check DB_PORT or dialect.'
        ) from val_e
    except Exception as general_e:
        raise RuntimeError(
            f'An unexpected error occurred while creating the database engine: {general_e}'
        ) from general_e


def get_db_session(engine: Engine) -> Callable[[], Generator[Session, None, None]]:
    '''
        Returns a generator function that provides a database session.

        Args:
            engine (Engine): The database engine to use.

        Returns:
            Callable: A generator function to obtain a DB session; FastAPI
                closes it when the request ends.
    '''
    session_factory = sessionmaker(autocommit = False, autoflush = False, bind = engine)

    def _get_db() -> Generator[Session, None, None]:
        '''
            Opens a session for one request and always closes it.
        '''
        db: Session = session_factory()
        try:
            yield db
        finally:
            db.close()
    return _get_db


ENGINE: Engine = get_database_engine(ENV_VARS['DB_DIALECT'])
GET_DB_DEPENDENCY: Callable = get_db_session(ENGINE)  # pylint: disable=invalid-name
