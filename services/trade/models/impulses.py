'''
    Impulses Models
'''
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    ForeignKey,
    DateTime,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from models.products import AttendanceProductMixin
from services.db_connection import Base
from services.utils import get_current_time_gmt

class TradePromotion(Base):  # pylint: disable=too-few-public-methods
    '''
        Promotion Header model (Bandeo).
    '''
    __tablename__ = 't_trade_promotions'

    id = Column(Integer, primary_key = True, index = True)
    company_id = Column(Integer, nullable = False, index = True)

    name = Column(String(255), nullable = False)
    description = Column(Text, nullable = True)
    start_date = Column(DateTime, nullable = False)
    end_date = Column(DateTime, nullable = False)

    status = Column(String(20), default = 'ACTIVE', nullable = False)
    created_at = Column(DateTime, nullable = False, default = get_current_time_gmt)

    # Relationship to the Promotion Details (SKUs included)
    details = relationship(
        'TradePromotionDetail',
        back_populates = 'promotion',
        cascade = 'all, delete-orphan'
    )

    __table_args__ = (
        # Ensure the promotion name is unique per company
        UniqueConstraint(
            'company_id', 'name',
            name = 'uc_promotion_name_company'
        ),
    )

class TradePromotionDetail(Base):  # pylint: disable=too-few-public-methods
    '''
        Promotion Detail model.
    '''
    __tablename__ = 't_trade_promotion_details'

    id = Column(Integer, primary_key = True, index = True)

    # Relationship to the Promotion Header
    promotion_id = Column(
        Integer, ForeignKey('t_trade_promotions.id', ondelete = 'CASCADE'),
        nullable = False, index = True
    )
    promotion = relationship('TradePromotion', back_populates = 'details')

    # Relationship to the Product
    product_id = Column(
        Integer, ForeignKey('t_products.id', ondelete = 'RESTRICT'),
        nullable = False, index = True
    )
    product = relationship('Product')

    # Binaria 2026-07-08: quantity of this SKU that makes up one unit of the
    # promotion (e.g. 12 sausages per "san juanero" pack). Drives the planned
    # bandeo demand: qty_planned = promotion_quantity * sku_quantity.
    sku_quantity = Column(Integer, nullable = False, default = 1)

    created_at = Column(DateTime, nullable = False, default = get_current_time_gmt)

    __table_args__ = (
        # A product can only be in a promotion once
        UniqueConstraint(
            'promotion_id', 'product_id',
            name = 'uc_promotion_product'
        ),
    )

# --- B.1. IMPULSE ACTIVITIES MODELS ---

class ImpulseInventoryStart(Base, AttendanceProductMixin):  # pylint: disable=too-few-public-methods
    '''
        Records the initial inventory count at the start of a visit.

        iter5 (Binaria, 2026-06-20): unified storage for both Impulses and
        Replenishments inventory. The same physical stock is touched by
        both processes (Impulses move it, Replenishments restore it), so
        the table now carries batch + expiration + sala/almacén breakdown
        + client_company_id. Legacy `quantity` column kept nullable so
        existing callers that read it keep working; new code populates the
        new columns and derives `quantity = quantity_in_room + quantity_in_warehouse`.
    '''
    __tablename__ = 't_trade_impulse_inventory_start'

    id = Column(Integer, primary_key = True, index = True)

    # iter5: brand / client owner — same convention as t_trade_impulse_sales.
    client_company_id = Column(Integer, nullable = True, index = True)

    # iter5: traceability of incoming batches.
    batch_number = Column(String(50), nullable = True, index = True)
    expiration_date = Column(DateTime, nullable = True)

    # iter5: split count by physical location. Legacy `quantity` aggregates both.
    quantity_in_room = Column(Integer, nullable = False, default = 0)
    quantity_in_warehouse = Column(Integer, nullable = False, default = 0)
    quantity = Column(Integer, nullable = True)

    # Free-text notes captured by the operator during the count.
    observations = Column(Text, nullable = True)

    # Audit field (Created only)
    created_at = Column(DateTime, nullable = False, default = get_current_time_gmt)

    __table_args__ = (
        # iter5: batch_number added to the unique tuple. A PoS can now report
        # the same product across multiple lots in a single visit.
        UniqueConstraint(
            'attendance_id', 'product_id', 'batch_number',
            name = 'uc_impulse_start_attendance_product_batch'
        ),
    )

class ImpulseSale(Base):  # pylint: disable=too-few-public-methods
    '''
        Header record for a single Sale transaction.
    '''
    __tablename__ = 't_trade_impulse_sales'

    id = Column(Integer, primary_key = True, index = True)

    # Foreign Key to LOCALIZATION.t_attendances (The Visit ID)
    attendance_id = Column(Integer, nullable = False, index = True)

    company_id = Column(Integer, nullable = False, index = True)
    # 2026-05-20 (Binaria): sales are owned by the CLIENT company (the
    # one that owns the POS and the products sold). The executor lives
    # in the parent attendance's `company_id`.
    client_company_id = Column(Integer, nullable = True, index = True)
    # 2026-05-28 (Binaria): free-text annotation captured at the sale
    # header so the operator can attach context (promo applied, customer
    # remark, delivery issue) that doesn't fit at the line-item level.
    observations = Column(Text, nullable = True)
    created_at = Column(DateTime, nullable = False, default = get_current_time_gmt)

    # Relationship to the Sale Details (SKUs sold)
    details = relationship(
        'ImpulseSaleDetail',
        back_populates = 'sale_header',
        cascade = 'all, delete-orphan'
    )

    # Relationship to Photos
    photos = relationship(
        'Photo',
        primaryjoin = "and_(foreign(Photo.entity_id)==ImpulseSale.id, "
                    "Photo.entity_type=='IMPULSE_SALE')",
        uselist = True,
        viewonly = True
    )

class ImpulseSaleDetail(Base):  # pylint: disable=too-few-public-methods
    '''
        Detail record for a Sale transaction.
    '''
    __tablename__ = 't_trade_impulse_sale_details'

    id = Column(Integer, primary_key = True, index = True)

    # Relationship to the Sale Header
    impulse_sale_id = Column(
        Integer, ForeignKey('t_trade_impulse_sales.id', ondelete = 'CASCADE'),
        nullable = False, index = True
    )
    sale_header = relationship('ImpulseSale', back_populates = 'details')

    promotion_id = Column(Integer, nullable = True)
    # Relationship to the Product
    product_id = Column(
        Integer, ForeignKey('t_products.id', ondelete = 'RESTRICT'),
        nullable = False, index = True
    )
    product = relationship('Product')

    # Quantity sold
    quantity = Column(Integer, nullable = False)

    __table_args__ = (
        # A product can only appear once per sale transaction
        UniqueConstraint(
            'impulse_sale_id', 'product_id',
            name = 'uc_impulse_sale_product'
        ),
    )

class ImpulseInventoryEnd(Base, AttendanceProductMixin):  # pylint: disable=too-few-public-methods
    '''
        Records the final inventory count.

        iter5: same shape as ImpulseInventoryStart (batch + expiration +
        sala/almacén + client_company_id). See that model's docstring for
        the rationale behind unifying Impulses + Replenishments inventory.
    '''
    __tablename__ = 't_trade_impulse_inventory_end'
    id = Column(Integer, primary_key = True, index = True)

    client_company_id = Column(Integer, nullable = True, index = True)

    batch_number = Column(String(50), nullable = True, index = True)
    expiration_date = Column(DateTime, nullable = True)

    quantity_in_room = Column(Integer, nullable = False, default = 0)
    quantity_in_warehouse = Column(Integer, nullable = False, default = 0)
    quantity = Column(Integer, nullable = True)

    # Free-text notes captured by the operator during the count.
    observations = Column(Text, nullable = True)

    # Audit field (Created only)
    created_at = Column(DateTime, nullable = False, default = get_current_time_gmt)

    __table_args__ = (
        # A product can only be registered once per attendance (visit)
        UniqueConstraint(
            'attendance_id', 'product_id',
            name = 'uc_impulse_end_attendance_product'
        ),
    )
