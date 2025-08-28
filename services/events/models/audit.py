'''
   Audit Models
'''
from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.sql import text
from sqlalchemy.orm import declarative_base
from services.db_connection import Base

class AuditRecord(Base):# pylint: disable=R0903
    '''
        SQLAlchemy model for an audit record.
    '''
    __tablename__ = 't_audit_records'

    id = Column(Integer, primary_key = True, index = True)
    microservice = Column(String(50), nullable = False)
    entity_name = Column(String(50), nullable = False)
    entity_id = Column(Integer, nullable = False)
    action = Column(String(10), nullable = False)
    user_id = Column(String(50), nullable = False)
    timestamp = Column(DateTime, nullable = False, server_default = text('now()'))
    old_values = Column(JSON, nullable = True)
    new_values = Column(JSON, nullable = True)

    def __repr__(self):
        return (
            f"<AuditRecord(id = {self.id}, microservice = '{self.microservice}', "
            f"entity_name = '{self.entity_name}', action = '{self.action}')>"
        )
