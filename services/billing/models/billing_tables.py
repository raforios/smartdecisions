'''
    Billing: the PostgreSQL tables, in BILLING's own database.

    The same eight sets the DynamoDB tables held, with the shop (`owner`) in
    every primary key: a query without it cannot even name a row. What a
    note carries inside (its lines with the lots each unit left, its payment
    parts, its invoice, its credit notes) stays a JSON document for now, as
    it was; the stock card (kárdex) will give the lines their own table.

    Money is stored exact (NUMERIC) and read as float, as the services use it.
    Times are stored with their zone.

    | Table          | Primary key                       |
    |----------------|-----------------------------------|
    | products       | owner, sku                        |
    | lots           | owner, sku, lot_id                |
    | sales          | owner, sale_id                    |
    | purchases      | owner, purchase_id                |
    | settings       | owner, setting_key                |
    | cash_sessions  | owner, session_id                 |
    | cash_movements | owner, session_id, movement_id    |
    | customers      | owner, document                   |
    | parameters     | name (the service's own values)   |
'''
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import CreateIndex, CreateTable

from core.db_connection import Base

OWNER_LENGTH = 120


def _money() -> Numeric:
    '''Exact in the database, float in Python, as the services use money.'''
    return Numeric(14, 4, asdecimal = False)


def _document() -> JSON:
    '''A nested document: JSONB in PostgreSQL (indexable), JSON in the tests.'''
    return JSON().with_variant(postgresql.JSONB(), 'postgresql')


def _quantity() -> Numeric:
    '''Units, which a fractioned sale (a blister of a box) makes non-integer.'''
    return Numeric(14, 3, asdecimal = False)


class ProductRow(Base):  # pylint: disable=too-few-public-methods
    '''A SKU in one shop's catalogue.'''
    __tablename__ = 'products'
    owner: Mapped[str] = mapped_column(String(OWNER_LENGTH), primary_key = True)
    sku: Mapped[str] = mapped_column(String(40), primary_key = True)
    description: Mapped[str] = mapped_column(String(200))
    laboratory: Mapped[str] = mapped_column(String(120))
    category: Mapped[str | None] = mapped_column(String(80))
    unit: Mapped[str] = mapped_column(String(20), default = 'UNIT')
    barcode: Mapped[str | None] = mapped_column(String(60))
    min_stock: Mapped[float] = mapped_column(_quantity(), default = 0)
    suggested_price: Mapped[float | None] = mapped_column(_money())
    requires_prescription: Mapped[bool] = mapped_column(Boolean, default = False)
    is_active: Mapped[bool] = mapped_column(Boolean, default = True)
    sin_activity_code: Mapped[str | None] = mapped_column(String(20))
    sin_product_code: Mapped[str | None] = mapped_column(String(20))
    sin_unit_code: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone = True))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone = True))


class LotRow(Base):  # pylint: disable=too-few-public-methods
    '''One batch of one SKU, with the cost it came in at and its sale price.'''
    __tablename__ = 'lots'
    owner: Mapped[str] = mapped_column(String(OWNER_LENGTH), primary_key = True)
    sku: Mapped[str] = mapped_column(String(40), primary_key = True)
    lot_id: Mapped[str] = mapped_column(String(60), primary_key = True)
    unit_cost: Mapped[float] = mapped_column(_money())
    sale_price: Mapped[float] = mapped_column(_money())
    quantity_received: Mapped[float] = mapped_column(_quantity())
    quantity_remaining: Mapped[float] = mapped_column(_quantity())
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone = True))
    lot_code: Mapped[str | None] = mapped_column(String(60))
    expiry_date: Mapped[date | None] = mapped_column(Date)
    purchase_id: Mapped[str | None] = mapped_column(String(60))


class SaleRow(Base):  # pylint: disable=too-few-public-methods
    '''A sale note, with its lines and their allocations to lots.'''
    __tablename__ = 'sales'
    __table_args__ = (Index('ix_sales_owner_created', 'owner', 'created_at'),)
    owner: Mapped[str] = mapped_column(String(OWNER_LENGTH), primary_key = True)
    sale_id: Mapped[str] = mapped_column(String(60), primary_key = True)
    number: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20))
    payment_method: Mapped[str] = mapped_column(String(30))
    lines: Mapped[list[dict[str, Any]]] = mapped_column(_document())
    subtotal: Mapped[float] = mapped_column(_money())
    discount: Mapped[float] = mapped_column(_money())
    total: Mapped[float] = mapped_column(_money())
    cost: Mapped[float] = mapped_column(_money())
    created_by: Mapped[str] = mapped_column(String(OWNER_LENGTH))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone = True))
    buyer: Mapped[dict[str, Any]] = mapped_column(_document(), default = dict)
    notes: Mapped[str | None] = mapped_column(Text)
    card_number: Mapped[str | None] = mapped_column(String(20))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone = True))
    cancelled_by: Mapped[str | None] = mapped_column(String(OWNER_LENGTH))
    cash_session_id: Mapped[str | None] = mapped_column(String(60))
    invoice: Mapped[dict[str, Any] | None] = mapped_column(_document())
    invoice_xml: Mapped[str | None] = mapped_column(Text)
    payments: Mapped[list[dict[str, Any]]] = mapped_column(_document(), default = list)
    credit_notes: Mapped[list[dict[str, Any]]] = mapped_column(_document(), default = list)


class PurchaseRow(Base):  # pylint: disable=too-few-public-methods
    '''A purchase note: what a supplier delivered and the lots it created.'''
    __tablename__ = 'purchases'
    __table_args__ = (Index('ix_purchases_owner_created', 'owner', 'created_at'),)
    owner: Mapped[str] = mapped_column(String(OWNER_LENGTH), primary_key = True)
    purchase_id: Mapped[str] = mapped_column(String(60), primary_key = True)
    number: Mapped[str] = mapped_column(String(40))
    supplier_name: Mapped[str] = mapped_column(String(200))
    lines: Mapped[list[dict[str, Any]]] = mapped_column(_document())
    total_cost: Mapped[float] = mapped_column(_money())
    created_by: Mapped[str] = mapped_column(String(OWNER_LENGTH))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone = True))
    supplier_document: Mapped[str | None] = mapped_column(String(40))
    invoice_number: Mapped[str | None] = mapped_column(String(40))
    invoice_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)


class SettingRow(Base):  # pylint: disable=too-few-public-methods
    '''
        One per-shop setting: the shop's configuration, a document counter,
        the SIN's codes, a contingency. The key says which; the value is its
        document, as it was in DynamoDB.
    '''
    __tablename__ = 'settings'
    owner: Mapped[str] = mapped_column(String(OWNER_LENGTH), primary_key = True)
    setting_key: Mapped[str] = mapped_column(String(120), primary_key = True)
    value: Mapped[dict[str, Any]] = mapped_column(_document(), default = dict)


class CashSessionRow(Base):  # pylint: disable=too-few-public-methods
    '''A till: one user's shift, for one day.'''
    __tablename__ = 'cash_sessions'
    __table_args__ = (Index('ix_cash_sessions_owner_day', 'owner', 'business_day'),)
    owner: Mapped[str] = mapped_column(String(OWNER_LENGTH), primary_key = True)
    session_id: Mapped[str] = mapped_column(String(60), primary_key = True)
    user_email: Mapped[str] = mapped_column(String(OWNER_LENGTH))
    status: Mapped[str] = mapped_column(String(20))
    business_day: Mapped[date] = mapped_column(Date)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone = True))
    opening_cash: Mapped[float] = mapped_column(_money())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone = True))
    closed_by: Mapped[str | None] = mapped_column(String(OWNER_LENGTH))
    counted_cash: Mapped[float | None] = mapped_column(_money())
    expected_cash: Mapped[float | None] = mapped_column(_money())
    difference: Mapped[float | None] = mapped_column(_money())
    note: Mapped[str | None] = mapped_column(Text)


class CashMovementRow(Base):  # pylint: disable=too-few-public-methods
    '''Cash that left a till; never deleted, only cancelled.'''
    __tablename__ = 'cash_movements'
    owner: Mapped[str] = mapped_column(String(OWNER_LENGTH), primary_key = True)
    session_id: Mapped[str] = mapped_column(String(60), primary_key = True)
    movement_id: Mapped[str] = mapped_column(String(60), primary_key = True)
    expense_type: Mapped[str] = mapped_column(String(30))
    amount: Mapped[float] = mapped_column(_money())
    concept: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20))
    created_by: Mapped[str] = mapped_column(String(OWNER_LENGTH))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone = True))
    purchase_id: Mapped[str | None] = mapped_column(String(60))
    cancelled_by: Mapped[str | None] = mapped_column(String(OWNER_LENGTH))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone = True))


class CustomerRow(Base):  # pylint: disable=too-few-public-methods
    '''A buyer the shop invoiced, by its NIT or CI.'''
    __tablename__ = 'customers'
    owner: Mapped[str] = mapped_column(String(OWNER_LENGTH), primary_key = True)
    document: Mapped[str] = mapped_column(String(40), primary_key = True)
    name: Mapped[str | None] = mapped_column(String(200))
    document_type: Mapped[int | None] = mapped_column(Integer)
    email: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone = True))
    created_by: Mapped[str | None] = mapped_column(String(OWNER_LENGTH))
    last_invoiced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone = True))


class ParameterRow(Base):  # pylint: disable=too-few-public-methods
    '''
        One of BILLING's own business values (docs/parametros.md), the same
        for every shop; what changes per shop lives in `settings`.
    '''
    __tablename__ = 'parameters'
    name: Mapped[str] = mapped_column(String(120), primary_key = True)
    value: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)


# BILLING's tables, in the order the schema file creates them. The metadata
# is shared with anything else built on Base, so the list is explicit.
TABLES = [row.__table__ for row in (
    ProductRow, LotRow, SaleRow, PurchaseRow, SettingRow, CashSessionRow,
    CashMovementRow, CustomerRow, ParameterRow
)]

SCHEMA_HEADER = (
    '-- BILLING: el esquema de su base PostgreSQL, generado de models/billing_tables.py\n'
    '-- con schema_sql(). Se aplica conectado como el usuario billing; sin Alembic.\n'
)


def schema_sql() -> str:
    '''
        The PostgreSQL DDL of these tables, as models/billing_schema.sql holds
        it. A test compares the two, so the file applied to the database never
        drifts from the models the service queries.

        Returns:
            str: CREATE TABLE and CREATE INDEX statements, in dependency order.
    '''
    dialect = postgresql.dialect()
    statements = [SCHEMA_HEADER]
    for table in TABLES:
        statements.append(f'{str(CreateTable(table).compile(dialect = dialect)).strip()};')
        statements.extend(f'{str(CreateIndex(index).compile(dialect = dialect)).strip()};'
                          for index in sorted(table.indexes, key = lambda one: one.name))
    return '\n\n'.join(statements) + '\n'
