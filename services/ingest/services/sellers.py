'''
    The seller master — who sells, stated once.

    The files name a seller the way the owner's ERP does —"Ana", "V-017"— and
    the same person signs in to the product with an email. Routes needs to know
    they are the same person: the plan comes from Ana's portfolio in the file,
    and the phone that runs it belongs to ana@empresa.com. That link is made
    here, once, by a manager, instead of every module guessing it.

    Same rule as the client master: a seller the files mention and the master
    does not know is CREATED; one already there is NOT rewritten. Linking a
    seller to a user is a separate, explicit act.
'''
from typing import List, Optional

import pandas as pd
from boto3.resources.base import ServiceResource

from models.sellers import SellerItem
from schemas.clients import ClientSource
from schemas.sellers import (
    SellerError,
    SellerListResponseSchema,
    SellerResponseSchema,
    SellerUpdateSchema
)
from services.crud import find_item_by_key, query_by_partition
from services.environment import load_and_validate_env_vars
from services.exceptions import ResourceNotFoundError
from services.logger_config import custom_logger as logger
from services.utils import get_current_time_gmt

ENV_VARS = load_and_validate_env_vars({'DYNAMODB_TABLE_NAME_INGEST_SELLERS': str})
SELLERS_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_INGEST_SELLERS']

# The column every transaction contract uses for the seller.
SELLER_COLUMN = 'seller'


def to_seller_response(item: SellerItem) -> SellerResponseSchema:
    '''
        Shapes a stored seller for the API.

        Args:
            item (SellerItem): The stored seller.

        Returns:
            SellerResponseSchema: The seller as the API returns it.
    '''
    return SellerResponseSchema(
        id = item['id'],
        name = item.get('name') or item['id'],
        user_email = item.get('user_email'),
        source = ClientSource(item.get('source') or ClientSource.FILE.value),
        created_at = item['created_at'],
        updated_at = item['updated_at']
    )


def list_sellers(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    user_email: Optional[str] = None
) -> List[SellerItem]:
    '''
        The owner's sellers, optionally only the ones linked to one user.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account that owns the data.
            user_email (Optional[str]): Keep only the sellers this user is.

        Returns:
            List[SellerItem]: Matching sellers, by code.
    '''
    items = query_by_partition(
        dynamodb_resource = dynamodb_resource,
        table_name = SELLERS_TABLE,
        partition_key = 'owner_email',
        partition_value = owner_email
    )
    if user_email:
        wanted = user_email.strip().lower()
        items = [item for item in items
                 if str(item.get('user_email') or '').lower() == wanted]
    return sorted(items, key = lambda item: item['id'])


def to_seller_list_response(items: List[SellerItem]) -> SellerListResponseSchema:
    '''
        Wraps a list of sellers with how many can already sign in.

        Args:
            items (List[SellerItem]): Stored sellers.

        Returns:
            SellerListResponseSchema: The list and its counts.
    '''
    sellers = [to_seller_response(item) for item in items]
    return SellerListResponseSchema(
        sellers = sellers,
        total = len(sellers),
        linked = sum(1 for seller in sellers if seller.user_email)
    )


def sellers_from_frame(frame: pd.DataFrame) -> List[str]:
    '''
        The distinct sellers a validated frame mentions.

        Args:
            frame (pd.DataFrame): Validated sales or visits frame.

        Returns:
            List[str]: Seller codes, trimmed and without blanks.
    '''
    if frame.empty or SELLER_COLUMN not in frame.columns:
        return []
    names = frame[SELLER_COLUMN].dropna().astype(str).str.strip()
    return sorted({name for name in names if name})


def register_sellers(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    sellers: List[str],
    source: ClientSource
) -> int:
    '''
        Creates the sellers the master does not know yet. Never rewrites one.

        A seller has nothing for a file to complete —its name is its code until
        a manager says otherwise—, so a known seller is simply left alone.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account that owns the data.
            sellers (List[str]): Seller codes found in a load.
            source (ClientSource): Which door they came through.

        Returns:
            int: How many were created.
    '''
    if not sellers:
        return 0
    known = {item['id'] for item in list_sellers(dynamodb_resource, owner_email)}
    now = get_current_time_gmt().isoformat()
    table = dynamodb_resource.Table(SELLERS_TABLE)
    created = 0
    for code in sellers:
        if code in known:
            continue
        table.put_item(Item = {
            'owner_email': owner_email, 'id': code, 'name': code,
            'source': source.value, 'created_at': now, 'updated_at': now
        })
        created += 1
    message = (f'Seller master of {owner_email} fed from {source.value}: '
               f'{created} created, {len(sellers) - created} already known.')
    logger.info(message)
    return created


def update_seller(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    seller_id: str,
    changes: SellerUpdateSchema
) -> SellerItem:
    '''
        States who a seller is: their display name and the user they sign in as.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account that owns the data.
            seller_id (str): Seller code.
            changes (SellerUpdateSchema): Attributes to overwrite.

        Returns:
            SellerItem: The stored seller after the change.

        Raises:
            ResourceNotFoundError: SELLER_NOT_FOUND when it is not the owner's.
    '''
    stored = find_item_by_key(
        dynamodb_resource = dynamodb_resource,
        table_name = SELLERS_TABLE,
        key = {'owner_email': owner_email, 'id': seller_id}
    )
    if not stored:
        error_msg = f'Seller {seller_id} not found for {owner_email}.'
        logger.warning(error_msg)
        raise ResourceNotFoundError(detail = SellerError.SELLER_NOT_FOUND.value)

    update = changes.model_dump(exclude_unset = True)
    if 'user_email' in update and update['user_email']:
        update['user_email'] = update['user_email'].strip().lower()
    stored.update(update)
    stored['updated_at'] = get_current_time_gmt().isoformat()
    dynamodb_resource.Table(SELLERS_TABLE).put_item(Item = stored)
    message = f'Seller {seller_id} of {owner_email} updated.'
    logger.info(message)
    return stored
