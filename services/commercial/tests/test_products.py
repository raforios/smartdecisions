'''
    Tests for the product master: keyed by the supplier's SKU, fed by the API
    and by the sales rows that name a SKU, under the rule every master
    follows —create what is missing, complete what is empty, never overwrite.
'''
import asyncio
from typing import Any

import pandas as pd
import pytest
from pydantic import ValidationError

from core.exceptions import ResourceNotFoundError
from controllers import products as controllers
from schemas.products import (
    ProductBulkUpsertSchema,
    ProductListResponseSchema,
    ProductResponseSchema,
    ProductSource,
    ProductUpdateSchema,
    ProductUpsertResultSchema,
    ProductUpsertSchema
)
from services import products as master
from tests.test_clients import OWNER, resource_fixture # pylint: disable=unused-import


def _run(coroutine: Any) -> Any:
    '''
        Runs a controller coroutine to completion.

        Args:
            coroutine (Any): The controller call.

        Returns:
            Any: Whatever the controller returns.
    '''
    return asyncio.run(coroutine)


def _stored(
    resource: Any,
    sku: str
) -> dict[str, Any] | None:
    '''
        Reads one product straight out of the double.

        Args:
            resource (Any): DynamoDB double.
            sku (str): The product's SKU.

        Returns:
            dict[str, Any] | None: The stored row.
    '''
    return resource.tables.get(master.PRODUCTS.name, {}).get((OWNER, sku))


def test_a_load_creates_completes_and_never_overwrites(resource):
    '''
        The first load creates; a later one fills only what is empty and
        leaves the stored values as they were.
    '''
    first = master.upsert_products(resource, OWNER, [ProductUpsertSchema(
        sku = 'VIT-C-500', description = 'Vitamina C 500 mg', unit = 'BOX')], ProductSource.API)
    second = master.upsert_products(resource, OWNER, [ProductUpsertSchema(
        sku = 'VIT-C-500', description = 'Otro nombre', brand = 'Bago',
        suggested_price = 25.5)], ProductSource.FILE)
    again = master.upsert_products(resource, OWNER, [ProductUpsertSchema(
        sku = 'VIT-C-500', description = 'Vitamina C 500 mg')], ProductSource.API)

    stored = _stored(resource, 'VIT-C-500')
    assert (first.created, second.completed, again.unchanged) == (1, 1, 1)
    assert stored['description'] == 'Vitamina C 500 mg'
    assert stored['brand'] == 'Bago' and stored['unit'] == 'BOX'
    assert stored['source'] == 'API'


def test_the_unit_is_a_closed_catalogue():
    '''A unit outside the catalogue is refused, so 'caja' cannot split in three.'''
    with pytest.raises(ValidationError):
        ProductUpsertSchema(sku = 'A', description = 'A', unit = 'CJ')


def test_a_sales_frame_teaches_only_the_rows_with_a_sku():
    '''
        A row whose identifier is its own name has no SKU and stays out; a SKU
        repeated across rows enters once.
    '''
    frame = pd.DataFrame({
        'product_id': ['SKU-1', 'SKU-1', 'Galleta'],
        'product_name': ['Leche 1 L', 'Leche 1 L', 'Galleta'],
        'category': ['Lacteos', 'Lacteos', None]
    })

    products = master.products_from_frame(frame)

    assert [(p.sku, p.description, p.category) for p in products] == [
        ('SKU-1', 'Leche 1 L', 'Lacteos')]


def test_the_master_fills_what_a_sale_left_blank(resource):
    '''
        A sale that names the SKU but not the category gets it from the
        master; a cell the file did fill keeps its value.
    '''
    master.upsert_products(resource, OWNER, [ProductUpsertSchema(
        sku = 'SKU-1', description = 'Leche 1 L', category = 'Lacteos')], ProductSource.API)
    frame = pd.DataFrame({'product_id': ['SKU-1', 'SKU-1'],
                          'product_name': ['Leche 1 L', 'Leche entera'],
                          'category': [None, 'Bebidas']})

    synced = master.sync_products(resource, OWNER, frame, ProductSource.FILE)

    assert list(synced['category']) == ['Lacteos', 'Bebidas']
    assert list(synced['product_name']) == ['Leche 1 L', 'Leche entera']


def test_a_frame_without_products_leaves_the_master_alone():
    '''Visits name no product: the master is not even asked.'''
    frame = pd.DataFrame({'pos_id': ['PDV-1']})
    assert master.sync_products(None, OWNER, frame, ProductSource.FILE) is frame


def test_the_controllers_return_their_models(resource):
    '''The API door, the list, the read and the correction, as the endpoints run them.'''
    loaded = _run(controllers.upsert_products_controller(
        dynamodb_resource = resource, current_user = OWNER, request = None,
        payload = ProductBulkUpsertSchema(products = [
            ProductUpsertSchema(sku = 'SKU-1', description = 'Leche 1 L', unit = 'LITER')])))
    listed = _run(controllers.list_products_controller(resource, OWNER, None))
    corrected = _run(controllers.update_product_controller(
        resource, 'SKU-1', ProductUpdateSchema(suggested_price = 9.5), OWNER, None))
    one = _run(controllers.get_product_controller(resource, 'SKU-1', OWNER, None))

    assert isinstance(loaded, ProductUpsertResultSchema) and loaded.created == 1
    assert isinstance(listed, ProductListResponseSchema) and listed.total == 1
    assert isinstance(corrected, ProductResponseSchema) and corrected.suggested_price == 9.5
    assert one.unit.value == 'LITER' and one.description == 'Leche 1 L'


def test_another_owners_product_does_not_exist(resource):
    '''A product of another account answers as one that does not exist.'''
    master.upsert_products(resource, 'other@bearsoft.com.bo', [ProductUpsertSchema(
        sku = 'SKU-1', description = 'Leche')], ProductSource.API)
    with pytest.raises(ResourceNotFoundError):
        master.get_product(resource, OWNER, 'SKU-1')


def test_the_api_door_carries_the_sku_as_the_file_does():
    '''
        A pushed line with a SKU is known by it; one without is known by its
        name, exactly as a file row.
    '''
    # pylint: disable=import-outside-toplevel
    from controllers.common import rows_frame
    from schemas.channels import SaleRowSchema
    from services.commercial import prepare_rows as prepare_sales_rows

    frame = prepare_sales_rows(rows_frame([
        SaleRowSchema(date = '2026-11-01', order_id = 'F-1', product_id = 'SKU-1',
                      product_name = 'Leche 1 L', quantity = 2),
        SaleRowSchema(date = '2026-11-01', order_id = 'F-2', product_name = 'Galleta',
                      quantity = 1)
    ]))

    assert list(frame['product_id']) == ['SKU-1', 'Galleta']
    assert [p.sku for p in master.products_from_frame(frame)] == ['SKU-1']
