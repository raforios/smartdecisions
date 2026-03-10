'''
    Mining Analysis Models
'''
from sqlalchemy import (
    Column,
    Integer,
    UniqueConstraint,
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

    id = Column(Integer, primary_key = True, index = True)
    name = Column(String(100), unique = True, nullable = False, index = True)
    unit = Column(String(20), nullable = False)
    created_at = Column(DateTime, nullable = False, default = get_current_time_gmt)

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

    id = Column(Integer, primary_key = True, index = True)
    mineral_id = Column(Integer, ForeignKey('t_minerals.id'), nullable = False)
    date = Column(Date, nullable = False, index = True)
    price_low = Column(Numeric(18, 4), nullable = True)
    price_high = Column(Numeric(18, 4), nullable = True)
    created_at = Column(DateTime, nullable = False, default = get_current_time_gmt)

    mineral = relationship('Mineral', back_populates='prices')

class Department(Base):# pylint: disable=too-few-public-methods
    '''
        Departament model for parameters
    '''
    __tablename__ = 't_departments'

    id = Column(Integer, primary_key = True, index = True)
    name = Column(String(100), unique=True, index = True, nullable = False)

    # Relación uno a muchos con Municipios
    municipalities = relationship('Municipality', back_populates='department')

class Municipality(Base):# pylint: disable=too-few-public-methods
    '''
        Municipality model for parameters
    '''
    __tablename__ = 't_municipalities'

    id = Column(Integer, primary_key = True, index = True)
    official_code = Column(Integer, unique=True, index = True, nullable = False) # Cod. Muni. Prod.
    name = Column(String(150), nullable = False)
    province = Column(String(150))
    department_id = Column(Integer, ForeignKey('t_departments.id'), nullable = False)

    # Relaciones
    department = relationship('Department', back_populates = 'municipalities')
    royalties = relationship('RoyaltyPayment', back_populates = 'municipality')

class RoyaltyPayment(Base):# pylint: disable=too-few-public-methods
    '''
        Royalty payment fact table for the Star Schema.
    '''
    __tablename__ = 't_royalties'

    id = Column(Integer, primary_key = True, index = True)
    municipality_id = Column(Integer, ForeignKey('t_municipalities.id'), nullable = False)
    period_date = Column(Date, index = True, nullable = False) # Primer día del mes evaluado

    # Métricas Financieras (Bs.)
    total_collected = Column(Numeric(18, 4), default = 0)
    commission = Column(Numeric(18, 4), default = 0)
    subtotal = Column(Numeric(18, 4), default = 0)
    gov_dept = Column(Numeric(18, 4), default = 0)
    gov_muni = Column(Numeric(18, 4), default = 0)

    # Restricción: Un solo registro por municipio y mes
    __table_args__ = (
        UniqueConstraint('municipality_id', 'period_date', name = 'uq_municipality_period'),
    )

    municipality = relationship('Municipality', back_populates = 'royalties')
