'''
    The two tables of the minerals ETL, as the API created them in MySQL.

    Only the columns the load reads or writes. The catalogue is the table
    `t_minerals`: the load matches the Excel headers against it, never against
    a list written in the code.
'''
import unicodedata

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import DeclarativeMeta, declarative_base

Base: DeclarativeMeta = declarative_base()


class Mineral(Base):  # pylint: disable=too-few-public-methods
    '''
        One mineral of the catalogue (`t_minerals`).
    '''
    __tablename__ = 't_minerals'

    id = Column(Integer, primary_key = True)
    name = Column(String(100), unique = True, nullable = False)
    unit = Column(String(20), nullable = False)
    chemical_symbol = Column(String(10), nullable = True)
    quoted_in = Column(String(50), nullable = True)
    method = Column(String(255), nullable = True)
    created_at = Column(DateTime, nullable = False)


class MiningPrice(Base):  # pylint: disable=too-few-public-methods
    '''
        One daily quotation (`t_mining_prices`).
    '''
    __tablename__ = 't_mining_prices'

    id = Column(Integer, primary_key = True)
    mineral_id = Column(Integer, ForeignKey('t_minerals.id'), nullable = False)
    date = Column(Date, nullable = False)
    price_low = Column(Numeric(18, 4), nullable = True)
    price_high = Column(Numeric(18, 4), nullable = True)
    created_at = Column(DateTime, nullable = False)


def normalize_name(name: str) -> str:
    '''
        Lower-cases and strips accents, so 'Estaño', 'ESTANO' and 'estano' match.

        Args:
            name (str): Name as written in the Excel or the table.

        Returns:
            str: The comparable form.
    '''
    base = unicodedata.normalize('NFKD', str(name).strip().lower())
    return ''.join(c for c in base if not unicodedata.combining(c))
