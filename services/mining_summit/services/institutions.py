'''
    Business logic for the Institutions reference catalog of the Mining Summit.

    The catalog is static reference data bundled as data/institutions.json. It is
    served read-only; role and seat-assignment type are derived per entry from
    the category so the rules stay single-sourced in summit_rules.
'''
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from schemas.enums import InstitutionCategory
from services.exceptions import RegisterNotFoundError
from services.summit_rules import resolve_assignment_type, resolve_role

CATALOG_PATH = Path(__file__).resolve().parent.parent / 'data' / 'institutions.json'


@lru_cache(maxsize = 1)
def _load_catalog() -> tuple[Dict[str, Any], ...]:
    '''
        Loads and caches the bundled institutions catalog from disk.

        Returns:
            tuple[Dict[str, Any], ...]: Immutable sequence of raw entries.
    '''
    raw = CATALOG_PATH.read_text(encoding = 'utf-8')
    return tuple(json.loads(raw))


def _enrich(institution: Dict[str, Any]) -> Dict[str, Any]:
    '''
        Adds the derived role and seat-assignment type to a catalog entry.

        Args:
            institution (Dict[str, Any]): Raw catalog entry.

        Returns:
            Dict[str, Any]: Entry including 'role' and 'assignment_type'.
    '''
    role = resolve_role(InstitutionCategory(institution['category']))
    return {
        **institution,
        'role': role.value,
        'assignment_type': resolve_assignment_type(role).value
    }


def list_institutions(
    category: Optional[str] = None,
    role: Optional[str] = None
) -> List[Dict[str, Any]]:
    '''
        Returns the enriched catalog, optionally filtered by category and role.

        Args:
            category (Optional[str]): Category value to filter by.
            role (Optional[str]): Derived role value to filter by.

        Returns:
            List[Dict[str, Any]]: Matching enriched institutions.
    '''
    items = [_enrich(item) for item in _load_catalog()]
    if category:
        items = [item for item in items if item['category'] == category]
    if role:
        items = [item for item in items if item['role'] == role]
    return items


def get_institution(institution_id: str) -> Dict[str, Any]:
    '''
        Returns a single enriched institution by id.

        Args:
            institution_id (str): The institution slug identifier.

        Returns:
            Dict[str, Any]: The enriched institution entry.

        Raises:
            RegisterNotFoundError: If no institution matches the id.
    '''
    for item in _load_catalog():
        if item['id'] == institution_id:
            return _enrich(item)
    raise RegisterNotFoundError(detail = f'Institution not found: {institution_id}')
