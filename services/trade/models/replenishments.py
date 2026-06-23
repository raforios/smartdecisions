'''
    Replenishments Models
'''
# Inventory-style models intentionally share the same shape with
# `models.impulses` (quantity + observations + audit + unique constraint
# per attendance/product/batch). Pylint's duplicate-code detector flags
# the overlap; we keep the parallel structure to keep each model self-
# contained and silence the warning here.
# pylint: disable=duplicate-code
from typing import Optional
from sqlalchemy import (
    Boolean,
    Column,
    DECIMAL,
    Float,
    Integer,
    String,
    Text,
    Time,
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
    # Cliente (marca/producto) cuyo reporte de reposición se está registrando.
    # Nullable por compatibilidad con filas históricas anteriores al iter 5.
    client_company_id = Column(Integer, nullable = True, index = True)

    # Foreign Key to LOCALIZATION.t_attendances (The Visit ID)
    attendance_id = Column(Integer, nullable = False, index = True)
    comments = Column(Text, nullable = True)

    # Marcador para flujo de revisión / aprobación. Default False = pendiente.
    reviewed = Column(Boolean, nullable = False, default = False, index = True)

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

# iter5 (Binaria, 2026-06-20): ReplenishmentInventory was removed.
# Inventory is a single physical concept that both processes (Impulses
# and Replenishments) operate on, so it now lives in the unified tables
# t_trade_impulse_inventory_start and t_trade_impulse_inventory_end
# (see models.impulses). Replenishment flows write/read those tables via
# the existing /v1/impulses/visit/{attendance_id}/inventory-start and
# /inventory-end endpoints.

class ReplenishmentReception(Base, AttendanceProductMixin):  # pylint: disable=too-few-public-methods
    '''
        Records a product reception from a supplier at the POS.

        From iter 5 (Binaria, 2026-06-20) batch_number and expiration_date
        were added so the operator can register expirations on every
        incoming batch (the previous shape only had quantity + comments,
        which made traceability impossible — Binaria flagged this).
    '''
    __tablename__ = 't_trade_replenishment_receptions'
    id = Column(Integer, primary_key = True, index = True)
    client_company_id = Column(Integer, nullable = True, index = True)

    quantity_received = Column(Integer, nullable = False)

    # Iter 5 additions. Nullable so historical receptions registered without
    # this metadata keep parsing; new writes from the API populate them.
    batch_number = Column(String(50), nullable = True, index = True)
    expiration_date = Column(DateTime, nullable = True)

    # Optional comments from the user
    comments = Column(Text, nullable = True)

    # Audit field (Created only)
    created_at = Column(DateTime, nullable = False, default = get_current_time_gmt)

# --- B.3. COMPLEMENTARY ACTIVITIES MODELS ---

class ComplementaryBandeo(Base):  # pylint: disable=too-few-public-methods
    '''
        Header record for a Complementary Bandeo Report.

        iter6 (Binaria, 2026-06-22): drives the two-stage flow demanded by
        req 7.3.4.1. A visit can register N bandeos (one per planned
        promotion); each header walks through PENDING -> RECEIVED ->
        RETURNED with received_at / returned_at timestamps.
    '''
    __tablename__ = 't_trade_complementary_bandeo_header'

    id = Column(Integer, primary_key = True, index = True)

    company_id = Column(Integer, nullable = False, index = True)
    client_company_id = Column(Integer, nullable = True, index = True)

    # Foreign Key to LOCALIZATION.t_attendances (The Visit ID).
    # iter6: dropped the unique constraint — a visit can have several bandeos.
    attendance_id = Column(Integer, nullable = False, index = True)

    # iter6: which planned bandeo (promotion) this header belongs to.
    promotion_id = Column(
        Integer, ForeignKey('t_trade_promotions.id', ondelete = 'RESTRICT'),
        nullable = True, index = True
    )
    promotion = relationship('TradePromotion')

    # iter6: lifecycle of the in-field bandeo activity.
    status = Column(String(20), nullable = False, default = 'PENDING', index = True)
    received_at = Column(DateTime, nullable = True)
    returned_at = Column(DateTime, nullable = True)

    comments = Column(Text, nullable = True)
    created_at = Column(DateTime, nullable = False, default = get_current_time_gmt)

    # Relationship to the bandeo products
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

    __table_args__ = (
        # iter6: one header per planned bandeo per visit.
        UniqueConstraint(
            'attendance_id', 'promotion_id',
            name = 'uc_bandeo_attendance_promotion'
        ),
    )

class ComplementaryBandeoDetail(Base):  # pylint: disable=too-few-public-methods
    '''
        Detail record for a Bandeo Report.

        iter6 (Binaria, 2026-06-22): tracks the three quantities of the
        in-field flow (planned, received, used) plus the operator-editable
        returned amount and unit_of_measure. observations is required when
        the user overrides the calculated quantity_returned.
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

    # iter6: in-field quantities (req 7.3.4.1).
    quantity_planned = Column(Integer, nullable = False, default = 0)
    quantity_received = Column(Integer, nullable = False, default = 0)
    quantity_used = Column(Integer, nullable = True)
    # quantity_returned becomes editable in the Return stage and is
    # therefore nullable until the operator confirms it.
    quantity_returned = Column(Integer, nullable = True)

    unit_of_measure = Column(String(20), nullable = True)
    observations = Column(Text, nullable = True)

    __table_args__ = (
        # A product can only appear once per bandeo header
        UniqueConstraint(
            'bandeo_header_id', 'product_id',
            name = 'uc_bandeo_report_product'
        ),
    )

class ComplementaryPromoPoint(Base):  # pylint: disable=too-few-public-methods
    '''
        Records a Complementary Promotional Point Report.

        iter6 (Binaria, 2026-06-22): captures the fields demanded by
        req 7.3.4.2 — opening/closing time of the promotional point and
        a long-form description distinct from optional comments.
    '''
    __tablename__ = 't_trade_complementary_promo_point'

    id = Column(Integer, primary_key = True, index = True)

    company_id = Column(Integer, nullable = False, index = True)
    client_company_id = Column(Integer, nullable = True, index = True)

    # Foreign Key to LOCALIZATION.t_attendances (The Visit ID)
    attendance_id = Column(Integer, nullable = False, index = True)

    # iter6: per req 7.3.4.2 the operator must record activity window +
    # a long description (materials used, observations, etc.).
    opening_time = Column(Time, nullable = True)
    closing_time = Column(Time, nullable = True)
    description = Column(Text, nullable = True)

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

    # iter6 (Binaria, 2026-06-22): per req 7.3.4.3 — precio observado y
    # geolocalizacion del PC cuando no hay PDV abierto.
    price = Column(DECIMAL(12, 2), nullable = True)
    latitude = Column(Float, nullable = True)
    longitude = Column(Float, nullable = True)
    location_description = Column(Text, nullable = True)

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
