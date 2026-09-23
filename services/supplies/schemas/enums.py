'''
    Domain enums shared between schemas, models and business logic.
'''
from enum import Enum


class RoleEnum(str, Enum):
    '''
        Roles consumed from the JWT payload. Mirrors the AUTH service enum.
    '''
    ADMIN = 'ADMIN'
    MANAGER = 'MANAGER'
    WAREHOUSE_MANAGER = 'WAREHOUSE_MANAGER'


class EntryTypeEnum(str, Enum):
    '''
        Type of a warehouse entry (Nota de Ingreso). Mirrors the three intake
        channels of the legacy system.
    '''
    COMPRA = 'COMPRA'
    DONACION_TRANSFERENCIA = 'DONACION_TRANSFERENCIA'
    REINGRESO = 'REINGRESO'


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
    ENTRY = 'ENTRY'
    MANUAL = 'MANUAL'
