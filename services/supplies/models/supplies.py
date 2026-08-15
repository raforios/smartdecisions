'''
    Supplies Models.

    Captures the full inventory domain:
        - Catalog: categories (accounting groups), units, items.
        - Suppliers: the registered vendors a Nota de Ingreso can point to.
        - Entries: warehouse intake documents (Nota de Ingreso) whose detail
          lines are the PEPS/FIFO cost layers consumed on delivery.
        - Requests: end-user requests for materials, with full state history.
        - Kardex: append-only, valued ledger of stock movements.
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
    EntryTypeEnum,
    MovementTypeEnum,
    ReferenceTypeEnum,
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
    # Holds the full article description (single descriptive text, no legacy
    # "old code"); the source catalog carries descriptions up to ~250 chars.
    name = Column(String(500), nullable = False)
    description = Column(String(500), nullable = True)
    category_id = Column(Integer, ForeignKey('t_supplies_category.id'),
                         nullable = False, index = True)
    unit_id = Column(Integer, ForeignKey('t_supplies_unit.id'),
                     nullable = False, index = True)
    min_stock = Column(Numeric(14, 4), nullable = False, default = 0)
    current_stock = Column(Numeric(14, 4), nullable = False, default = 0)
    # Units committed to open requests (CREATED / IN_PROCESS) but not yet
    # delivered. Held so two requests cannot promise the same physical units;
    # released when the request is rejected, cancelled, deleted or delivered.
    reserved_stock = Column(Numeric(14, 4), nullable = False, default = 0)
    default_replenishment_qty = Column(Numeric(14, 4), nullable = False, default = 0)
    is_active = Column(Boolean, nullable = False, default = True)
    created_at = Column(DateTime, nullable = False, default = get_current_time_gmt)
    updated_at = Column(DateTime, nullable = False, default = get_current_time_gmt,
                        onupdate = get_current_time_gmt)

    category = relationship('Category', back_populates = 'items')
    unit = relationship('Unit', back_populates = 'items')
    entry_details = relationship('EntryDetail', back_populates = 'item')
    kardex_movements = relationship('KardexMovement', back_populates = 'item')


class Supplier(Base):  # pylint: disable=too-few-public-methods
    '''
        Registered vendor a Nota de Ingreso can be issued against.

        Deactivation is soft (is_active) because entries keep pointing at the
        supplier that issued them; a vendor that stops working with the
        warehouse must disappear from the pickers without breaking history.
    '''
    __tablename__ = 't_supplies_supplier'

    id = Column(Integer, primary_key = True, index = True)
    name = Column(String(200), nullable = False, index = True)
    nit = Column(String(50), nullable = False, unique = True, index = True)
    contact_person = Column(String(200), nullable = False)
    address = Column(String(300), nullable = False)
    email = Column(String(150), nullable = True)
    phone = Column(String(50), nullable = False)
    is_active = Column(Boolean, nullable = False, default = True)
    created_at = Column(DateTime, nullable = False, default = get_current_time_gmt)
    updated_at = Column(DateTime, nullable = False, default = get_current_time_gmt,
                        onupdate = get_current_time_gmt)

    entries = relationship('Entry', back_populates = 'supplier_record')


class Entry(Base):  # pylint: disable=too-few-public-methods
    '''
        Warehouse entry document (Nota de Ingreso).

        Groups several items received under a single supplier / invoice /
        requirement event. Each detail line is an independent PEPS/FIFO cost
        layer, so the exact cost and source document of every unit in stock
        can always be reconstructed.
    '''
    __tablename__ = 't_supplies_entry'

    id = Column(Integer, primary_key = True, index = True)
    code = Column(String(50), nullable = False, unique = True, index = True)
    entry_type = Column(
        Enum(EntryTypeEnum),
        nullable = False,
        default = EntryTypeEnum.COMPRA,
        index = True,
    )
    supplier_id = Column(Integer, ForeignKey('t_supplies_supplier.id'),
                         nullable = True, index = True)
    # Denormalized supplier name captured when the note was issued: renaming a
    # supplier must not rewrite the documents already printed and signed.
    supplier = Column(String(200), nullable = True)
    requirement_no = Column(String(100), nullable = True)
    requirement_date = Column(Date, nullable = True)
    delivery_note = Column(String(100), nullable = True)
    delivery_note_date = Column(Date, nullable = True)
    invoice_no = Column(String(100), nullable = True)
    authorization = Column(String(100), nullable = True)
    invoice_date = Column(Date, nullable = True)
    observations = Column(Text, nullable = True)
    # Discount applies to the whole note; total = subtotal - discount.
    discount = Column(Numeric(14, 4), nullable = False, default = 0)
    subtotal = Column(Numeric(14, 4), nullable = False, default = 0)
    total = Column(Numeric(14, 4), nullable = False, default = 0)
    created_by = Column(String(150), nullable = False)
    created_at = Column(DateTime, nullable = False, default = get_current_time_gmt, index = True)

    details = relationship(
        'EntryDetail',
        back_populates = 'entry',
        cascade = 'all, delete-orphan',
        order_by = 'EntryDetail.id',
    )
    supplier_record = relationship('Supplier', back_populates = 'entries')


class EntryDetail(Base):  # pylint: disable=too-few-public-methods
    '''
        A single line of a Nota de Ingreso and, at the same time, a PEPS/FIFO
        cost layer.

        qty_remaining starts equal to qty_initial and is decremented as
        deliveries consume the layer oldest-first. When it reaches zero the
        layer is exhausted and consumption moves to the next entry.
    '''
    __tablename__ = 't_supplies_entry_detail'

    id = Column(Integer, primary_key = True, index = True)
    entry_id = Column(Integer, ForeignKey('t_supplies_entry.id'),
                      nullable = False, index = True)
    item_id = Column(Integer, ForeignKey('t_supplies_item.id'),
                     nullable = False, index = True)
    qty_initial = Column(Numeric(14, 4), nullable = False)
    qty_remaining = Column(Numeric(14, 4), nullable = False)
    unit_cost = Column(Numeric(14, 4), nullable = False)
    total_cost = Column(Numeric(14, 4), nullable = False)

    entry = relationship('Entry', back_populates = 'details')
    item = relationship('Item', back_populates = 'entry_details')


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
    # Printed on the SOLICITUD / ENTREGA forms, which are signed on paper and
    # need a person, a job title and a unit, not just a login address.
    requester_name = Column(String(200), nullable = True)
    requester_position = Column(String(200), nullable = True)
    requester_unit = Column(String(200), nullable = True)
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
    # PEPS/FIFO valuation: cost of this movement and the entry (lote) it came
    # from. For OUT rows these identify the exact cost layer consumed.
    unit_cost = Column(Numeric(14, 4), nullable = True)
    total_cost = Column(Numeric(14, 4), nullable = True)
    source_entry_id = Column(
        Integer, ForeignKey('t_supplies_entry.id'), nullable = True, index = True)
    source_entry_detail_id = Column(
        Integer, ForeignKey('t_supplies_entry_detail.id'), nullable = True)
    batch_code = Column(String(100), nullable = True)
    notes = Column(Text, nullable = True)
    created_by = Column(String(150), nullable = False)
    created_at = Column(DateTime, nullable = False, default = get_current_time_gmt, index = True)

    item = relationship('Item', back_populates = 'kardex_movements')
