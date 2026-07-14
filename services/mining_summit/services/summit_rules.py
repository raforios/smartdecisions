'''
    Business reference rules for the Mining Summit.

    Single source of truth for how an institution's category maps to a
    participant role, and how that role maps to a seat-assignment type. Kept
    here (not in schemas) because these are business rules, not data shapes.
'''
from schemas.enums import (
    AssignmentType,
    InstitutionCategory,
    ParticipantRole,
    ThematicAxis
)

# Each institutional category determines the functional role its members play
# at the working tables. Confirmed by the event owner (2026-07-10).
CATEGORY_ROLE_MAP: dict[InstitutionCategory, ParticipantRole] = {
    InstitutionCategory.ACTORES_PRODUCTIVOS: ParticipantRole.PARTICIPANTE,
    InstitutionCategory.INSTITUCIONES_AFINES: ParticipantRole.PARTICIPANTE,
    InstitutionCategory.PUBLICAS_NIVEL_CENTRAL: ParticipantRole.MODERADOR,
    InstitutionCategory.ORGANO_LEGISLATIVO: ParticipantRole.MODERADOR,
    InstitutionCategory.SECTOR_ACADEMICO: ParticipantRole.VEEDOR,
    InstitutionCategory.GOBIERNOS_DEPARTAMENTALES: ParticipantRole.INVITADO,
    InstitutionCategory.COOPERACION_LOGISTICA: ParticipantRole.ORGANIZADOR,
    InstitutionCategory.CAMARAS: ParticipantRole.ORGANIZADOR,
    InstitutionCategory.ORGANIZADOR_ENTE_RECTOR: ParticipantRole.ORGANIZADOR
}

# Participants and moderators hold a permanent seat; observers and guests rotate
# in temporarily; organizers do not take a table seat at all.
ROLE_ASSIGNMENT_MAP: dict[ParticipantRole, AssignmentType] = {
    ParticipantRole.PARTICIPANTE: AssignmentType.FIJO,
    ParticipantRole.MODERADOR: AssignmentType.FIJO,
    ParticipantRole.VEEDOR: AssignmentType.ROTATIVO,
    ParticipantRole.INVITADO: AssignmentType.ROTATIVO,
    ParticipantRole.ORGANIZADOR: AssignmentType.ROTATIVO,
    ParticipantRole.PRENSA: AssignmentType.ROTATIVO,
    ParticipantRole.FACILITADOR: AssignmentType.ROTATIVO
}

# Display metadata for the six thematic axes: (official number, human label).
AXIS_METADATA: dict[ThematicAxis, tuple[int, str]] = {
    ThematicAxis.SEGURIDAD_JURIDICA: (1, 'Seguridad Jurídica Minera'),
    ThematicAxis.CONTRATOS: (2, 'Contratos Mineros'),
    ThematicAxis.INSTITUCIONALIDAD: (3, 'Institucionalidad y Organización del Sector Minero'),
    ThematicAxis.MEDIO_AMBIENTE: (4, 'Medio Ambiente'),
    ThematicAxis.COMERCIALIZACION: (5, 'Comercialización, Trazabilidad y Minería Ilegal'),
    ThematicAxis.DESARROLLO_PRODUCTIVO: (6, 'Desarrollo Productivo, Inversiones e Incentivos')
}

# Reverse lookup used by the ETL to resolve the Excel "Eje Temático" number
# (1-6) chosen by each participant into its thematic axis.
AXIS_BY_NUMBER: dict[int, ThematicAxis] = {
    number: axis for axis, (number, _label) in AXIS_METADATA.items()
}


def resolve_axis_by_number(number: int) -> ThematicAxis:
    '''
        Resolves the thematic axis for an official axis number (1-6).

        Args:
            number (int): The axis number as filled in the registration Excel.

        Returns:
            ThematicAxis: The matching thematic axis.

        Raises:
            KeyError: If the number is outside the 1-6 range.
    '''
    return AXIS_BY_NUMBER[number]

# Every classroom-table (aula ≡ mesa) seats the same number of people.
MESA_CAPACITY = 30

# The 17 campus rooms assigned to the summit (the non-highlighted rooms in
# aulas.jpeg), all with a 30-seat capacity: 17 x 30 = 510 fixed seats. Order is
# preserved from the source layout and drives the axis allocation below.
AULAS_SEED: tuple[dict[str, str | int], ...] = (
    {'code': 'A3', 'block': 'A', 'location': 'Planta Baja', 'capacity': MESA_CAPACITY},
    {'code': 'A7', 'block': 'A', 'location': 'Primer Piso', 'capacity': MESA_CAPACITY},
    {'code': 'A8', 'block': 'A', 'location': 'Primer Piso', 'capacity': MESA_CAPACITY},
    {'code': 'A9', 'block': 'A', 'location': 'Primer Piso', 'capacity': MESA_CAPACITY},
    {'code': 'A10', 'block': 'A', 'location': 'Primer Piso', 'capacity': MESA_CAPACITY},
    {'code': 'A11', 'block': 'A', 'location': 'Primer Piso', 'capacity': MESA_CAPACITY},
    {'code': 'A12', 'block': 'A', 'location': 'Segundo Piso', 'capacity': MESA_CAPACITY},
    {'code': 'A13', 'block': 'A', 'location': 'Segundo Piso', 'capacity': MESA_CAPACITY},
    {'code': 'A14', 'block': 'A', 'location': 'Segundo Piso', 'capacity': MESA_CAPACITY},
    {'code': 'A15', 'block': 'A', 'location': 'Segundo Piso', 'capacity': MESA_CAPACITY},
    {'code': 'A16', 'block': 'A', 'location': 'Segundo Piso', 'capacity': MESA_CAPACITY},
    {'code': 'L11', 'block': 'L', 'location': 'Tercer Piso', 'capacity': MESA_CAPACITY},
    {'code': 'L12', 'block': 'L', 'location': 'Tercer Piso', 'capacity': MESA_CAPACITY},
    {'code': 'L13', 'block': 'L', 'location': 'Tercer Piso', 'capacity': MESA_CAPACITY},
    {'code': 'L15', 'block': 'L', 'location': 'Tercer Piso', 'capacity': MESA_CAPACITY},
    {'code': 'A5', 'block': 'A', 'location': 'Planta Baja', 'capacity': MESA_CAPACITY},
    {'code': 'A6', 'block': 'A', 'location': 'Planta Baja', 'capacity': MESA_CAPACITY}
)

# Fixed number of mesas (tables) allocated to each thematic axis. Option A chosen
# by the event owner (2026-07-10): allocation is set by axis importance, not by
# live demand. ADJUST these counts by importance; they MUST sum to the number of
# aulas (len(AULAS_SEED) = 17). The allocation is validated at runtime.
MESA_ALLOCATION: dict[ThematicAxis, int] = {
    ThematicAxis.SEGURIDAD_JURIDICA: 3,
    ThematicAxis.CONTRATOS: 3,
    ThematicAxis.INSTITUCIONALIDAD: 3,
    ThematicAxis.MEDIO_AMBIENTE: 3,
    ThematicAxis.COMERCIALIZACION: 3,
    ThematicAxis.DESARROLLO_PRODUCTIVO: 2
}


def resolve_role(category: InstitutionCategory) -> ParticipantRole:
    '''
        Resolves the participant role for a given institutional category.

        Args:
            category (InstitutionCategory): The institution's category.

        Returns:
            ParticipantRole: The functional role for that category.
    '''
    return CATEGORY_ROLE_MAP[category]


def resolve_assignment_type(role: ParticipantRole) -> AssignmentType:
    '''
        Resolves the seat-assignment type for a given participant role.

        Args:
            role (ParticipantRole): The participant's functional role.

        Returns:
            AssignmentType: FIJO for seated roles, ROTATIVO otherwise.
    '''
    return ROLE_ASSIGNMENT_MAP[role]
