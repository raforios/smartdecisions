'''
    Trade Models
'''
from sqlalchemy import (
    Column,
    Integer,
    Numeric,
    String,
    Text,
    ForeignKey,
    DateTime,
    Boolean,
    UniqueConstraint
)
from sqlalchemy.orm import (
    relationship,
    Mapped,
    mapped_column,
    declared_attr
)
from services.db_connection import Base
from services.utils import get_current_time_gmt

class SKUSequencer(Base):  # pylint: disable=too-few-public-methods
    '''
        Control table to manage the sequential number (SEC) of the SKU.
        Ensures atomicity and uniqueness of the sequence PER company and PER category combination.
    '''
    __tablename__ = 't_sku_sequencer'

    id = Column(Integer, primary_key = True, index = True)

    # Composite key representing the relevant category combination.
    # Example: '100.200.000.000' for SKU '100.200.000.000.001'
    segment_key = Column(String(50), nullable = False, index = True)

    # Last assigned sequential number
    last_sequence_number = Column(Integer, default = 0, nullable = False)

    company_id = Column(Integer, nullable = False, index = True)

    __table_args__ = (
        # The combination of segment key and company must be unique
        UniqueConstraint('segment_key', 'company_id', name = 'uc_sku_segment_company'),
    )

    # Audit field following the PLANNING model example
    created_at = Column(DateTime, nullable = False, default = get_current_time_gmt)


class Product(Base):  # pylint: disable=too-few-public-methods
    '''
        Product Catalog. Stores the complete SKU and classification categories.
    '''
    __tablename__ = 't_products'

    id = Column(Integer, primary_key = True, index = True)
    company_id = Column(Integer, nullable = False, index = True)

    # Complete SKU: XXX.YYY.ZZZ.WWW.SEC
    sku = Column(String(50), unique = True, nullable = False, index = True)

    name = Column(String(255), nullable = False)
    description = Column(Text, nullable = True)

    # The 4 classification categories
    category_1_code = Column(String(10), nullable = False) # XXX_(Mandatory)
    category_2_code = Column(String(10), nullable = True, default = '000')  # YYY
    category_3_code = Column(String(10), nullable = True, default = '000')  # ZZZ
    category_4_code = Column(String(10), nullable = True, default = '000')  # WWW

    status = Column(String(20), default = 'ACTIVE')

    # Audit fields
    created_at = Column(DateTime, nullable = False, default = get_current_time_gmt)

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
    # DECIMAL(10, 7) for coordinate precision.
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

class SKUEquivalency(Base):  # pylint: disable=too-few-public-methods
    '''
        Catalog to store product code equivalencies between the internal
        SKU and external client systems.
    '''
    __tablename__ = 't_trade_sku_equivalencies'

    id = Column(Integer, primary_key = True, index = True)
    company_id = Column(Integer, nullable = False, index = True)

    # Relationship to the internal Product (SKU)
    product_id = Column(
        Integer, ForeignKey('t_products.id', ondelete = 'CASCADE'),
        nullable = False, index = True
    )
    product = relationship('Product')

    # Name of the external system (e.g., "SAP", "ERP_CLIENTE")
    external_system_name = Column(String(100), nullable = False, index = True)

    # Code of the product in the external system
    external_product_code = Column(String(50), nullable = False, index = True)

    # Standard status field
    status = Column(String(20), default = 'ACTIVE', nullable = False)

    # Audit field (Created only)
    created_at = Column(DateTime, nullable = False, default = get_current_time_gmt)

    __table_args__ = (
        # Ensure the external code is unique per external system and company
        UniqueConstraint(
            'company_id', 'external_system_name', 'external_product_code',
            name = 'uc_external_system_code'
        ),
    )

class ProductAssignmentPOS(Base):  # pylint: disable=too-few-public-methods
    '''
        Maps which Products (SKUs) are assigned to which Points of Sale (POS).
    '''
    __tablename__ = 't_trade_product_assignments_pos'

    id = Column(Integer, primary_key = True, index = True)
    company_id = Column(Integer, nullable = False, index = True)

    # Relationship to the Product
    product_id = Column(
        Integer, ForeignKey('t_products.id', ondelete = 'CASCADE'),
        nullable = False, index = True
    )
    product = relationship('Product')

    # Relationship to the Point of Sale
    point_of_sale_id = Column(
        Integer, ForeignKey('t_points_of_sale.id', ondelete = 'CASCADE'),
        nullable = False, index = True
    )
    point_of_sale = relationship('PointOfSale')

    # Standard status field
    status = Column(String(20), default = 'ACTIVE', nullable = False)

    # Audit field (Created only)
    created_at = Column(DateTime, nullable = False, default = get_current_time_gmt)

    __table_args__ = (
        # A product can only be assigned to a POS once per company
        UniqueConstraint(
            'company_id', 'product_id', 'point_of_sale_id',
            name = 'uc_product_pos_assignment'
        ),
    )

class AttendanceProductMixin: # pylint: disable=too-few-public-methods
    '''
        Mixin (template) for models that link a visit (attendance_id)
        and a product (product_id).
    '''

    @declared_attr
    # pylint: disable=no-self-argument
    def attendance_id(cls) -> Mapped[int]:
        '''
            Foreign Key column for LOCALIZATION.t_attendances (The Visit ID)
        '''
        return mapped_column(Integer, nullable = False, index = True)

    @declared_attr
    # pylint: disable=no-self-argument
    def product_id(cls) -> Mapped[int]:
        '''
            Foreign Key column for t_products.
        '''
        return mapped_column(
            Integer,
            ForeignKey('t_products.id', ondelete = 'RESTRICT'),
            nullable = False,
            index = True
        )

    @declared_attr
    # pylint: disable=no-self-argument
    def product(cls) -> Mapped['Product']:
        '''
            Relationship with t_products.
        '''
        return relationship('Product')
