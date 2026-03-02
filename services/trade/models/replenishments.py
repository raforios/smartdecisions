'''
    Replenishments Models
'''
from typing import Optional
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

# --- B.2. REPLENISHMENT ACTIVITIES MODELS ---

class ReplenishmentReport(Base):  # pylint: disable=too-few-public-methods
    '''
        Records a Replenishment (Stocking) report.
    '''
    __tablename__ = 't_trade_replenishment_reports'

    id = Column(Integer, primary_key = True, index = True)

    company_id = Column(Integer, nullable = False, index = True)

    # Foreign Key to LOCALIZATION.t_attendances (The Visit ID)
    attendance_id = Column(Integer, nullable = False, index = True)
    comments = Column(Text, nullable = True)

    # Audit field (Created only)
    created_at = Column(DateTime, nullable = False, default = get_current_time_gmt)

    # Relationship to Photos (Polymorphic)
    photos = relationship(
        'Photo',
        primaryjoin = "and_(foreign(Photo.entity_id)==ReplenishmentReport.id, "
                    "Photo.entity_type=='REPLENISHMENT_REPORT')",
        uselist = True,
        viewonly = True
    )

class ReplenishmentInventory(Base, AttendanceProductMixin):  # pylint: disable=too-few-public-methods
    '''
        Records the detailed inventory count during a Replenishment visit.
    '''
    __tablename__ = 't_trade_replenishment_inventory'

    id = Column(Integer, primary_key = True, index = True)

    batch_number = Column(String(50), nullable = False, index = True)
    expiration_date = Column(DateTime, nullable = False)
    quantity = Column(Integer, nullable = False)

    # Audit field (Created only)
    created_at = Column(DateTime, nullable = False, default = get_current_time_gmt)

    __table_args__ = (
        # A product/batch combination can only be registered once per visit
        UniqueConstraint(
            'attendance_id', 'product_id', 'batch_number',
            name = 'uc_replenish_inv_attendance_product_batch'
        ),
    )

class ReplenishmentReception(Base, AttendanceProductMixin):  # pylint: disable=too-few-public-methods
    '''
        Records a product reception from a supplier at the POS.
    '''
    __tablename__ = 't_trade_replenishment_receptions'
    id = Column(Integer, primary_key = True, index = True)

    quantity_received = Column(Integer, nullable = False)

    # Optional comments from the user
    comments = Column(Text, nullable = True)

    # Audit field (Created only)
    created_at = Column(DateTime, nullable = False, default = get_current_time_gmt)

# --- B.3. COMPLEMENTARY ACTIVITIES MODELS ---

class ComplementaryBandeo(Base):  # pylint: disable=too-few-public-methods
    '''
        Header record for a Complementary Bandeo Report.
    '''
    __tablename__ = 't_trade_complementary_bandeo_header'

    id = Column(Integer, primary_key = True, index = True)

    company_id = Column(Integer, nullable = False, index = True)

    # Foreign Key to LOCALIZATION.t_attendances (The Visit ID)
    # A visit can only have one bandeo report.
    attendance_id = Column(Integer, nullable = False, unique = True, index = True)
    comments = Column(Text, nullable = True)
    created_at = Column(DateTime, nullable = False, default = get_current_time_gmt)

    # Relationship to the returned products
    details = relationship(
        'ComplementaryBandeoDetail',
        back_populates = 'bandeo_header',
        cascade = 'all, delete-orphan'
    )

    photos = relationship(
        'Photo',
        primaryjoin = "and_(foreign(Photo.entity_id)==ComplementaryBandeo.id, "
                    "Photo.entity_type=='BANDEO')",
        uselist = True,
        viewonly = True
    )

class ComplementaryBandeoDetail(Base):  # pylint: disable=too-few-public-methods
    '''
        Detail record for a Bandeo Report.
    '''
    __tablename__ = 't_trade_complementary_bandeo_detail'

    id = Column(Integer, primary_key = True, index = True)

    # Relationship to the Bandeo Header
    bandeo_header_id = Column(
        Integer, ForeignKey('t_trade_complementary_bandeo_header.id', ondelete = 'CASCADE'),
        nullable = False, index = True
    )
    bandeo_header = relationship('ComplementaryBandeo', back_populates = 'details')

    # Relationship to the Product being returned
    product_id = Column(
        Integer, ForeignKey('t_products.id', ondelete = 'RESTRICT'),
        nullable = False, index = True
    )
    product = relationship('Product')

    # Quantity returned
    quantity_returned = Column(Integer, nullable = False)

    __table_args__ = (
        # A product can only appear once per bandeo report
        UniqueConstraint(
            'bandeo_header_id', 'product_id',
            name = 'uc_bandeo_report_product'
        ),
    )

class ComplementaryPromoPoint(Base):  # pylint: disable=too-few-public-methods
    '''
        Records a Complementary Promotional Point Report.
    '''
    __tablename__ = 't_trade_complementary_promo_point'

    id = Column(Integer, primary_key = True, index = True)

    company_id = Column(Integer, nullable = False, index = True)

    # Foreign Key to LOCALIZATION.t_attendances (The Visit ID)
    attendance_id = Column(Integer, nullable = False, index = True)
    comments = Column(Text, nullable = True)
    created_at = Column(DateTime, nullable = False, default = get_current_time_gmt)

    photos = relationship(
        'Photo',
        primaryjoin = "and_(foreign(Photo.entity_id)==ComplementaryPromoPoint.id, "
                    "Photo.entity_type=='PROMO_POINT')",
        uselist = True,
        viewonly = True
    )

class ComplementaryCompetition(Base):  # pylint: disable=too-few-public-methods
    '''
        Records a general report on Competitor Activity.
    '''
    __tablename__ = 't_trade_complementary_competition'

    id = Column(Integer, primary_key = True, index = True)

    # Linked to the user and company
    user_id = Column(Integer, nullable = False, index = True)
    company_id = Column(Integer, nullable = False, index = True)

    # Optionally linked to a POS if the report is specific to one
    point_of_sale_id = Column(
        Integer, ForeignKey('t_points_of_sale.id', ondelete = 'SET NULL'),
        nullable = True, index = True
    )
    point_of_sale = relationship('PointOfSale')

    competitor_name = Column(String(255), nullable = False)
    activity_type = Column(String(255), nullable = True)
    product_name = Column(String(255), nullable = True)
    details = Column(Text, nullable = True)
    created_at = Column(DateTime, nullable = False, default = get_current_time_gmt)

    @property
    def pos_id(self) -> Optional[int]:
        '''Alias for point_of_sale_id for schema compatibility.'''
        return self.point_of_sale_id

    photos = relationship(
        'Photo',
        primaryjoin = "and_(foreign(Photo.entity_id)==ComplementaryCompetition.id, "
                    "Photo.entity_type=='COMPETITION')",
        uselist = True,
        viewonly = True
    )
