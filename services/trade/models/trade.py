'''
    Trade Models
'''
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
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

# --- A.3. TRADE PLANNING MODEL ---
class TradePlanning(Base):  # pylint: disable=too-few-public-methods
    '''
        Trade local planning.
        Links the PLANNING ID to the TRADE POS, the user,
        and the planned vs. actual workload.
        (Using classical SQLAlchemy 1.x syntax for consistency).
    '''
    __tablename__ = 't_trade_planning'

    id = Column(Integer, primary_key=True, index = True)
    company_id = Column(Integer, nullable = False, index = True)

    # ID from PLANNING microservice
    planning_id = Column(Integer, nullable = True, index = True)

    is_adhoc = Column(Boolean, default = False, nullable = False)
    justification = Column(Text, nullable = True)

    # User ID (from frontend)
    user_id = Column(Integer, nullable = False, index = True)

    # Link to the TRADE Point of Sale
    point_of_sale_id = Column(
        Integer,
        ForeignKey('t_points_of_sale.id', ondelete = 'RESTRICT'),
        nullable = False,
        index = True
    )
    point_of_sale = relationship("PointOfSale")

    # --- Business Rule: Workload Calculation ---

    # Workload defined in this plan (e.g., 60 minutes)
    planned_workload_minutes = Column(Integer, nullable = False)
    # Actual workload (calculated after check-out)
    actual_workload_minutes = Column(Integer, nullable = True)
    # Difference (calculated after check-out)
    workload_difference_minutes = Column(Integer, nullable = True)

    status = Column(String(20), default = 'PENDING', nullable = False)
    comments = Column(Text, nullable = True)

    # Audit field (Created only)
    created_at = Column(
        DateTime,
        nullable = False,
        default = get_current_time_gmt
    )

    __table_args__ = (
        # A user can only have one plan per POS and PLANNING ID
        UniqueConstraint(
            'planning_id', 'point_of_sale_id', 'user_id',
            name = 'uc_trade_planning_unique'
        ),
    )
