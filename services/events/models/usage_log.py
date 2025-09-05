'''
   Usage Log Models
'''
from sqlalchemy import Column, Integer, String, DateTime, JSON, Text
from sqlalchemy.sql import text
from services.db_connection import Base

class UsageLog(Base):# pylint: disable=R0903
    '''
        SQLAlchemy model for a usage log record.
    '''
    __tablename__ = 't_usage_logs'

    id = Column(Integer, primary_key = True, index = True)
    user_id = Column(String(50), nullable = False)
    microservice = Column(String(50), nullable = False)
    endpoint = Column(Text, nullable = False)
    method = Column(String(10), nullable = False)
    status_code = Column(Integer, nullable = False)
    ip_address = Column(String(50), nullable = False)
    request_body = Column(JSON, nullable = True)
    response_body = Column(JSON, nullable = True)
    response_time_ms = Column(Integer, nullable = True)
    timestamp = Column(DateTime, nullable = False, server_default = text('now()'))

    def __repr__(self):
        return (
            f"<UsageLog(id = {self.id}, microservice = '{self.microservice}', "
            f"user_id = '{self.user_id}', endpoint = '{self.endpoint}')>"
        )
