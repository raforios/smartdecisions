'''
    BILLING's PostgreSQL tables: the schema file applied to the database is
    the one the models describe, and every table keeps the shop in its key.
'''
from pathlib import Path

from sqlalchemy import inspect

from core.db_connection import ENGINE, Base
from models.billing_tables import TABLES, schema_sql

SCHEMA_FILE = Path(__file__).resolve().parents[1] / 'models' / 'billing_schema.sql'


def test_the_schema_file_is_the_one_the_models_describe():
    '''Regenerate it with schema_sql() whenever a model changes.'''
    assert SCHEMA_FILE.read_text() == schema_sql()


def test_every_shop_table_has_the_owner_in_its_primary_key():
    '''A row of one shop cannot even be named without the shop.'''
    shop_tables = [table for table in TABLES if table.name != 'parameters']
    assert len(shop_tables) == 8
    for table in shop_tables:
        assert 'owner' in [column.name for column in table.primary_key.columns], table.name


def test_the_tables_are_created_on_the_test_database():
    '''The models build on SQLite as they do on PostgreSQL.'''
    Base.metadata.create_all(ENGINE, tables = TABLES)
    created = set(inspect(ENGINE).get_table_names())
    assert {'products', 'lots', 'sales', 'purchases', 'settings', 'cash_sessions',
            'cash_movements', 'customers', 'parameters'} <= created
