'''
    Tests for the supplier (proveedores) CRUD and its link to the Nota de
    Ingreso, including the rules that protect already-issued documents.
'''
import asyncio
import pytest

from controllers.supplier import (
    create_supplier_controller,
    delete_supplier_controller,
    list_suppliers_controller,
    update_supplier_controller,
)
from schemas.supplier import (
    SupplierCreateSchema,
    SupplierFilterSchema,
    SupplierUpdateSchema,
)
from services.exceptions import (
    InvalidInputError,
    RegisterAlreadyExistsError,
    RegisterNotFoundError,
)
from tests.conftest import make_catalog_item, register_entry


def _supplier_payload(name = 'COMERCIAL ANDINA SRL', nit = '1023456789') -> SupplierCreateSchema:
    '''
        Valid supplier payload; the email is the only optional field.
    '''
    return SupplierCreateSchema(
        name = name,
        nit = nit,
        contact_person = 'Maria Quispe',
        address = 'Av. Mariscal Santa Cruz 1234',
        phone = '22123456',
    )


def test_create_supplier_without_email(db_session):
    '''Email is the only optional field.'''
    created = asyncio.run(create_supplier_controller(db_session, _supplier_payload()))

    assert created.id > 0
    assert created.email is None
    assert created.is_active is True


def test_duplicate_nit_is_rejected(db_session):
    '''The NIT identifies the vendor, so it cannot repeat.'''
    asyncio.run(create_supplier_controller(db_session, _supplier_payload()))

    with pytest.raises(RegisterAlreadyExistsError):
        asyncio.run(create_supplier_controller(
            db_session, _supplier_payload(name = 'OTRA EMPRESA SRL')))


def test_listing_filters_by_text_and_active_flag(db_session):
    '''Search covers name, NIT and contact; only_active hides deactivated ones.'''
    asyncio.run(create_supplier_controller(db_session, _supplier_payload()))
    other = asyncio.run(create_supplier_controller(
        db_session, _supplier_payload(name = 'PAPELERA DEL SUR', nit = '9988776655')))
    asyncio.run(update_supplier_controller(
        db_session, other.id, SupplierUpdateSchema(is_active = False)))

    by_text = asyncio.run(list_suppliers_controller(
        db_session, SupplierFilterSchema(search = 'papelera')))
    only_active = asyncio.run(list_suppliers_controller(
        db_session, SupplierFilterSchema(only_active = True)))

    assert [s.name for s in by_text] == ['PAPELERA DEL SUR']
    assert [s.name for s in only_active] == ['COMERCIAL ANDINA SRL']


def test_entry_stores_the_supplier_name_as_a_snapshot(db_session):
    '''Renaming a vendor must not rewrite the notes it already issued.'''
    item = make_catalog_item(db_session)
    supplier = asyncio.run(create_supplier_controller(db_session, _supplier_payload()))
    entry = register_entry(db_session, item, 10, 2, supplier.id)

    asyncio.run(update_supplier_controller(
        db_session, supplier.id, SupplierUpdateSchema(name = 'NUEVO NOMBRE SRL')))

    assert entry.supplier_id == supplier.id
    assert entry.supplier == 'COMERCIAL ANDINA SRL'


def test_entry_against_unknown_supplier_fails(db_session):
    '''An entry cannot point at a vendor that does not exist.'''
    item = make_catalog_item(db_session)

    with pytest.raises(RegisterNotFoundError):
        register_entry(db_session, item, 10, 2, supplier_id = 999)


def test_entry_against_deactivated_supplier_fails(db_session):
    '''A deactivated vendor disappears from new documents.'''
    item = make_catalog_item(db_session)
    supplier = asyncio.run(create_supplier_controller(db_session, _supplier_payload()))
    asyncio.run(update_supplier_controller(
        db_session, supplier.id, SupplierUpdateSchema(is_active = False)))

    with pytest.raises(InvalidInputError):
        register_entry(db_session, item, 10, 2, supplier.id)


def test_supplier_with_documents_cannot_be_deleted(db_session):
    '''History wins over cleanup: such a vendor must be deactivated.'''
    item = make_catalog_item(db_session)
    supplier = asyncio.run(create_supplier_controller(db_session, _supplier_payload()))
    register_entry(db_session, item, 10, 2, supplier.id)

    with pytest.raises(InvalidInputError):
        asyncio.run(delete_supplier_controller(db_session, supplier.id))


def test_unused_supplier_can_be_deleted(db_session):
    '''A vendor registered by mistake can still be removed.'''
    supplier = asyncio.run(create_supplier_controller(db_session, _supplier_payload()))

    removed = asyncio.run(delete_supplier_controller(db_session, supplier.id))
    remaining = asyncio.run(list_suppliers_controller(db_session, SupplierFilterSchema()))

    assert removed == supplier.id
    assert remaining == []
