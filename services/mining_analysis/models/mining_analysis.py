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

    # New metadata columns
    chemical_symbol = Column(String(10), nullable = True)
    quoted_in = Column(String(50), nullable = True) # E.g., LME, AM, LFIX
    method = Column(String(255), nullable = True)

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
    transactions = relationship('RoyaltyTransaction', back_populates = 'municipality')


# --- NUEVOS MODELOS PARA DETALLE DE PAGOS Y EMPRESAS ---

class Company(Base):# pylint: disable=too-few-public-methods
    '''
        Company model to track mining operators.
    '''
    __tablename__ = 't_companies'

    id = Column(Integer, primary_key = True, index = True)
    nit = Column(String(50), unique = True, index = True, nullable = False)
    name = Column(String(250), nullable = False)

    # Relación con las transacciones de pago
    transactions = relationship('RoyaltyTransaction', back_populates = 'company')

class RoyaltyTransaction(Base):# pylint: disable=too-few-public-methods
    '''
        Granular fact table for individual royalty payments.
        Origin: "DETALLE DE PAGOS" sheet.
    '''
    __tablename__ = 't_royalty_transactions'

    id = Column(Integer, primary_key = True, index = True)
    company_id = Column(Integer, ForeignKey('t_companies.id'), nullable = False)
    municipality_id = Column(Integer, ForeignKey('t_municipalities.id'), nullable = False)

    # Referencias del pago
    order_number = Column(String(100), index = True, nullable = False)
    form_code = Column(String(50))
    bank_code = Column(String(50))

    # Temporalidad (Fecha de documento y particiones)
    payment_date = Column(Date, index = True, nullable = False)
    year = Column(Integer, index = True, nullable = False)
    month = Column(Integer, index = True, nullable = False)

    # Métricas Financieras
    amount_paid_bob = Column(Numeric(18, 4), default = 0)
    amount_paid_usd = Column(Numeric(18, 4), default = 0)

    # Relaciones
    company = relationship('Company', back_populates = 'transactions')
    municipality = relationship('Municipality', back_populates = 'transactions')


# --- MODELO ORIGINAL DE COPARTICIPACIÓN MANTENIDO ---

class RoyaltyPayment(Base):# pylint: disable=too-few-public-methods
    '''
        Royalty payment summary table.
        Origin: "COPARTICIPACIÓN" sheet.
    '''
    __tablename__ = 't_royalties'

    id = Column(Integer, primary_key = True, index = True)
    municipality_id = Column(Integer, ForeignKey('t_municipalities.id'), nullable = False)

    # Fecha completa y particiones temporales
    period_date = Column(Date, index = True, nullable = False)
    year = Column(Integer, index = True, nullable = False)
    month = Column(Integer, index = True, nullable = False)
    day = Column(Integer, index = True, nullable = False)

    # Métricas Financieras (Bs.)
    total_collected_bob = Column(Numeric(18, 4), default = 0)
    commission_bob = Column(Numeric(18, 4), default = 0)
    subtotal_bob = Column(Numeric(18, 4), default = 0)
    gov_dept_bob = Column(Numeric(18, 4), default = 0)
    gov_muni_bob = Column(Numeric(18, 4), default = 0)

    # Métricas Financieras (USD) calculadas dinámicamente en el ETL
    total_collected_usd = Column(Numeric(18, 4), default = 0)
    commission_usd = Column(Numeric(18, 4), default = 0)
    subtotal_usd = Column(Numeric(18, 4), default = 0)
    gov_dept_usd = Column(Numeric(18, 4), default = 0)
    gov_muni_usd = Column(Numeric(18, 4), default = 0)

    # Restricción: Un solo registro por municipio y mes en el resumen
    __table_args__ = (
        UniqueConstraint('municipality_id', 'period_date', name = 'uq_municipality_period'),
    )

    municipality = relationship('Municipality', back_populates = 'royalties')
