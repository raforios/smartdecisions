'''
    Role Schema
'''
from enum import Enum

class Role(str, Enum):
    '''
        Role Class with ENUM settings.
        Global per-user role emitted in the JWT payload and consumed by all
        downstream microservices.
    '''
    ADMIN = 'ADMIN'
    WAREHOUSE_MANAGER = 'WAREHOUSE_MANAGER'
    REQUESTER = 'REQUESTER'
    # Mining Summit (Cumbre Minera) roles.
    REGISTRATION = 'REGISTRATION'
    REPORTS = 'REPORTS'
