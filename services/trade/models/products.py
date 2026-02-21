'''
    Products Models
'''
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    ForeignKey,
    DateTime,
    UniqueConstraint,
    and_,
    Numeric
)
from sqlalchemy.orm import (
    relationship,
    foreign,
    Mapped,
    mapped_column,
    declared_attr
)
from models.common import Photo
from services.db_connection import Base
from services.utils import get_current_time_gmt

# pylint: disable=too-few-public-methods
class ProductCategory(Base):
    '''
        Stores the externally provided category codes for a product.
        This allows for a flexible number of categories (4 to 7+).
    '''
    __tablename__ = 't_product_categories'

    id = Column(Integer, primary_key = True, index = True)
    product_id = Column(Integer, ForeignKey('t_products.id', ondelete = 'CASCADE'),
                        nullable = False, index = True)

    # Identifier for the category, e.g., 'BRAND', 'FLAVOR', 'SIZE'
    # This corresponds to the old 'category_1', 'category_2' concept.
    category_name = Column(String(100), nullable = False)

    # The actual code from the external system, e.g., 'COKE', 'CHERRY', '12OZ'
    category_code = Column(String(50), nullable = False)

    __table_args__ = (
        UniqueConstraint('product_id', 'category_name', name='uc_product_category_name'),
    )

class Product(Base):  # pylint: disable=too-few-public-methods
    '''
        Product Catalog. Stores the complete SKU and related data.
        Category information is now in a separate table.
    '''
    __tablename__ = 't_products'

    id = Column(Integer, primary_key = True, index = True)
    company_id = Column(Integer, nullable = False, index = True)

    # Complete SKU: XXX.YYY.ZZZ.WWW.SEC (logic will now read from ProductCategory)
    sku = Column(String(50), unique = True, nullable = False, index = True)

    name = Column(String(255), nullable = False)
    description = Column(Text, nullable = True)

    # --- Relationship to flexible categories ---
    categories = relationship(
        'ProductCategory',
        cascade='all, delete-orphan',
        backref='product'
    )

    # --- Fields from section 5.3 ---
    product_type = Column(String(50), nullable = False) # Venta / Promocional

    # Units of Measure
    stock_unit = Column(String(10), nullable = False)
    replenishment_unit = Column(String(10), nullable = False)
    purchase_unit = Column(String(10), nullable = True)
    sale_unit = Column(String(10), nullable = True)

    # Stock Control
    near_expiration_days = Column(Integer, nullable = False)
    minimum_stock = Column(Integer, nullable = False)

    # Pricing
    stock_value = Column(Numeric(10, 2), nullable = True)
    purchase_price = Column(Numeric(10, 2), nullable = True)
    sale_price = Column(Numeric(10, 2), nullable = True)
    currency = Column(String(10), nullable = True)

    # Other Product Data
    manufacturer = Column(String(255), nullable = True)
    country_of_origin = Column(String(10), nullable = True)
    handling_instructions = Column(Text, nullable = True)
    storage_conditions = Column(Text, nullable = True)
    special_precautions = Column(Text, nullable = True)

    status = Column(String(20), default = 'ACTIVE')

    photos = relationship(
        'Photo',
        primaryjoin = lambda: and_(
            Photo.entity_type == 'PRODUCT',
            foreign(Photo.entity_id) == Product.id
        ),
        lazy = 'joined',
        cascade = 'all, delete-orphan'
    )

    # Audit fields
    created_at = Column(DateTime, nullable = False, default = get_current_time_gmt)

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
    product = relationship('Product', overlaps = 'product')

    # Name of the external system (e.g., 'SAP', 'ERP_CLIENTE')
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
        return relationship('Product', overlaps = 'product')

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
    product = relationship('Product', overlaps = 'product')

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
