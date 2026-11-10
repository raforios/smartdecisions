'''
    BILLING's data access on PostgreSQL.

    The services keep working with the records they always had: dictionaries
    keyed by the shop (`owner`) and a sort key (the SKU, the sale id that
    starts with its time, "sku#lot_id" for a lot, "session#movement" for a
    till movement, the setting key). This module turns those records into
    rows and back, so the business code only changes the connection it
    passes: a database session instead of the DynamoDB resource.

    Rules it keeps:

        - The owner is part of every query.
        - Times travel as ISO strings, as before, and are stored with their
          zone; days are stored as dates.
        - A field the table does not have is rejected, never dropped.
        - Nothing here commits: the controller commits once per operation, so
          a sale, its lots and its till are saved together or not at all.
'''
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session

from core.logger_config import custom_logger as logger
from models.billing import (
    CASH_MOVEMENTS_TABLE,
    CASH_SESSIONS_TABLE,
    CUSTOMERS_TABLE,
    LOTS_TABLE,
    PRODUCTS_TABLE,
    PURCHASES_TABLE,
    SALES_TABLE,
    SETTINGS_TABLE
)
from models.billing_tables import (
    CashMovementRow,
    CashSessionRow,
    CustomerRow,
    LotRow,
    ProductRow,
    PurchaseRow,
    SaleRow,
    SettingRow
)

OWNER_KEY = 'owner'
# The settings value keeps everything a setting record carries but its keys.
SETTING_VALUE = 'value'


@dataclass(frozen = True)
class TableShape:
    '''
        How one table's records map to rows.

        `sort_key` is the record's own key as the services know it. When it is
        made of two columns (`parts`), the record carries the joined value and
        the row the columns; `virtual` says the joined value is not a column.
    '''
    model: type
    sort_key: str
    parts: tuple[str, ...] = ()
    document: bool = False

    @property
    def virtual(self) -> bool:
        '''Whether the sort key is the join of two columns.'''
        return bool(self.parts)


SHAPES: dict[str, TableShape] = {
    PRODUCTS_TABLE: TableShape(ProductRow, 'sku'),
    LOTS_TABLE: TableShape(LotRow, 'lot_key', ('sku', 'lot_id')),
    SALES_TABLE: TableShape(SaleRow, 'sale_id'),
    PURCHASES_TABLE: TableShape(PurchaseRow, 'purchase_id'),
    SETTINGS_TABLE: TableShape(SettingRow, 'setting_key', document = True),
    CASH_SESSIONS_TABLE: TableShape(CashSessionRow, 'session_id'),
    CASH_MOVEMENTS_TABLE: TableShape(CashMovementRow, 'movement_key',
                                     ('session_id', 'movement_id')),
    CUSTOMERS_TABLE: TableShape(CustomerRow, 'document')
}


@dataclass
class SortBounds:
    '''
        How a read narrows the sort key of one owner's records: a prefix, or
        a range (`from`, `to`, either may be missing).
    '''
    sort_key: str
    begins_with: str | None = None
    between: dict[str, str] = field(default_factory = dict)


def _shape(table: str) -> TableShape:
    '''The shape of a table, by the name the services use.'''
    return SHAPES[table]


def _to_column(
    column: Any,
    value: Any
) -> Any:
    '''An ISO string becomes the date or time its column stores.'''
    if value is None or not isinstance(value, str):
        return value
    if isinstance(column.type, DateTime):
        return datetime.fromisoformat(value)
    if isinstance(column.type, Date):
        return date.fromisoformat(value[:10])
    return value


def _from_column(value: Any) -> Any:
    '''A stored date or time back to the ISO string the services use.'''
    if isinstance(value, datetime):
        return value.isoformat(timespec = 'seconds')
    if isinstance(value, date):
        return value.isoformat()
    return value


def to_row(
    table: str,
    record: dict[str, Any]
) -> Any:
    '''
        A record as a row of its table.

        Args:
            table (str): The table, by the name the services use.
            record (dict[str, Any]): The record, with its owner and sort key.

        Returns:
            Any: The model instance, not yet added to a session.

        Raises:
            ValueError: The record carries a field the table does not have.
    '''
    shape = _shape(table)
    fields = {key: value for key, value in record.items() if value is not None}
    if shape.document:
        keys = {OWNER_KEY: fields.pop(OWNER_KEY), shape.sort_key: fields.pop(shape.sort_key)}
        return shape.model(**keys, value = fields)
    if shape.virtual:
        joined = fields.pop(shape.sort_key, None)
        if joined is not None and not all(part in fields for part in shape.parts):
            fields.update(dict(zip(shape.parts, joined.split('#', 1))))
    columns = shape.model.__table__.columns
    unknown = set(fields) - set(columns.keys())
    if unknown:
        raise ValueError(f'{table} has no column for {sorted(unknown)}')
    return shape.model(**{key: _to_column(columns[key], value) for key, value in fields.items()})


def to_record(
    table: str,
    row: Any
) -> dict[str, Any]:
    '''
        A row as the record the services know, with its sort key.

        Args:
            table (str): The table, by the name the services use.
            row (Any): The model instance.

        Returns:
            dict[str, Any]: The record; empty columns are left out, as an
                absent attribute was in DynamoDB.
    '''
    shape = _shape(table)
    if shape.document:
        return {OWNER_KEY: row.owner, shape.sort_key: getattr(row, shape.sort_key),
                **(row.value or {})}
    record = {column: _from_column(getattr(row, column))
              for column in shape.model.__table__.columns.keys()
              if getattr(row, column) is not None}
    if shape.virtual:
        record[shape.sort_key] = '#'.join(str(record[part]) for part in shape.parts)
    return record


def _key_filter(
    shape: TableShape,
    sort_value: str
) -> dict[str, Any]:
    '''The columns and values that name one record of an owner.'''
    if shape.virtual:
        return dict(zip(shape.parts, sort_value.split('#', 1)))
    return {shape.sort_key: sort_value}


def get_item(
    db: Session,
    table: str,
    owner: str,
    sort_value: str,
    lock: bool = False
) -> dict[str, Any] | None:
    '''
        One record of an owner, or None.

        Args:
            db (Session): The database session.
            table (str): The table, by the name the services use.
            owner (str): The shop.
            sort_value (str): The record's own key.
            lock (bool): Hold the row until the transaction ends, so whoever
                reads it next waits for this change (a counter, a lot).

        Returns:
            dict[str, Any] | None: The record.
    '''
    shape = _shape(table)
    query = select(shape.model).filter_by(owner = owner, **_key_filter(shape, sort_value))
    if lock:
        query = query.with_for_update()
    row = db.execute(query).scalar_one_or_none()
    return to_record(table, row) if row is not None else None


def write_item(
    db: Session,
    table: str,
    record: dict[str, Any]
) -> None:
    '''
        Stores a record whole: it replaces whatever the owner had under that key.

        Args:
            db (Session): The database session.
            table (str): The table, by the name the services use.
            record (dict[str, Any]): The record, with its owner and sort key.
    '''
    shape = _shape(table)
    row = to_row(table, record)
    keys = {name: getattr(row, name)
            for name in (shape.parts or (shape.sort_key,))}
    existing = db.execute(select(shape.model).filter_by(owner = row.owner, **keys)
                          ).scalar_one_or_none()
    if existing is not None:
        for column in shape.model.__table__.columns.keys():
            setattr(existing, column, getattr(row, column))
    else:
        db.add(row)
    db.flush()


def delete_item(
    db: Session,
    table: str,
    owner: str,
    sort_value: str
) -> None:
    '''
        Removes one record of an owner, if it is there.

        Args:
            db (Session): The database session.
            table (str): The table, by the name the services use.
            owner (str): The shop.
            sort_value (str): The record's own key.
    '''
    shape = _shape(table)
    row = db.execute(select(shape.model).filter_by(
        owner = owner, **_key_filter(shape, sort_value))).scalar_one_or_none()
    if row is not None:
        db.delete(row)
        db.flush()


def read_partition(
    db: Session,
    table: str,
    owner: str,
    bounds: SortBounds | None = None,
    descending: bool = False
) -> list[dict[str, Any]]:
    '''
        Every record of one owner, optionally narrowed on the sort key, in
        sort-key order.

        Args:
            db (Session): The database session.
            table (str): The table, by the name the services use.
            owner (str): The shop.
            bounds (SortBounds | None): A prefix or a range of the sort key.
            descending (bool): Last first when True.

        Returns:
            list[dict[str, Any]]: The records.
    '''
    shape = _shape(table)
    model = shape.model
    query = select(model).filter_by(owner = owner)
    if bounds and bounds.begins_with:
        query = query.where(_sort_column(shape).startswith(bounds.begins_with, autoescape = True))
    if bounds and bounds.between:
        column = _sort_column(shape)
        if bounds.between.get('from'):
            query = query.where(column >= bounds.between['from'])
        if bounds.between.get('to'):
            query = query.where(column <= bounds.between['to'])
    order = _sort_column(shape)
    query = query.order_by(order.desc() if descending else order)
    records = [to_record(table, row) for row in db.execute(query).scalars()]
    message = f'Read on {table} returned {len(records)} record(s).'
    logger.info(message)
    return records


def _sort_column(shape: TableShape) -> Any:
    '''The sort key as a column expression, joined when it is two columns.'''
    if not shape.virtual:
        return getattr(shape.model, shape.sort_key)
    first, second = (getattr(shape.model, part) for part in shape.parts)
    return first + '#' + second


def ensure_item(
    db: Session,
    table: str,
    record: dict[str, Any]
) -> None:
    '''
        Creates a record only if the owner has none under that key, safely
        against a second till doing the same at the same moment.

        Args:
            db (Session): The database session.
            table (str): The table, by the name the services use.
            record (dict[str, Any]): The record to create when missing.
    '''
    row = to_row(table, record)
    model = _shape(table).model
    values = {column: getattr(row, column) for column in model.__table__.columns.keys()
              if getattr(row, column) is not None}
    dialect = postgresql if db.get_bind().dialect.name == 'postgresql' else sqlite
    db.execute(dialect.insert(model).values(**values).on_conflict_do_nothing())
    db.flush()


def take_counter(
    db: Session,
    owner: str,
    counter_key: str
) -> int:
    '''
        Takes the next value of one counter: two tills at the same second
        never get the same number, because the counter row stays locked until
        the transaction that took it ends.

        Args:
            db (Session): The database session.
            owner (str): The shop.
            counter_key (str): Which counter.

        Returns:
            int: The value taken, 1 the first time.
    '''
    ensure_item(db, SETTINGS_TABLE, {OWNER_KEY: owner, 'setting_key': counter_key,
                                     'last_number': 0})
    row = db.execute(select(SettingRow).filter_by(owner = owner, setting_key = counter_key)
                     .with_for_update()).scalar_one()
    taken = int((row.value or {}).get('last_number', 0)) + 1
    row.value = {**(row.value or {}), 'last_number': taken}
    db.flush()
    return taken


def add_to_lot(
    db: Session,
    owner: str,
    lot_key_value: str,
    units: float
) -> bool:
    '''
        Moves units in (positive) or out (negative) of one lot, only while it
        still holds what is taken out. One UPDATE with the condition inside,
        so two tills cannot both sell the last box.

        Args:
            db (Session): The database session.
            owner (str): The shop.
            lot_key_value (str): "sku#lot_id".
            units (float): Units to add, negative to take.

        Returns:
            bool: False when the lot is gone or no longer holds the units.
    '''
    sku, lot_id = lot_key_value.split('#', 1)
    statement = (LotRow.__table__.update()
                 .where(LotRow.owner == owner, LotRow.sku == sku, LotRow.lot_id == lot_id)
                 .values(quantity_remaining = LotRow.quantity_remaining + units))
    if units < 0:
        statement = statement.where(LotRow.quantity_remaining >= -units)
    return db.execute(statement).rowcount == 1
