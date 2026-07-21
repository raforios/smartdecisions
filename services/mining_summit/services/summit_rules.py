'''
    Business reference rules for the Mining Summit.

    Single source of truth for the thematic axes, the campus aulas and their
    allocation. The participant role is no longer derived from the institution:
    it belongs to each person and is supplied per row in the ETL or picked in
    the registration form.
'''
from schemas.enums import ParticipantRole, ThematicAxis

# Roles that are registered but never take an aula seat until a real role is
# assigned. Used to gate seat assignment (see participants.create_participant).
UNSEATED_ROLES: frozenset[str] = frozenset({ParticipantRole.SIN_ROL.value})

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

# The 21 campus rooms assigned to the summit (updated list, 2026-07-17), with
# per-aula capacities: 15 x 35 + 32 + 24 + 25 + 22 + 20 + 21 = 669 seats. Order is
# preserved from the source layout and drives the axis allocation below.
AULAS_SEED: tuple[dict[str, str | int], ...] = (
    {'code': 'A3', 'block': 'A', 'location': '', 'capacity': 35},
    {'code': 'A7', 'block': 'A', 'location': '', 'capacity': 35},
    {'code': 'A8', 'block': 'A', 'location': '', 'capacity': 35},
    {'code': 'A9', 'block': 'A', 'location': '', 'capacity': 35},
    {'code': 'A10', 'block': 'A', 'location': '', 'capacity': 35},
    {'code': 'A11', 'block': 'A', 'location': '', 'capacity': 35},
    {'code': 'A12', 'block': 'A', 'location': '', 'capacity': 35},
    {'code': 'A13', 'block': 'A', 'location': '', 'capacity': 35},
    {'code': 'A14', 'block': 'A', 'location': '', 'capacity': 35},
    {'code': 'A15', 'block': 'A', 'location': '', 'capacity': 35},
    {'code': 'A16', 'block': 'A', 'location': '', 'capacity': 35},
    {'code': 'L11', 'block': 'L', 'location': '', 'capacity': 35},
    {'code': 'L12', 'block': 'L', 'location': '', 'capacity': 35},
    {'code': 'L13', 'block': 'L', 'location': '', 'capacity': 35},
    {'code': 'L15', 'block': 'L', 'location': '', 'capacity': 35},
    {'code': 'A5', 'block': 'A', 'location': '', 'capacity': 32},
    {'code': 'A6', 'block': 'A', 'location': '', 'capacity': 24},
    {'code': 'C2', 'block': 'C', 'location': '', 'capacity': 25},
    {'code': 'L14', 'block': 'L', 'location': '', 'capacity': 22},
    {'code': 'L10', 'block': 'L', 'location': '', 'capacity': 20},
    {'code': 'PRISMA', 'block': 'PRISMA', 'location': '', 'capacity': 21}
)

# Fixed number of mesas (aulas) allocated to each thematic axis. Balanced split
# chosen by the event owner (2026-07-17): 4/4/4/3/3/3. They MUST sum to the number
# of aulas (len(AULAS_SEED) = 21). The allocation is validated at runtime.
MESA_ALLOCATION: dict[ThematicAxis, int] = {
    ThematicAxis.SEGURIDAD_JURIDICA: 4,
    ThematicAxis.CONTRATOS: 4,
    ThematicAxis.INSTITUCIONALIDAD: 4,
    ThematicAxis.MEDIO_AMBIENTE: 3,
    ThematicAxis.COMERCIALIZACION: 3,
    ThematicAxis.DESARROLLO_PRODUCTIVO: 3
}
