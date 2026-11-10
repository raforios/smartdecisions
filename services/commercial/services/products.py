'''
    The product master — what is sold, stated once, keyed by the SKU of the
    producer, distributor or supplier (Rafael, 5-nov-2026).

    Two doors feed it under the rule every master follows
    (`services/master_records.py`): the owner's system through the API, and
    the sales file whose rows name a SKU. A product that is not there is
    created; one that is there only gets its empty fields filled in.
    Correcting a stored value is `update_product`, a separate act.

    Reading goes the other way: what a sales row omits about its product —the
    description, the category— is taken from the master.
'''
from typing import Any

import pandas as pd
from boto3.resources.base import ServiceResource

from core.crud import find_item_by_key, query_by_partition
from core.environment import load_and_validate_env_vars
from core.exceptions import ResourceNotFoundError
from core.logger_config import custom_logger as logger
from core.utils import get_current_time_gmt
from models.products import ProductItem
from schemas.products import (
    ProductError,
    ProductListResponseSchema,
    ProductResponseSchema,
    ProductSource,
    ProductUpdateSchema,
    ProductUpsertResultSchema,
    ProductUpsertSchema
)
from services.commercial_utils import from_dynamo, to_dynamo
from services.master_records import MasterTable, clean_attributes, feed_master, is_empty

ENV_VARS = load_and_validate_env_vars({'DYNAMODB_TABLE_NAME_COMMERCIAL_PRODUCTS': str})
PRODUCTS = MasterTable(name = ENV_VARS['DYNAMODB_TABLE_NAME_COMMERCIAL_PRODUCTS'], key = 'sku')

# How a product is named inside a validated sales frame, and what the master
# fills in where a row left it blank: its description and its category.
SKU_COLUMN = 'product_id'
NAME_COLUMN = 'product_name'
_FRAME_ATTRIBUTES: dict[str, str] = {'description': NAME_COLUMN, 'category': 'category'}


def to_product_response(item: ProductItem) -> ProductResponseSchema:
    '''
        Turns a stored product into its DTO.

        Args:
            item (ProductItem): Item as DynamoDB returned it.

        Returns:
            ProductResponseSchema: The product as the API publishes it.
    '''
    return ProductResponseSchema(**from_dynamo(
        {key: value for key, value in item.items() if key != 'owner_email'}))


def get_product(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    sku: str
) -> ProductItem:
    '''
        One product of the owner's master.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account that owns the data.
            sku (str): The product's SKU.

        Returns:
            ProductItem: The stored product.

        Raises:
            ResourceNotFoundError: PRODUCT_NOT_FOUND when it is not the owner's.
    '''
    item = find_item_by_key(dynamodb_resource = dynamodb_resource, table_name = PRODUCTS.name,
                            key = {'owner_email': owner_email, 'sku': sku})
    if not item:
        error_msg = f'Product {sku} not found for {owner_email}.'
        logger.warning(error_msg)
        raise ResourceNotFoundError(detail = ProductError.PRODUCT_NOT_FOUND.value)
    return item


def list_products(
    dynamodb_resource: ServiceResource,
    owner_email: str
) -> ProductListResponseSchema:
    '''
        The owner's products, by SKU.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account that owns the data.

        Returns:
            ProductListResponseSchema: The products and how many.
    '''
    items = sorted(query_by_partition(dynamodb_resource = dynamodb_resource,
                                      table_name = PRODUCTS.name, partition_key = 'owner_email',
                                      partition_value = owner_email),
                   key = lambda item: item['sku'])
    products = [to_product_response(item) for item in items]
    return ProductListResponseSchema(products = products, total = len(products))


def suggested_prices(
    dynamodb_resource: ServiceResource,
    owner_email: str
) -> dict[str, float]:
    '''
        The supplier's suggested price of each of the owner's products that
        has one.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account that owns the data.

        Returns:
            dict[str, float]: Bolivianos per SKU.
    '''
    return {product.sku: product.suggested_price
            for product in list_products(dynamodb_resource, owner_email).products
            if product.suggested_price}


def upsert_products(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    products: list[ProductUpsertSchema],
    source: ProductSource
) -> ProductUpsertResultSchema:
    '''
        Feeds the master: creates what is missing and completes what is empty.
        A SKU repeated in one load is merged first, the earlier values winning.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account that owns the data.
            products (list[ProductUpsertSchema]): Products to feed in.
            source (ProductSource): The door they came through.

        Returns:
            ProductUpsertResultSchema: Created, completed and unchanged counts.
    '''
    records: dict[str, dict[str, Any]] = {}
    for candidate in products:
        merged = records.setdefault(candidate.sku, {})
        for key, value in clean_attributes(
                candidate.model_dump(mode = 'json', exclude = {'sku'})).items():
            if is_empty(merged.get(key)):
                merged[key] = value
    load = feed_master(dynamodb_resource, PRODUCTS, owner_email, records, source.value)
    return ProductUpsertResultSchema(created = load.created, completed = load.completed,
                                     unchanged = load.unchanged)


def update_product(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    sku: str,
    changes: ProductUpdateSchema
) -> ProductItem:
    '''
        Corrects a product already in the master, overwriting what it names;
        fields left out are untouched.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account that owns the data.
            sku (str): The product's SKU.
            changes (ProductUpdateSchema): Attributes to overwrite.

        Returns:
            ProductItem: The stored product after the change.

        Raises:
            ResourceNotFoundError: PRODUCT_NOT_FOUND when it is not the owner's.
    '''
    stored = get_product(dynamodb_resource, owner_email, sku)
    stored.update(to_dynamo(changes.model_dump(mode = 'json', exclude_unset = True)))
    stored['updated_at'] = get_current_time_gmt().isoformat()
    dynamodb_resource.Table(PRODUCTS.name).put_item(Item = stored)
    message = f'Product {sku} of {owner_email} corrected.'
    logger.info(message)
    return stored


def products_from_frame(frame: pd.DataFrame) -> list[ProductUpsertSchema]:
    '''
        The products a validated sales frame names by SKU, each once.

        A row without a SKU has its name for an identifier; it is not a SKU,
        so it does not enter the master.

        Args:
            frame (pd.DataFrame): Validated sales frame.

        Returns:
            list[ProductUpsertSchema]: One entry per SKU.
    '''
    if frame.empty or SKU_COLUMN not in frame.columns or NAME_COLUMN not in frame.columns:
        return []
    named = frame[frame[SKU_COLUMN].astype(str) != frame[NAME_COLUMN].astype(str)]
    columns = [SKU_COLUMN] + [column for column in _FRAME_ATTRIBUTES.values()
                              if column in frame.columns]
    rows = named[list(dict.fromkeys(columns))].drop_duplicates(subset = [SKU_COLUMN],
                                                                keep = 'last')
    products: list[ProductUpsertSchema] = []
    for record in rows.to_dict(orient = 'records'):
        sku, name = record.get(SKU_COLUMN), record.get(NAME_COLUMN)
        if is_empty(sku):
            continue
        products.append(ProductUpsertSchema(
            sku = str(sku), description = str(name) if not is_empty(name) else str(sku),
            category = None if is_empty(record.get('category')) else str(record['category'])))
    return products


def enrich_frame(
    frame: pd.DataFrame,
    master: list[ProductResponseSchema]
) -> pd.DataFrame:
    '''
        Fills in what a sales file did not say about its products, from the
        master; a cell the file did fill keeps its value.

        Args:
            frame (pd.DataFrame): Validated sales frame.
            master (list[ProductResponseSchema]): The owner's products.

        Returns:
            pd.DataFrame: The same frame with its product blanks filled.
    '''
    if frame.empty or not master or SKU_COLUMN not in frame.columns:
        return frame
    known = {product.sku: product for product in master}
    skus = frame[SKU_COLUMN].astype(str)
    for field, column in _FRAME_ATTRIBUTES.items():
        replacement = skus.map(lambda sku, field = field: getattr(known.get(sku), field, None))
        blank = (frame[column].isna() if column in frame.columns
                 else pd.Series(True, index = frame.index))
        fillable = blank & replacement.notna()
        if fillable.any():
            frame.loc[fillable, column] = replacement[fillable]
    return frame


def sync_products(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    frame: pd.DataFrame,
    source: ProductSource
) -> pd.DataFrame:
    '''
        Runs both directions of the master against one validated sales frame:
        the frame teaches the master the SKUs it names, then the master fills
        the frame's blanks.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account that owns the data.
            frame (pd.DataFrame): Validated sales frame.
            source (ProductSource): The door the frame came through.

        Returns:
            pd.DataFrame: The frame with its product blanks filled.
    '''
    # Visits and collections name no product: the master is not asked.
    if frame.empty or SKU_COLUMN not in frame.columns:
        return frame
    named = products_from_frame(frame)
    if named:
        upsert_products(dynamodb_resource, owner_email, named, source)
    return enrich_frame(frame, list_products(dynamodb_resource, owner_email).products)
