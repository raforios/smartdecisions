'''
    Database Connection
'''
import os
from typing import TypedDict, Callable, Generator
from sqlalchemy import create_engine, URL
from sqlalchemy.orm import sessionmaker, declarative_base, DeclarativeMeta, Session
from sqlalchemy.engine.base import Engine
from dotenv import dotenv_values

class DatabaseConfig(TypedDict):
    '''
        TypedDict to define the expected structure and types of database parameters.
        Ensures better type checking and clarity for DB_PARAMETERS.
    '''
    DB_USER: str
    DB_PASSWORD: str
    DB_HOST: str
    DATABASE: str
    DB_PORT: str
    DB_DIALECT: str

_LOCAL_ENV_PARAMS = dotenv_values('.env') if os.path.exists('.env') else {}

DB_PARAMETERS: DatabaseConfig = {
    'DB_USER': os.environ.get('DB_USER') or _LOCAL_ENV_PARAMS.get('DB_USER'),
    'DB_PASSWORD': os.environ.get('DB_PASSWORD') or _LOCAL_ENV_PARAMS.get('DB_PASSWORD'),
    'DB_HOST': os.environ.get('DB_HOST') or _LOCAL_ENV_PARAMS.get('DB_HOST'),
    'DATABASE': os.environ.get('DATABASE') or _LOCAL_ENV_PARAMS.get('DATABASE'),
    'DB_PORT': os.environ.get('DB_PORT') or _LOCAL_ENV_PARAMS.get('DB_PORT'),
    'DB_DIALECT': os.environ.get('DB_DIALECT') or _LOCAL_ENV_PARAMS.get('DB_DIALECT')
} # type: ignore

REQUIRED_DB_KEYS = ['DB_USER', 'DB_PASSWORD', 'DB_HOST', 'DATABASE', 'DB_PORT', 'DB_DIALECT']
for key in REQUIRED_DB_KEYS:
    if DB_PARAMETERS.get(key) is None or DB_PARAMETERS.get(key) == '':
        raise EnvironmentError(
            f'''Missing or empty required database environment variable: "{
            key}". Ensure it\'s set in os.environ or in your .env file.'''
        )

Base: DeclarativeMeta = declarative_base()

def get_database_engine(db_dialect: str) -> Engine:
    '''
        Creates and returns a generic SQLAlchemy database engine.

        Args:
        db_dialect (str): The database dialect (e.g., 'mysql+pymysql',
        'postgresql+psycopg2').

        Returns:
        sqlalchemy.engine.base.Engine: The configured database engine.
    '''
    try:
        url_database = URL.create(
            db_dialect,
            username = DB_PARAMETERS['DB_USER'],
            password = DB_PARAMETERS['DB_PASSWORD'],
            host = DB_PARAMETERS['DB_HOST'],
            database = DB_PARAMETERS['DATABASE'],
            port = int(DB_PARAMETERS['DB_PORT'])
        )
        return create_engine(
            url_database,
            pool_pre_ping = True,
            pool_size = 10,
            max_overflow = 20,
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


def get_db_session(engine: Engine) -> Callable:
    '''
        Returns a generator function that provides a database session.

        Args:
        engine (sqlalchemy.engine.base.Engine): The database engine to use.

        Returns:
        Callable: A generator function to obtain a DB session.
    '''
    session_factory = sessionmaker(autocommit = False, autoflush = False, bind = engine)

    def _get_db() -> Generator[Session, None, None]:
        '''
            Obtains and manages the connection to the database.
        '''
        db: Session = session_factory()
        try:
            yield db
        finally:
            db.close()
    return _get_db

DATABASE_DIALECT: str = DB_PARAMETERS['DB_DIALECT']
ENGINE: Engine = get_database_engine(DATABASE_DIALECT)
GET_DB_DEPENDENCY: Callable = get_db_session(ENGINE)
