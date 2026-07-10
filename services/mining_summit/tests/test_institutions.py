'''
    services/mining_summit/tests/test_institutions.py

    Unit tests for the institutions reference catalog and the category-to-role
    resolution rules. They run without AWS access (static bundled catalog).
'''
import pytest

from schemas.enums import (
    AssignmentType,
    InstitutionCategory,
    ParticipantRole
)
from services.exceptions import RegisterNotFoundError
from services.institutions import get_institution, list_institutions
from services.summit_rules import (
    CATEGORY_ROLE_MAP,
    ROLE_ASSIGNMENT_MAP,
    resolve_assignment_type,
    resolve_role
)


def test_catalog_has_all_institutions_and_total_cupos():
    '''
        The bundled catalog must expose the 72 official institutions summing the
        742 planned cupos, and every category must resolve (no ValueError).
    '''
    items = list_institutions()
    assert len(items) == 72
    assert sum(item['cupos'] for item in items) == 742


def test_every_category_maps_to_a_role_and_assignment():
    '''
        The rule maps must be exhaustive over categories and roles so no
        institution can end up without a resolved role/assignment.
    '''
    assert set(CATEGORY_ROLE_MAP) == set(InstitutionCategory)
    assert set(ROLE_ASSIGNMENT_MAP) == set(ParticipantRole)


def test_role_and_assignment_derivation_for_known_institution():
    '''
        A productive-actor institution is a PARTICIPANTE holding a FIJO seat.
    '''
    fencomin = get_institution('federacion-nacional-de-cooperativas-mineras-de-bolivia-fencomin')
    assert fencomin['category'] == InstitutionCategory.ACTORES_PRODUCTIVOS.value
    assert fencomin['role'] == ParticipantRole.PARTICIPANTE.value
    assert fencomin['assignment_type'] == AssignmentType.FIJO.value


def test_observer_category_is_rotating():
    '''
        Academic-sector institutions are VEEDOR and therefore ROTATIVO.
    '''
    academics = list_institutions(category = InstitutionCategory.SECTOR_ACADEMICO.value)
    assert academics
    assert all(item['role'] == ParticipantRole.VEEDOR.value for item in academics)
    assert all(item['assignment_type'] == AssignmentType.ROTATIVO.value for item in academics)


def test_filter_by_role_returns_only_matching_role():
    '''
        Filtering by the ORGANIZADOR role must exclude any seated participant.
    '''
    organizers = list_institutions(role = ParticipantRole.ORGANIZADOR.value)
    assert organizers
    assert all(item['role'] == ParticipantRole.ORGANIZADOR.value for item in organizers)


def test_get_institution_unknown_id_raises_not_found():
    '''
        An unknown institution id must raise RegisterNotFoundError (HTTP 404).
    '''
    with pytest.raises(RegisterNotFoundError):
        get_institution('this-institution-does-not-exist')


def test_resolvers_are_consistent_with_maps():
    '''
        The resolver helpers must agree with the underlying reference maps.
    '''
    role = resolve_role(InstitutionCategory.ORGANO_LEGISLATIVO)
    assert role is ParticipantRole.MODERADOR
    assert resolve_assignment_type(role) is AssignmentType.FIJO
