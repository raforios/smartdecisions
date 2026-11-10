'''
    The SQL boilerplate: the engine the tests run on, and the CRUD that keeps
    the owner in every query.
'''
import pytest
from pydantic import BaseModel
from sqlalchemy import String, UniqueConstraint
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column

from core import crud
from core.db_connection import ENGINE, GET_DB_DEPENDENCY, Base
from core.exceptions import RegisterNotFoundError


class _Note(Base):  # pylint: disable=too-few-public-methods
    '''A table only these tests use.'''
    __tablename__ = 'test_core_notes'
    __table_args__ = (UniqueConstraint('owner', 'code'),)
    id: Mapped[int] = mapped_column(primary_key = True)
    owner: Mapped[str] = mapped_column(String(120))
    code: Mapped[str] = mapped_column(String(40))
    text: Mapped[str] = mapped_column(String(200), default = '')


class _NoteIn(BaseModel):
    '''What a note is created or changed with.'''
    code: str | None = None
    text: str | None = None


@pytest.fixture(name = 'db')
def fixture_db():
    '''A session on a fresh table, closed and dropped after the test.'''
    _Note.__table__.create(ENGINE, checkfirst = True)
    session_source = GET_DB_DEPENDENCY()
    session = next(session_source, None)
    yield session
    session.rollback()
    session_source.close()
    _Note.__table__.drop(ENGINE)


def test_the_tests_run_on_sqlite_in_memory():
    '''No database server and no network during the tests.'''
    assert ENGINE.dialect.name == 'sqlite'


def test_a_record_is_found_only_by_its_owner(db):
    '''Another company's record answers exactly like a missing one.'''
    crud.create_record(db, _Note, _NoteIn(code = 'A1', text = 'mine'), {'owner': 'shop-a'})
    assert crud.get_record(db, _Note, 'shop-a', code = 'A1').text == 'mine'
    assert crud.find_record(db, _Note, 'shop-b', code = 'A1') is None
    with pytest.raises(RegisterNotFoundError):
        crud.get_record(db, _Note, 'shop-b', code = 'A1')


def test_a_duplicate_key_goes_up_as_an_integrity_error(db):
    '''The controller gives the duplicate its business meaning.'''
    crud.create_record(db, _Note, _NoteIn(code = 'A1'), {'owner': 'shop-a'})
    with pytest.raises(IntegrityError):
        crud.create_record(db, _Note, _NoteIn(code = 'A1'), {'owner': 'shop-a'})


def test_update_changes_only_what_is_set_and_delete_removes(db):
    '''Unset fields stay; a deleted record is gone for its owner.'''
    note = crud.create_record(db, _Note, _NoteIn(code = 'A1', text = 'old'), {'owner': 'shop-a'})
    crud.update_record(db, note, _NoteIn(text = 'new'))
    assert (note.code, note.text) == ('A1', 'new')
    crud.delete_record(db, _Note, 'shop-a', code = 'A1')
    assert crud.find_record(db, _Note, 'shop-a', code = 'A1') is None


def test_a_page_holds_only_the_owners_records_in_order(db):
    '''Pagination never mixes companies.'''
    for code in ('C', 'A', 'B'):
        crud.create_record(db, _Note, _NoteIn(code = code), {'owner': 'shop-a'})
    crud.create_record(db, _Note, _NoteIn(code = 'Z'), {'owner': 'shop-b'})
    page = crud.get_all_records_paginated(db, _Note, 'shop-a', (1, 5), _Note.code)
    assert [note.code for note in page] == ['B', 'C']
