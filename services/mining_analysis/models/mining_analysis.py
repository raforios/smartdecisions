'''
    Mining Analysis Models
'''
from sqlalchemy import (
    Column,
    Integer,
    String,
    Numeric,
    DateTime,
    ForeignKey,
    Date
)
from sqlalchemy.orm import relationship
from services.db_connection import Base
from services.utils import get_current_time_gmt

class Mineral(Base): # pylint: disable=too-few-public-methods
    '''
        SQLAlchemy model for a mineral catalog.
    '''
    __tablename__ = 't_minerals'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    unit = Column(String(20), nullable=False)
    created_at = Column(DateTime, nullable=False, default=get_current_time_gmt)

    prices = relationship(
        'MiningPrice',
        back_populates='mineral',
        cascade='all, delete-orphan'
    )

class MiningPrice(Base): # pylint: disable=too-few-public-methods
    '''
        SQLAlchemy model for transactional mineral prices.
    '''
    __tablename__ = 't_mining_prices'

    id = Column(Integer, primary_key=True, index=True)
    mineral_id = Column(Integer, ForeignKey('t_minerals.id'), nullable=False)
    date = Column(Date, nullable=False, index=True)
    price_low = Column(Numeric(18, 4), nullable=True)
    price_high = Column(Numeric(18, 4), nullable=True)
    created_at = Column(DateTime, nullable=False, default=get_current_time_gmt)

    mineral = relationship('Mineral', back_populates='prices')
