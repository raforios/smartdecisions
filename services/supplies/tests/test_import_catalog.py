'''
    Unit tests for the catalog importer (scripts/import_catalog.py).

    These cover the pure mapping logic and validate the real source CSV files
    so the import cannot silently drop rows or leak the legacy 'Codel old'
    column into the new catalog. The scripts/ directory is put on sys.path by
    tests/__init__.py.
'''
import csv
import os

# tests/__init__.py puts scripts/ on sys.path at runtime; Pylint analyses
# statically and cannot follow that, hence the disable.
import import_catalog  # pylint: disable=import-error

_DOCS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'docs')


def _read(name: str) -> list[dict[str, str]]:
    '''
        Reads one of the source CSV files under docs/ into row dicts.
    '''
    with open(os.path.join(_DOCS_DIR, name), encoding = 'utf-8-sig') as handle:
        return list(csv.DictReader(handle))


def test_is_active_maps_estado():
    '''Only the literal "ACTIVO" (case and padding aside) means active.'''
    assert import_catalog.is_active('ACTIVO') is True
    assert import_catalog.is_active('  activo ') is True
    assert import_catalog.is_active('INACTIVO') is False
    assert import_catalog.is_active('') is False


def test_build_item_payload_never_includes_old_code():
    '''The legacy code must not reach the new catalog, by key or by value.'''
    row = {
        'Código': '30001',
        'Codel old': '721',
        'Descripción': '  BOTAS DE GOMA; PUNTERA METALICA  ',
        'Unidad de Medida': 'PAR',
        'Cuenta contable': 'CALZADOS',
        'Estado': 'ACTIVO',
    }
    payload = import_catalog.build_item_payload(row, category_id = 5, unit_id = 3)

    assert payload['code'] == '30001'
    assert payload['name'] == 'BOTAS DE GOMA; PUNTERA METALICA'
    assert payload['category_id'] == 5
    assert payload['unit_id'] == 3
    assert payload['is_active'] is True
    assert not any('old' in str(key).lower() for key in payload)
    assert '721' not in payload.values()


def test_articulos_csv_shape_and_no_old_code_data():
    '''The source file carries 382 articles and an entirely empty legacy column.'''
    rows = _read('articulos.csv')
    assert len(rows) == 382
    assert 'Codel old' in rows[0]
    assert all(not row['Codel old'].strip() for row in rows)


def test_every_article_resolves_to_an_accounting_group():
    '''No article may reference a group missing from grupo-contable.csv.'''
    groups = {row['Descripción'].strip().upper() for row in _read('grupo-contable.csv')}
    rows = _read('articulos.csv')
    unresolved = sorted({
        row['Cuenta contable'].strip()
        for row in rows
        if row['Cuenta contable'].strip().upper() not in groups
    })
    assert unresolved == [], f'Accounting groups missing for: {unresolved}'


def test_units_are_derived_and_non_empty():
    '''Every article states a unit of measure, and there are 14 distinct ones.'''
    rows = _read('articulos.csv')
    units = {row['Unidad de Medida'].strip() for row in rows}
    assert '' not in units
    assert len(units) == 14
