'''
    POS Models
'''
from sqlalchemy import (
    Column,
    Integer,
    Numeric,
    String,
    ForeignKey,
    DateTime,
    Boolean,
    UniqueConstraint
)
from sqlalchemy.orm import (
    relationship
)
from services.db_connection import Base
from services.utils import get_current_time_gmt

class PointOfSale(Base):  # pylint: disable=too-few-public-methods
    '''
        Point of Sale (POS) Model.
    '''
    __tablename__ = 't_points_of_sale'

    id = Column(Integer, primary_key = True, index = True)
    company_id = Column(Integer, nullable = False, index = True)

    name = Column(String(255), nullable = False)
    external_code = Column(String(50), unique = True, nullable = True)
    address = Column(String(255), nullable = True)
    is_active = Column(Boolean, default = True, nullable = False)

    # Geolocalization (for integration with LOCALIZATION)
    latitude = Column(Numeric(16, 14), nullable = False)
    longitude = Column(Numeric(16, 14), nullable = False)

    # Relationship with local inventory
    inventory = relationship(
        'PointOfSaleInventory',
        back_populates = 'point_of_sale',
        cascade = 'all, delete-orphan'
    )

    # Audit fields
    created_at = Column(DateTime, nullable = False, default = get_current_time_gmt)

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
