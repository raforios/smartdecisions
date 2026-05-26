'''
    CMS admin write services backed by DynamoDB.

    Each entity exposes create / get / update / delete / admin_list. The
    update flow is read-merge-put rather than UpdateExpression to keep
    partial updates trivially correct (two round-trips per write are
    acceptable at the expected admin volume).

    All timestamps are stored as ISO 8601 strings in `America/La_Paz`
    timezone, matching the convention used by the SQL-backed services.
'''
import uuid
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional

from boto3.resources.base import ServiceResource
from botocore.exceptions import ClientError
from pydantic import BaseModel

from models.cms import (
    CMS_NEWS_TABLE,
    CMS_DOCUMENTS_TABLE,
    CMS_SLIDES_TABLE,
    CMS_ENTITIES_TABLE,
)
from services.exceptions import RegisterNotFoundError
from services.logger_config import custom_logger as logger
from services.utils import get_current_time_gmt
from services.cms import _resolve_s3_url, _resolve_asset


# ---------- Generic helpers ----------

def _generate_id() -> str:
    '''
        Returns a 32-char hex uuid used as the partition key for every
        CMS item.
    '''
    return uuid.uuid4().hex


def _now_iso() -> str:
    '''
        Returns the current Bolivia-time as an ISO 8601 string.
    '''
    return get_current_time_gmt().isoformat()


def _serialize_payload(payload: BaseModel,
                       exclude_unset: bool = False) -> Dict[str, Any]:
    '''
        Dumps the Pydantic model to a dict, converting non-DynamoDB-native
        types (datetime, date, float) into safe representations.
    '''
    raw = payload.model_dump(exclude_unset = exclude_unset, mode = 'json')
    return _convert_for_dynamodb(raw)


def _convert_for_dynamodb(value: Any) -> Any:
    '''
        Recursively turns floats into Decimals (DynamoDB rejects floats).
        Datetimes and dates are already converted to ISO strings by
        `model_dump(mode='json')`, so they pass through unchanged.
    '''
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: _convert_for_dynamodb(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_convert_for_dynamodb(v) for v in value]
    return value


def _fetch_item(table, item_id: str) -> Dict[str, Any]:
    '''
        Returns the raw DynamoDB item or raises RegisterNotFoundError.
    '''
    response = table.get_item(Key = {'id': item_id})
    item = response.get('Item')
    if not item:
        message = f'{table.name} item id={item_id} not found.'
        logger.warning(message)
        raise RegisterNotFoundError(detail = message)
    return item


def _scan_all_items(table) -> List[Dict[str, Any]]:
    '''
        Paginated full Scan. Used only by admin listings.
    '''
    items: List[Dict[str, Any]] = []
    scan_kwargs: Dict[str, Any] = {}
    while True:
        response = table.scan(**scan_kwargs)
        items.extend(response.get('Items', []))
        last_key = response.get('LastEvaluatedKey')
        if not last_key:
            break
        scan_kwargs['ExclusiveStartKey'] = last_key
    return items


def _put_new_item(table, payload: BaseModel,
                  extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    '''
        Persists a new item with a generated id and timestamps. Returns
        the stored representation.
    '''
    now = _now_iso()
    item: Dict[str, Any] = _serialize_payload(payload)
    item.update({
        'id': _generate_id(),
        'created_at': now,
        'updated_at': now,
    })
    if extra:
        item.update(extra)
    try:
        table.put_item(
            Item = item,
            ConditionExpression = 'attribute_not_exists(id)',
        )
    except ClientError as e:
        error_msg = f'Failed to create item in {table.name}: {e}'
        logger.error(error_msg, exc_info = True)
        raise
    return item


def _merge_and_put(table, item_id: str, update_payload: BaseModel,
                   _decorate: Optional[Callable[[Dict[str, Any]], None]] = None,
                   ) -> Dict[str, Any]:
    '''
        Fetches the existing item, merges the non-None fields from
        `update_payload`, refreshes `updated_at`, and writes it back.
    '''
    existing = _fetch_item(table, item_id)
    updates = _serialize_payload(update_payload, exclude_unset = True)
    if not updates:
        return existing
    existing.update(updates)
    existing['updated_at'] = _now_iso()
    if _decorate:
        _decorate(existing)
    table.put_item(Item = existing)
    return existing


def _delete(table, item_id: str) -> None:
    '''
        Deletes the item. Raises if not found so the controller can
        return 404.
    '''
    _fetch_item(table, item_id) # validate existence before deleting.
    table.delete_item(Key = {'id': item_id})


def _decorate_with_urls(item: Dict[str, Any]) -> Dict[str, Any]:
    '''
        Attaches the convenience `*_url` fields to a raw DynamoDB item so
        admin responses can render previews without re-resolving on the
        client side. Operates on a shallow copy to keep the caller's dict
        intact.
    '''
    decorated = dict(item)
    if 'image_s3_bucket' in decorated or 'image_s3_key' in decorated:
        decorated['image_url'] = _resolve_s3_url(
            decorated.get('image_s3_bucket'),
            decorated.get('image_s3_key'),
        )
    if 'logo_s3_bucket' in decorated or 'logo_s3_key' in decorated:
        decorated['logo_url'] = _resolve_s3_url(
            decorated.get('logo_s3_bucket'),
            decorated.get('logo_s3_key'),
        )
    if any(k in decorated for k in ('file_s3_bucket', 'file_s3_key',
                                    'file_external_url')):
        decorated['file_url'] = _resolve_asset(
            decorated.get('file_s3_bucket'),
            decorated.get('file_s3_key'),
            decorated.get('file_external_url'),
        )
    return decorated


def _sort_admin_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    '''
        Newest updated first — what an admin panel typically wants.
    '''
    return sorted(items, key = lambda r: r.get('updated_at') or '', reverse = True)


# ---------- News ----------

async def create_news_service(
    dynamodb_resource: ServiceResource, payload: BaseModel,
) -> Dict[str, Any]:
    '''
        Persists a new news entry. Returns the stored item decorated with
        the resolved image URL.
    '''
    table = dynamodb_resource.Table(CMS_NEWS_TABLE)
    item = _put_new_item(table, payload)
    return _decorate_with_urls(item)


async def get_news_service(
    dynamodb_resource: ServiceResource, news_id: str,
) -> Dict[str, Any]:
    '''
        Returns a single news item or raises RegisterNotFoundError.
    '''
    table = dynamodb_resource.Table(CMS_NEWS_TABLE)
    item = _fetch_item(table, news_id)
    return _decorate_with_urls(item)


async def update_news_service(
    dynamodb_resource: ServiceResource, news_id: str, payload: BaseModel,
) -> Dict[str, Any]:
    '''
        Partial update for a news item.
    '''
    table = dynamodb_resource.Table(CMS_NEWS_TABLE)
    item = _merge_and_put(table, news_id, payload)
    return _decorate_with_urls(item)


async def delete_news_service(
    dynamodb_resource: ServiceResource, news_id: str,
) -> None:
    '''
        Deletes a news item by id.
    '''
    table = dynamodb_resource.Table(CMS_NEWS_TABLE)
    _delete(table, news_id)


async def admin_list_news_service(
    dynamodb_resource: ServiceResource,
) -> Dict[str, Any]:
    '''
        Returns every news item (including drafts) sorted newest first.
    '''
    table = dynamodb_resource.Table(CMS_NEWS_TABLE)
    rows = _sort_admin_items(_scan_all_items(table))
    items = [_decorate_with_urls(r) for r in rows]
    return {
        'status': 'success',
        'message': 'News retrieved.',
        'items': items,
    }


# ---------- Documents ----------

async def create_document_service(
    dynamodb_resource: ServiceResource, payload: BaseModel,
) -> Dict[str, Any]:
    '''
        Persists a new document entry.
    '''
    table = dynamodb_resource.Table(CMS_DOCUMENTS_TABLE)
    item = _put_new_item(table, payload)
    return _decorate_with_urls(item)


async def get_document_service(
    dynamodb_resource: ServiceResource, document_id: str,
) -> Dict[str, Any]:
    '''
        Returns a single document by id.
    '''
    table = dynamodb_resource.Table(CMS_DOCUMENTS_TABLE)
    item = _fetch_item(table, document_id)
    return _decorate_with_urls(item)


async def update_document_service(
    dynamodb_resource: ServiceResource, document_id: str, payload: BaseModel,
) -> Dict[str, Any]:
    '''
        Partial update for a document.
    '''
    table = dynamodb_resource.Table(CMS_DOCUMENTS_TABLE)
    item = _merge_and_put(table, document_id, payload)
    return _decorate_with_urls(item)


async def delete_document_service(
    dynamodb_resource: ServiceResource, document_id: str,
) -> None:
    '''
        Deletes a document by id.
    '''
    table = dynamodb_resource.Table(CMS_DOCUMENTS_TABLE)
    _delete(table, document_id)


async def admin_list_documents_service(
    dynamodb_resource: ServiceResource,
) -> Dict[str, Any]:
    '''
        Returns every document (including drafts) sorted newest first.
    '''
    table = dynamodb_resource.Table(CMS_DOCUMENTS_TABLE)
    rows = _sort_admin_items(_scan_all_items(table))
    items = [_decorate_with_urls(r) for r in rows]
    return {
        'status': 'success',
        'message': 'Documents retrieved.',
        'items': items,
    }


# ---------- Slides ----------

async def create_slide_service(
    dynamodb_resource: ServiceResource, payload: BaseModel,
) -> Dict[str, Any]:
    '''
        Persists a new slide.
    '''
    table = dynamodb_resource.Table(CMS_SLIDES_TABLE)
    item = _put_new_item(table, payload)
    return _decorate_with_urls(item)


async def get_slide_service(
    dynamodb_resource: ServiceResource, slide_id: str,
) -> Dict[str, Any]:
    '''
        Returns a single slide.
    '''
    table = dynamodb_resource.Table(CMS_SLIDES_TABLE)
    item = _fetch_item(table, slide_id)
    return _decorate_with_urls(item)


async def update_slide_service(
    dynamodb_resource: ServiceResource, slide_id: str, payload: BaseModel,
) -> Dict[str, Any]:
    '''
        Partial update for a slide.
    '''
    table = dynamodb_resource.Table(CMS_SLIDES_TABLE)
    item = _merge_and_put(table, slide_id, payload)
    return _decorate_with_urls(item)


async def delete_slide_service(
    dynamodb_resource: ServiceResource, slide_id: str,
) -> None:
    '''
        Deletes a slide.
    '''
    table = dynamodb_resource.Table(CMS_SLIDES_TABLE)
    _delete(table, slide_id)


async def admin_list_slides_service(
    dynamodb_resource: ServiceResource,
) -> Dict[str, Any]:
    '''
        Returns every slide (including inactive) sorted newest first.
    '''
    table = dynamodb_resource.Table(CMS_SLIDES_TABLE)
    rows = _sort_admin_items(_scan_all_items(table))
    items = [_decorate_with_urls(r) for r in rows]
    return {
        'status': 'success',
        'message': 'Slides retrieved.',
        'items': items,
    }


# ---------- Entities ----------

async def create_entity_service(
    dynamodb_resource: ServiceResource, payload: BaseModel,
) -> Dict[str, Any]:
    '''
        Persists a new entity.
    '''
    table = dynamodb_resource.Table(CMS_ENTITIES_TABLE)
    item = _put_new_item(table, payload)
    return _decorate_with_urls(item)


async def get_entity_service(
    dynamodb_resource: ServiceResource, entity_id: str,
) -> Dict[str, Any]:
    '''
        Returns a single entity.
    '''
    table = dynamodb_resource.Table(CMS_ENTITIES_TABLE)
    item = _fetch_item(table, entity_id)
    return _decorate_with_urls(item)


async def update_entity_service(
    dynamodb_resource: ServiceResource, entity_id: str, payload: BaseModel,
) -> Dict[str, Any]:
    '''
        Partial update for an entity.
    '''
    table = dynamodb_resource.Table(CMS_ENTITIES_TABLE)
    item = _merge_and_put(table, entity_id, payload)
    return _decorate_with_urls(item)


async def delete_entity_service(
    dynamodb_resource: ServiceResource, entity_id: str,
) -> None:
    '''
        Deletes an entity.
    '''
    table = dynamodb_resource.Table(CMS_ENTITIES_TABLE)
    _delete(table, entity_id)


async def admin_list_entities_service(
    dynamodb_resource: ServiceResource,
) -> Dict[str, Any]:
    '''
        Returns every entity (including inactive) sorted newest first.
    '''
    table = dynamodb_resource.Table(CMS_ENTITIES_TABLE)
    rows = _sort_admin_items(_scan_all_items(table))
    items = [_decorate_with_urls(r) for r in rows]
    return {
        'status': 'success',
        'message': 'Entities retrieved.',
        'items': items,
    }
