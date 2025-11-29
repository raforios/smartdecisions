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
        Records the initial inventory count at the start of an Impulse visit.
    '''
    __tablename__ = 't_trade_impulse_inventory_start'

    id = Column(Integer, primary_key = True, index = True)

    # Quantity counted at the start
    quantity = Column(Integer, nullable = False)

    # Audit field (Created only)
    created_at = Column(DateTime, nullable = False, default = get_current_time_gmt)

    __table_args__ = (
        # A product can only be registered once per attendance (visit)
        UniqueConstraint(
            'attendance_id', 'product_id',
            name = 'uc_impulse_start_attendance_product'
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
    '''
    __tablename__ = 't_trade_impulse_inventory_end'
    id = Column(Integer, primary_key = True, index = True)

    # Quantity counted at the end
    quantity = Column(Integer, nullable = False)

    # Audit field (Created only)
    created_at = Column(DateTime, nullable = False, default = get_current_time_gmt)

    __table_args__ = (
        # A product can only be registered once per attendance (visit)
        UniqueConstraint(
            'attendance_id', 'product_id',
            name = 'uc_impulse_end_attendance_product'
        ),
    )
