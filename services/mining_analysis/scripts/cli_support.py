'''
    Shared scaffolding for the maintenance scripts.

    Both scripts open a database session, run their job and have to drain the
    session generator afterwards, and both refuse to start when the source file
    is missing. That was written twice, in two slightly different shapes; here
    it is written once, so a fix to the session handling lands in both.
'''
import sys
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Iterator

from sqlalchemy.orm import Session

from services.db_connection import ENGINE, get_db_session
from services.logger_config import custom_logger as logger


@contextmanager
def database_session() -> Iterator[Session]:
    '''
        Yields a database session and closes it afterwards.

        The session factory is a generator dependency, the same one FastAPI
        consumes, so it has to be advanced once more for its teardown to run.
        Wrapping that in a context manager keeps the detail out of every script.

        Yields:
            Session: An open session, closed when the block ends.
    '''
    session_factory = get_db_session(ENGINE)
    db_gen = session_factory()
    try:
        session = next(db_gen)
    except StopIteration as error:
        # The factory always yields once; if it did not, the database is
        # unreachable and the script must say so instead of failing later.
        raise RuntimeError('The session factory produced no session.') from error

    try:
        yield session
    finally:
        # Advancing the generator once more runs its teardown; it then stops,
        # which is the expected end and not an error.
        with suppress(StopIteration):
            next(db_gen)


def report(message: str) -> None:
    '''
        Sends one line to both the log and the console.

        Scripts are run by hand and their output is also the record of what was
        done, so every progress line goes to the two places.

        Args:
            message (str): Line to report.
    '''
    logger.info(message)
    print(message)


def source_is_missing(source: Path) -> bool:
    '''
        Reports whether the input file is absent, logging and printing it.

        Scripts are run by hand, so the message goes to stderr as well as to the
        log: whoever typed the command needs to see why nothing happened.

        Args:
            source (Path): File the script was asked to read.

        Returns:
            bool: True when the file does not exist.
    '''
    if source.exists():
        return False
    message = f'Source file not found: {source}'
    logger.error(message)
    print(message, file = sys.stderr)
    return True
