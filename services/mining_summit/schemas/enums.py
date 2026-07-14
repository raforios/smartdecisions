'''
    Domain enumerations for the Mining Summit service.
'''
from enum import Enum


class RoleEnum(str, Enum):
    '''
        Access-control roles consumed from the JWT 'role' claim (issued by AUTH).

        ADMIN        -> full access (config, ETL, baja/reemplazo, reports).
        REGISTRATION -> accreditation desk: scan QR / mark attendance and
                        register new attendees when authorized (cupo available).
        REPORTS      -> read-only: view reports and download the Excel exports;
                        cannot register or modify data.
    '''
    ADMIN = 'ADMIN'
    REGISTRATION = 'REGISTRATION'
    REPORTS = 'REPORTS'


# Role sets used by the route guards, single-sourced to avoid divergence.
# Attendance desk (register attendance / create attendees on-the-fly).
REGISTRATION_ROLES: tuple[str, ...] = (RoleEnum.ADMIN.value, RoleEnum.REGISTRATION.value)
# Read-only viewing of participants/attendances (any authenticated operator).
VIEW_ROLES: tuple[str, ...] = (
    RoleEnum.ADMIN.value, RoleEnum.REGISTRATION.value, RoleEnum.REPORTS.value
)
# Reports and Excel exports.
REPORT_ROLES: tuple[str, ...] = (RoleEnum.ADMIN.value, RoleEnum.REPORTS.value)


class ParticipantStatus(str, Enum):
    '''
        Lifecycle state of an accredited participant.

        ACTIVE   -> currently accredited; appears in the initial reports.
        REPLACED -> stepped down; a substitute took the seat (data retained,
                    hidden from the initial reports).
        CANCELLED -> accreditation annulled without substitute (data retained).
    '''
    ACTIVE = 'ACTIVE'
    REPLACED = 'REPLACED'
    CANCELLED = 'CANCELLED'


class ParticipantRole(str, Enum):
    '''
        Functional role a participant plays at the summit working tables.
        Derived from the institution's category (see summit_rules).
    '''
    PARTICIPANTE = 'PARTICIPANTE'
    MODERADOR = 'MODERADOR'
    VEEDOR = 'VEEDOR'
    INVITADO = 'INVITADO'
    ORGANIZADOR = 'ORGANIZADOR'
    PRENSA = 'PRENSA'
    FACILITADOR = 'FACILITADOR'


class AssignmentType(str, Enum):
    '''
        Whether a participant holds a permanent table seat (FIJO) or rotates
        in temporarily without consuming a fixed seat (ROTATIVO).
    '''
    FIJO = 'FIJO'
    ROTATIVO = 'ROTATIVO'


class ThematicAxis(str, Enum):
    '''
        The six fixed thematic axes (ejes) discussed at the summit tables.
    '''
    SEGURIDAD_JURIDICA = 'SEGURIDAD_JURIDICA'
    CONTRATOS = 'CONTRATOS'
    INSTITUCIONALIDAD = 'INSTITUCIONALIDAD'
    MEDIO_AMBIENTE = 'MEDIO_AMBIENTE'
    COMERCIALIZACION = 'COMERCIALIZACION'
    DESARROLLO_PRODUCTIVO = 'DESARROLLO_PRODUCTIVO'


class InstitutionCategory(str, Enum):
    '''
        The nine institutional categories from the official participation matrix
        (matriz_participantes.xlsx). Values match the spreadsheet labels verbatim.
    '''
    ACTORES_PRODUCTIVOS = 'ACTORES PRODUCTIVOS MINEROS'
    COOPERACION_LOGISTICA = 'COOPERACIÓN Y APOYO LOGÍSTICO'
    CAMARAS = 'CÁMARAS INDUSTRIALES Y EMPRESARIALES'
    GOBIERNOS_DEPARTAMENTALES = 'GOBIERNOS AUTÓNOMOS DEPARTAMENTALES'
    INSTITUCIONES_AFINES = 'INSTITUCIONES AFINES Y REGIONALES'
    PUBLICAS_NIVEL_CENTRAL = 'INSTITUCIONES PÚBLICAS - NIVEL CENTRAL'
    ORGANO_LEGISLATIVO = 'ÓRGANO LEGISLATIVO'
    ORGANIZADOR_ENTE_RECTOR = 'ORGANIZADOR / ENTE RECTOR'
    SECTOR_ACADEMICO = 'SECTOR ACADÉMICO Y DE INVESTIGACIÓN'
