'''
    Common Models
'''

from sqlalchemy import Column, Integer, String, DateTime, Index
from services.db_connection import Base
from services.utils import get_current_time_gmt

class Photo(Base):# pylint: disable=too-few-public-methods
    '''
        Polymorphic model for storing photos (S3 URLs)
        for different entities (Products, POS, etc.).
    '''
    __tablename__ = 't_trade_photos'

    id = Column(Integer, primary_key = True, index = True)
    company_id = Column(Integer, nullable = False, index = True)

    entity_type = Column(String(50), nullable = False, index = True)
    entity_id = Column(Integer, nullable = False, index = True)

    file_url = Column(String(500), nullable = False)
    file_key = Column(String(500), nullable = True)

    description = Column(String(255), nullable = True)

    created_at = Column(DateTime, nullable = False, default = get_current_time_gmt)

    __table_args__ = (
        Index('ix_entity_photos', 'entity_type', 'entity_id'),
    )
