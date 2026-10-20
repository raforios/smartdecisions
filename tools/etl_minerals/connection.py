'''
    Connections of the minerals ETL: the local MySQL it loads and the DynamoDB
    tables it publishes to.

    The tool owns them (Rafael, 19-oct-2026): it reads its own `.env`, next to
    this file, and imports nothing from `services/mining_analysis`. The API can
    change its persistence without the fortnightly load noticing, and the other
    way round.
'''
from collections.abc import Iterator
import os
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import boto3
from boto3.resources.base import ServiceResource
from dotenv import load_dotenv
from sqlalchemy import URL, create_engine
from sqlalchemy.orm import Session, sessionmaker

ENV_PATH = Path(__file__).resolve().parent / '.env'
REQUIRED = (
    'DB_DIALECT', 'DB_USER', 'DB_PASSWORD', 'DB_HOST', 'DB_PORT', 'DATABASE',
    'TARGET_TIMEZONE', 'AWS_PROFILE', 'AWS_REGION',
    'DYNAMODB_TABLE_NAME_MINERALS', 'DYNAMODB_TABLE_NAME_MINING_PRICES',
)


def environment() -> dict[str, str]:
    '''
        Reads the tool's `.env` and refuses to go on when a value is missing.

        Returns:
            dict[str, str]: Every required value.
    '''
    load_dotenv(ENV_PATH)
    missing = [name for name in REQUIRED if not os.getenv(name)]
    if missing:
        raise RuntimeError(f'Missing in {ENV_PATH}: {", ".join(missing)}.')
    return {name: os.environ[name] for name in REQUIRED}


def now() -> datetime:
    '''
        The current time in the configured zone, as the API stamps its rows.

        Returns:
            datetime: Aware datetime.
    '''
    return datetime.now(tz = ZoneInfo(environment()['TARGET_TIMEZONE']))


@contextmanager
def database_session() -> Iterator[Session]:
    '''
        Yields a session on the local MySQL and closes it afterwards.

        Yields:
            Session: An open session.
    '''
    env = environment()
    engine = create_engine(URL.create(
        env['DB_DIALECT'],
        username = env['DB_USER'],
        password = env['DB_PASSWORD'],
        host = env['DB_HOST'],
        port = int(env['DB_PORT']),
        database = env['DATABASE']
    ), pool_pre_ping = True)
    session = sessionmaker(bind = engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def dynamodb() -> ServiceResource:
    '''
        The DynamoDB resource of the configured profile and region.

        Returns:
            ServiceResource: boto3 resource.
    '''
    env = environment()
    return boto3.Session(profile_name = env['AWS_PROFILE'],
                         region_name = env['AWS_REGION']).resource('dynamodb')


def report(message: str) -> None:
    '''
        Prints one progress line: run by hand, the output is the record.

        Args:
            message (str): Line to report.
    '''
    print(message)


def source_is_missing(source: Path) -> bool:
    '''
        Reports whether the input file is absent.

        Args:
            source (Path): File the tool was asked to read.

        Returns:
            bool: True when the file does not exist.
    '''
    if source.exists():
        return False
    print(f'Source file not found: {source}', file = sys.stderr)
    return True
