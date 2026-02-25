'''
    POS Models
'''
import enum
from sqlalchemy import (
    Column,
    Integer,
    Numeric,
    String,
    ForeignKey,
    DateTime,
    Boolean,
    UniqueConstraint,
    and_
)
from sqlalchemy.dialects.mysql import ENUM as MySQLEnum
from sqlalchemy.orm import (
    relationship,
    foreign
)
from models.common import Photo
from services.db_connection import Base
from services.utils import get_current_time_gmt

class PointOfSaleStatus(enum.Enum):
    '''
        Represents the possible operational statuses for a Point of Sale.
    '''
    IN_CREATION = 'IN_CREATION'
    ACTIVE = 'ACTIVE'
    INACTIVE = 'INACTIVE'

class PointOfSale(Base):  # pylint: disable=too-few-public-methods
    '''
        Point of Sale (POS) Model.
    '''
    __tablename__ = 't_points_of_sale'

    id = Column(Integer, primary_key = True, index = True)
    company_id = Column(Integer, nullable = False, index = True)

    # Identification and Location (Mandatory)
    code = Column(String(50), nullable = False, index = True)
    name = Column(String(255), nullable = False)
    country_id = Column(Integer, nullable = False)
    city_id = Column(Integer, nullable = False)
    zone_id = Column(Integer, nullable = False)
    address = Column(String(255), nullable = False)
    latitude = Column(Numeric(10, 8), nullable = False)
    longitude = Column(Numeric(10, 8), nullable = False)
    max_checkin_distance = Column(Integer, nullable = False, default = 0)

    # Operation and Classification
    operating_hours = Column(String(255), nullable = True)
    pos_type_id = Column(Integer, nullable = False)
    channel_id = Column(Integer, nullable = False)
    status = Column(MySQLEnum(PointOfSaleStatus), nullable = False,
                    default = PointOfSaleStatus.IN_CREATION)

    # Complementary Information (Optional)
    external_code = Column(String(50), unique = True, nullable = True)
    description = Column(String(500), nullable = True)
    reference = Column(String(255), nullable = True)
    contact_person = Column(String(255), nullable = True)
    contact_phone = Column(String(50), nullable = True)
    contact_role = Column(String(100), nullable = True)

    # Relationship with local inventory
    inventory = relationship(
        'PointOfSaleInventory',
        back_populates = 'point_of_sale',
        cascade = 'all, delete-orphan'
    )

    photos = relationship(
        'Photo',
        primaryjoin = lambda: and_(
            Photo.entity_type == 'POS',
            foreign(Photo.entity_id) == PointOfSale.id
        ),
        lazy = 'joined',
        cascade = 'all, delete-orphan',
        overlaps = 'photos'
    )
    # Audit fields
    created_at = Column(DateTime, nullable = False, default = get_current_time_gmt)

    __table_args__ = (
        UniqueConstraint('company_id', 'code', name = 'uc_company_code'),
        UniqueConstraint('company_id', 'external_code', name = 'uc_company_external_code'),
    )

class PointOfSaleInventory(Base):  # pylint: disable=too-few-public-methods
    '''
        Detailed management of Local Inventories at the Point of Sale.
    '''
    __tablename__ = 't_pos_inventory'

    id = Column(Integer, primary_key = True, index = True)
    company_id = Column(Integer, nullable = False, index = True)

    # Relationship with the POS
    point_of_sale_id = Column(
        Integer, ForeignKey('t_points_of_sale.id', ondelete = 'CASCADE'),
        nullable = False, index = True
    )
    point_of_sale = relationship('PointOfSale', back_populates = 'inventory')

    # Relationship with the Product (SKU)
    product_id = Column(
        Integer, ForeignKey('t_products.id', ondelete = 'CASCADE'),
        nullable = False, index = True
    )
    product = relationship('Product')

    # Detailed inventory fields
    location = Column(String(50), nullable = False) # Location: Sala or Almacén
    batch_number = Column(String(50), nullable = False, index = True) # Batch

    expiration_date = Column(DateTime, nullable = False) # Expiration Date

    # Short Date: TRUE if it is a short date product.
    is_short_date = Column(Boolean, default = False)

    quantity = Column(Integer, nullable = False, default = 0) # Total units per SKU

    __table_args__ = (
        # Ensure the combination Batch/SKU/POS/Location is unique
        UniqueConstraint(
            'point_of_sale_id', 'product_id', 'batch_number', 'location', 
            name = 'uc_pos_inventory_detail'
        ),
    )

    # Audit field following the PLANNING model example
    created_at = Column(DateTime, nullable = False, default = get_current_time_gmt)
