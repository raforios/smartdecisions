'''
    Domain enums shared between schemas, models and business logic.
'''
from enum import Enum


class RoleEnum(str, Enum):
    '''
        Roles consumed from the JWT payload. Mirrors the AUTH service enum.
    '''
    ADMIN = 'ADMIN'
    WAREHOUSE_MANAGER = 'WAREHOUSE_MANAGER'
    REQUESTER = 'REQUESTER'


class RequestStatusEnum(str, Enum):
    '''
        State machine for supply requests.

        Allowed transitions:
            CREATED      -> IN_PROCESS (warehouse picks up the request)
            CREATED      -> (physical delete by REQUESTER/ADMIN)
            IN_PROCESS   -> DELIVERED  (warehouse delivers; triggers kardex OUT)
            IN_PROCESS   -> REJECTED   (warehouse declines)
            IN_PROCESS   -> CANCELLED  (warehouse/admin annuls)
            DELIVERED    -> CLOSED     (requester confirms receipt)
    '''
    CREATED = 'CREATED'
    IN_PROCESS = 'IN_PROCESS'
    DELIVERED = 'DELIVERED'
    CLOSED = 'CLOSED'
    REJECTED = 'REJECTED'
    CANCELLED = 'CANCELLED'


class ReplenishmentStatusEnum(str, Enum):
    '''
        Lifecycle of a replenishment order placed against an external
        purchasing system.
    '''
    REQUESTED = 'REQUESTED'
    IN_RECEPTION = 'IN_RECEPTION'
    COMPLETED = 'COMPLETED'
    CANCELLED = 'CANCELLED'


class MovementTypeEnum(str, Enum):
    '''
        Direction of a kardex movement.
    '''
    IN = 'IN'
    OUT = 'OUT'
    ADJUSTMENT = 'ADJUSTMENT'


class ReferenceTypeEnum(str, Enum):
    '''
        Origin of a kardex movement, used together with reference_id to
        reconstruct the source document of any stock change.
    '''
    REPLENISHMENT = 'REPLENISHMENT'
    REQUEST = 'REQUEST'
    MANUAL = 'MANUAL'
