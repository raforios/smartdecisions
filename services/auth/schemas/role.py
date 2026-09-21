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
    # SmartDecisions roles. Users of one client share a `client`; MANAGER runs
    # the account (plans, stock, analysis), SELLER works the street from the
    # phone (their own routes, visits and sales).
    MANAGER = 'MANAGER'
    SELLER = 'SELLER'
