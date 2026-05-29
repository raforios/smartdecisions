'''
    Supplies Models.

    Captures the full inventory domain:
        - Catalog: categories, units, items.
        - Replenishments: orders against an external purchasing system and
          their physical receptions.
        - Requests: end-user requests for materials, with full state history.
        - Kardex: append-only ledger of stock movements.
        - System parameters: tunable values (e.g. default replenishment qty).
'''
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from services.db_connection import Base
from services.utils import get_current_time_gmt
from schemas.enums import (
    MovementTypeEnum,
    ReferenceTypeEnum,
    ReplenishmentStatusEnum,
    RequestStatusEnum,
)


class Category(Base):  # pylint: disable=too-few-public-methods
    '''
        Supply category (e.g. cleaning, office, technical).
    '''
    __tablename__ = 't_supplies_category'

    id = Column(Integer, primary_key = True, index = True)
    code = Column(String(50), nullable = False, unique = True, index = True)
    name = Column(String(150), nullable = False)
    description = Column(String(500), nullable = True)
    is_active = Column(Boolean, nullable = False, default = True)
    created_at = Column(DateTime, nullable = False, default = get_current_time_gmt)

    items = relationship('Item', back_populates = 'category')


class Unit(Base):  # pylint: disable=too-few-public-methods
    '''
        Unit of measure (e.g. UND, BOX, KG).
    '''
    __tablename__ = 't_supplies_unit'

    id = Column(Integer, primary_key = True, index = True)
    code = Column(String(20), nullable = False, unique = True, index = True)
    name = Column(String(100), nullable = False)
    abbreviation = Column(String(10), nullable = False)
    is_active = Column(Boolean, nullable = False, default = True)
    created_at = Column(DateTime, nullable = False, default = get_current_time_gmt)

    items = relationship('Item', back_populates = 'unit')


class Item(Base):  # pylint: disable=too-few-public-methods
    '''
        Inventory item.

        current_stock is the materialized balance maintained by the kardex
        logic, kept in sync with t_supplies_kardex append-only ledger.
    '''
    __tablename__ = 't_supplies_item'

    id = Column(Integer, primary_key = True, index = True)
    code = Column(String(50), nullable = False, unique = True, index = True)
    name = Column(String(200), nullable = False)
    description = Column(String(500), nullable = True)
    category_id = Column(Integer, ForeignKey('t_supplies_category.id'),
                         nullable = False, index = True)
    unit_id = Column(Integer, ForeignKey('t_supplies_unit.id'),
                     nullable = False, index = True)
    min_stock = Column(Numeric(14, 4), nullable = False, default = 0)
    current_stock = Column(Numeric(14, 4), nullable = False, default = 0)
    default_replenishment_qty = Column(Numeric(14, 4), nullable = False, default = 0)
    is_active = Column(Boolean, nullable = False, default = True)
    created_at = Column(DateTime, nullable = False, default = get_current_time_gmt)
    updated_at = Column(DateTime, nullable = False, default = get_current_time_gmt,
                        onupdate = get_current_time_gmt)

    category = relationship('Category', back_populates = 'items')
    unit = relationship('Unit', back_populates = 'items')
    replenishments = relationship('Replenishment', back_populates = 'item')
    kardex_movements = relationship('KardexMovement', back_populates = 'item')


class Replenishment(Base):  # pylint: disable=too-few-public-methods
    '''
        Replenishment order header.

        Each row is independent even for the same item, so dates, suppliers,
        and batches can be traced back to a specific purchase event.
    '''
    __tablename__ = 't_supplies_replenishment'

    id = Column(Integer, primary_key = True, index = True)
    code = Column(String(50), nullable = False, unique = True, index = True)
    item_id = Column(Integer, ForeignKey('t_supplies_item.id'),
                     nullable = False, index = True)
    requested_qty = Column(Numeric(14, 4), nullable = False)
    received_qty = Column(Numeric(14, 4), nullable = False, default = 0)
    status = Column(
        Enum(ReplenishmentStatusEnum),
        nullable = False,
        default = ReplenishmentStatusEnum.REQUESTED,
        index = True,
    )
    supplier_hint = Column(String(200), nullable = True)
    notes = Column(Text, nullable = True)
    created_by = Column(String(150), nullable = False)
    created_at = Column(DateTime, nullable = False, default = get_current_time_gmt)
    completed_at = Column(DateTime, nullable = True)

    item = relationship('Item', back_populates = 'replenishments')
    receptions = relationship(
        'Reception',
        back_populates = 'replenishment',
        cascade = 'all, delete-orphan',
    )


class Reception(Base):  # pylint: disable=too-few-public-methods
    '''
        Physical reception of replenishment goods.

        Multiple receptions per replenishment are supported, each carrying
        its own batch, expiration, supplier, and invoice metadata.
    '''
    __tablename__ = 't_supplies_replenishment_reception'

    id = Column(Integer, primary_key = True, index = True)
    replenishment_id = Column(Integer, ForeignKey('t_supplies_replenishment.id'),
                              nullable = False, index = True)
    received_qty = Column(Numeric(14, 4), nullable = False)
    batch_code = Column(String(100), nullable = True)
    expiration_date = Column(Date, nullable = True)
    supplier_name = Column(String(200), nullable = False)
    invoice_number = Column(String(100), nullable = True)
    file_key = Column(String(500), nullable = True)
    notes = Column(Text, nullable = True)
    received_by = Column(String(150), nullable = False)
    received_at = Column(DateTime, nullable = False, default = get_current_time_gmt)

    replenishment = relationship('Replenishment', back_populates = 'receptions')


class Request(Base):  # pylint: disable=too-few-public-methods
    '''
        End-user request for supplies. Status transitions are validated in
        the service layer; the status_history relationship preserves the
        full audit trail.
    '''
    __tablename__ = 't_supplies_request'

    id = Column(Integer, primary_key = True, index = True)
    code = Column(String(50), nullable = False, unique = True, index = True)
    requester_email = Column(String(150), nullable = False, index = True)
    status = Column(
        Enum(RequestStatusEnum),
        nullable = False,
        default = RequestStatusEnum.CREATED,
        index = True,
    )
    notes = Column(Text, nullable = True)
    requested_at = Column(DateTime, nullable = False, default = get_current_time_gmt)
    processed_at = Column(DateTime, nullable = True)
    processed_by = Column(String(150), nullable = True)
    delivered_at = Column(DateTime, nullable = True)
    delivered_by = Column(String(150), nullable = True)
    closed_at = Column(DateTime, nullable = True)

    details = relationship(
        'RequestDetail',
        back_populates = 'request',
        cascade = 'all, delete-orphan',
    )
    status_history = relationship(
        'RequestStatusHistory',
        back_populates = 'request',
        cascade = 'all, delete-orphan',
        order_by = 'RequestStatusHistory.changed_at',
    )


class RequestDetail(Base):  # pylint: disable=too-few-public-methods
    '''
        Line item inside a supply request.
    '''
    __tablename__ = 't_supplies_request_detail'

    id = Column(Integer, primary_key = True, index = True)
    request_id = Column(Integer, ForeignKey('t_supplies_request.id'),
                        nullable = False, index = True)
    item_id = Column(Integer, ForeignKey('t_supplies_item.id'),
                     nullable = False, index = True)
    requested_qty = Column(Numeric(14, 4), nullable = False)
    delivered_qty = Column(Numeric(14, 4), nullable = False, default = 0)

    request = relationship('Request', back_populates = 'details')
    item = relationship('Item')

    __table_args__ = (UniqueConstraint('request_id', 'item_id'),)


class RequestStatusHistory(Base):  # pylint: disable=too-few-public-methods
    '''
        Append-only history of state transitions for a request.
    '''
    __tablename__ = 't_supplies_request_status_history'

    id = Column(Integer, primary_key = True, index = True)
    request_id = Column(Integer, ForeignKey('t_supplies_request.id'),
                        nullable = False, index = True)
    from_status = Column(Enum(RequestStatusEnum), nullable = True)
    to_status = Column(Enum(RequestStatusEnum), nullable = False)
    changed_by = Column(String(150), nullable = False)
    changed_at = Column(DateTime, nullable = False, default = get_current_time_gmt)
    reason = Column(Text, nullable = True)

    request = relationship('Request', back_populates = 'status_history')


class KardexMovement(Base):  # pylint: disable=too-few-public-methods
    '''
        Append-only stock ledger. Never updated or deleted; corrections are
        applied via additional ADJUSTMENT rows so the audit trail remains
        complete.
    '''
    __tablename__ = 't_supplies_kardex'

    id = Column(Integer, primary_key = True, index = True)
    item_id = Column(Integer, ForeignKey('t_supplies_item.id'),
                     nullable = False, index = True)
    movement_type = Column(Enum(MovementTypeEnum), nullable = False, index = True)
    reference_type = Column(Enum(ReferenceTypeEnum), nullable = False, index = True)
    reference_id = Column(Integer, nullable = True)
    quantity = Column(Numeric(14, 4), nullable = False)
    balance_before = Column(Numeric(14, 4), nullable = False)
    balance_after = Column(Numeric(14, 4), nullable = False)
    batch_code = Column(String(100), nullable = True)
    notes = Column(Text, nullable = True)
    created_by = Column(String(150), nullable = False)
    created_at = Column(DateTime, nullable = False, default = get_current_time_gmt, index = True)

    item = relationship('Item', back_populates = 'kardex_movements')


class SystemParameter(Base):  # pylint: disable=too-few-public-methods
    '''
        Tunable system-wide parameters (e.g. default replenishment buffer).
        Kept generic so new knobs can be added without schema changes.
    '''
    __tablename__ = 't_supplies_parameter'

    id = Column(Integer, primary_key = True, index = True)
    key = Column(String(100), nullable = False, unique = True, index = True)
    value = Column(String(500), nullable = False)
    description = Column(String(500), nullable = True)
    updated_by = Column(String(150), nullable = True)
    updated_at = Column(DateTime, nullable = False, default = get_current_time_gmt,
                        onupdate = get_current_time_gmt)
