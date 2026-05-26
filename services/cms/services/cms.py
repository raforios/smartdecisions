'''
    CMS read services backed by DynamoDB.

    Each function performs a Scan with a FilterExpression on the matching
    table and applies the final sort in Python. Volumes are small (a few
    dozen items per entity at most) so Scan is acceptable; if a tenant
    grows past that, swap to a Query on a GSI keyed by (lang, sort_order).

    The scan is paginated transparently to bypass DynamoDB's 1 MB-per-call
    soft limit, which is well above the expected payload size but worth
    handling defensively.
'''
from typing import Any, Callable, Dict, List, Optional
from boto3.dynamodb.conditions import Attr
from boto3.resources.base import ServiceResource

from models.cms import (
    CMS_NEWS_TABLE,
    CMS_DOCUMENTS_TABLE,
    CMS_SLIDES_TABLE,
    CMS_ENTITIES_TABLE,
)
from services.exceptions import RegisterNotFoundError


DEFAULT_LANG = 'es'

# Public S3 URL pattern. Institutional buckets are configured with public
# read; for restricted assets the admin path should pre-resolve a
# presigned URL via the FILES service and store it as `*_external_url`.
_S3_URL_TEMPLATE = 'https://{bucket}.s3.amazonaws.com/{key}'


def _resolve_s3_url(bucket: Optional[str], key: Optional[str]) -> Optional[str]:
    '''
        Builds the public S3 URL when both bucket and key are present.
    '''
    if not bucket or not key:
        return None
    return _S3_URL_TEMPLATE.format(bucket = bucket, key = key.lstrip('/'))


def _resolve_asset(bucket: Optional[str], key: Optional[str],
                   fallback: Optional[str] = None) -> Optional[str]:
    '''
        Prefers the resolved S3 URL; falls back to the provided URL when
        the asset lives outside S3.
    '''
    return _resolve_s3_url(bucket, key) or fallback


def _scan_with_filter(table, filter_expression) -> List[Dict[str, Any]]:
    '''
        Runs Scan with the supplied FilterExpression, transparently
        following `LastEvaluatedKey` until DynamoDB reports the scan is
        complete. Returns the aggregated items list.
    '''
    items: List[Dict[str, Any]] = []
    scan_kwargs = {'FilterExpression': filter_expression}
    while True:
        response = table.scan(**scan_kwargs)
        items.extend(response.get('Items', []))
        last_key = response.get('LastEvaluatedKey')
        if not last_key:
            break
        scan_kwargs['ExclusiveStartKey'] = last_key
    return items


def _sort_and_limit(items: List[Dict[str, Any]],
                    key_fn: Callable[[Dict[str, Any]], Any],
                    limit: int) -> List[Dict[str, Any]]:
    '''
        Sorts the supplied items by `key_fn` and applies the limit slice.
    '''
    return sorted(items, key = key_fn)[:limit]


# ---------- News ----------

async def list_published_news_service(
    dynamodb_resource: ServiceResource,
    lang: str = DEFAULT_LANG,
    news_type: Optional[str] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    '''
        Returns the published news items for a given language.
    '''
    table = dynamodb_resource.Table(CMS_NEWS_TABLE)
    expression = Attr('is_published').eq(True) & Attr('lang').eq(lang)
    if news_type:
        expression = expression & Attr('type').eq(news_type)
    raw_items = _scan_with_filter(table, expression)

    # Lower sort_order first, then newer published_at (string ISO sorts).
    def _key(item: Dict[str, Any]):
        return (int(item.get('sort_order', 0)),
                _negate_iso(item.get('published_at')))
    ordered = _sort_and_limit(raw_items, _key, limit)

    items = [
        {
            'id': r.get('id'),
            'lang': r.get('lang'),
            'type': r.get('type'),
            'title': r.get('title'),
            'summary': r.get('summary'),
            'body': r.get('body'),
            'image_url': _resolve_s3_url(
                r.get('image_s3_bucket'), r.get('image_s3_key'),
            ),
            'external_url': r.get('external_url'),
            'published_at': r.get('published_at'),
            'sort_order': int(r.get('sort_order', 0)),
        }
        for r in ordered
    ]
    return {
        'status': 'success',
        'message': 'News retrieved.',
        'lang': lang,
        'items': items,
    }


# ---------- Documents ----------

async def list_published_documents_service(
    dynamodb_resource: ServiceResource,
    lang: str = DEFAULT_LANG,
    doc_type: Optional[str] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    '''
        Returns the published documents for a given language.
    '''
    table = dynamodb_resource.Table(CMS_DOCUMENTS_TABLE)
    expression = Attr('is_published').eq(True) & Attr('lang').eq(lang)
    if doc_type:
        expression = expression & Attr('doc_type').eq(doc_type)
    raw_items = _scan_with_filter(table, expression)

    def _key(item: Dict[str, Any]):
        return (int(item.get('sort_order', 0)),
                _negate_iso(item.get('doc_date')))
    ordered = _sort_and_limit(raw_items, _key, limit)

    items = [
        {
            'id': r.get('id'),
            'lang': r.get('lang'),
            'title': r.get('title'),
            'doc_type': r.get('doc_type'),
            'doc_date': r.get('doc_date'),
            'file_url': _resolve_asset(
                r.get('file_s3_bucket'),
                r.get('file_s3_key'),
                r.get('file_external_url'),
            ),
            'sort_order': int(r.get('sort_order', 0)),
        }
        for r in ordered
    ]
    return {
        'status': 'success',
        'message': 'Documents retrieved.',
        'lang': lang,
        'items': items,
    }


# ---------- Slides ----------

async def list_active_slides_service(
    dynamodb_resource: ServiceResource,
    lang: str = DEFAULT_LANG,
    limit: int = 20,
) -> Dict[str, Any]:
    '''
        Returns the active hero slides for a given language.
    '''
    table = dynamodb_resource.Table(CMS_SLIDES_TABLE)
    expression = Attr('is_active').eq(True) & Attr('lang').eq(lang)
    raw_items = _scan_with_filter(table, expression)

    def _key(item: Dict[str, Any]):
        return (int(item.get('sort_order', 0)),
                _negate_iso(item.get('updated_at')))
    ordered = _sort_and_limit(raw_items, _key, limit)

    items = [
        {
            'id': r.get('id'),
            'lang': r.get('lang'),
            'title': r.get('title'),
            'description': r.get('description'),
            'image_url': _resolve_s3_url(
                r.get('image_s3_bucket'), r.get('image_s3_key'),
            ),
            'link_url': r.get('link_url'),
            'sort_order': int(r.get('sort_order', 0)),
        }
        for r in ordered
    ]
    return {
        'status': 'success',
        'message': 'Slides retrieved.',
        'lang': lang,
        'items': items,
    }


# ---------- Entities ----------

async def list_active_entities_service(
    dynamodb_resource: ServiceResource, limit: int = 50,
) -> Dict[str, Any]:
    '''
        Returns the active affiliated entities. Language-agnostic.
    '''
    table = dynamodb_resource.Table(CMS_ENTITIES_TABLE)
    expression = Attr('is_active').eq(True)
    raw_items = _scan_with_filter(table, expression)

    def _key(item: Dict[str, Any]):
        return (int(item.get('sort_order', 0)), item.get('name', ''))
    ordered = _sort_and_limit(raw_items, _key, limit)

    items = [
        {
            'id': r.get('id'),
            'name': r.get('name'),
            'short_description': r.get('short_description'),
            'url': r.get('url'),
            'logo_url': _resolve_s3_url(
                r.get('logo_s3_bucket'), r.get('logo_s3_key'),
            ),
            'sort_order': int(r.get('sort_order', 0)),
        }
        for r in ordered
    ]
    return {
        'status': 'success',
        'message': 'Entities retrieved.',
        'items': items,
    }


# ---------- Public get-by-id ----------
#
# The detail page of the institutional portal fetches a single item by
# id so the URL stays clean (`detail.html?type=news&id=abc`). Each
# helper returns the same shape as one element of the matching listing,
# already resolved (S3 URLs collapsed). When the item is missing OR has
# been hidden (`is_published=False` / `is_active=False`), we raise
# RegisterNotFoundError so the controller answers 404 — leaking
# unpublished content via id-guessing would be a privacy hole.


def _get_published_item(table, item_id: str, hidden_field: str,
                        hidden_when_false: bool = True) -> Dict[str, Any]:
    '''
        Returns the raw DynamoDB item if it exists AND is published/active.
        Raises RegisterNotFoundError otherwise. `hidden_field` is the
        boolean toggle to check (`is_published` for news/documents,
        `is_active` for slides/entities).
    '''
    response = table.get_item(Key = {'id': item_id})
    item = response.get('Item')
    if not item:
        raise RegisterNotFoundError(
            detail = f'{table.name} item id={item_id} not found.')
    visible = bool(item.get(hidden_field))
    if hidden_when_false and not visible:
        raise RegisterNotFoundError(
            detail = f'{table.name} item id={item_id} is not published.')
    return item


async def get_published_news_service(
    dynamodb_resource: ServiceResource, news_id: str,
) -> Dict[str, Any]:
    '''
        Returns one published news item by id.
    '''
    table = dynamodb_resource.Table(CMS_NEWS_TABLE)
    item = _get_published_item(table, news_id, 'is_published')
    return {
        'id': item.get('id'),
        'lang': item.get('lang'),
        'type': item.get('type'),
        'title': item.get('title'),
        'summary': item.get('summary'),
        'body': item.get('body'),
        'image_url': _resolve_s3_url(
            item.get('image_s3_bucket'), item.get('image_s3_key'),
        ),
        'external_url': item.get('external_url'),
        'published_at': item.get('published_at'),
        'sort_order': int(item.get('sort_order', 0)),
    }


async def get_published_document_service(
    dynamodb_resource: ServiceResource, document_id: str,
) -> Dict[str, Any]:
    '''
        Returns one published document by id.
    '''
    table = dynamodb_resource.Table(CMS_DOCUMENTS_TABLE)
    item = _get_published_item(table, document_id, 'is_published')
    return {
        'id': item.get('id'),
        'lang': item.get('lang'),
        'title': item.get('title'),
        'doc_type': item.get('doc_type'),
        'doc_date': item.get('doc_date'),
        'file_url': _resolve_asset(
            item.get('file_s3_bucket'),
            item.get('file_s3_key'),
            item.get('file_external_url'),
        ),
        'sort_order': int(item.get('sort_order', 0)),
    }


async def get_active_slide_service(
    dynamodb_resource: ServiceResource, slide_id: str,
) -> Dict[str, Any]:
    '''
        Returns one active slide by id.
    '''
    table = dynamodb_resource.Table(CMS_SLIDES_TABLE)
    item = _get_published_item(table, slide_id, 'is_active')
    return {
        'id': item.get('id'),
        'lang': item.get('lang'),
        'title': item.get('title'),
        'description': item.get('description'),
        'image_url': _resolve_s3_url(
            item.get('image_s3_bucket'), item.get('image_s3_key'),
        ),
        'link_url': item.get('link_url'),
        'sort_order': int(item.get('sort_order', 0)),
    }


async def get_active_entity_service(
    dynamodb_resource: ServiceResource, entity_id: str,
) -> Dict[str, Any]:
    '''
        Returns one active entity by id.
    '''
    table = dynamodb_resource.Table(CMS_ENTITIES_TABLE)
    item = _get_published_item(table, entity_id, 'is_active')
    return {
        'id': item.get('id'),
        'name': item.get('name'),
        'short_description': item.get('short_description'),
        'url': item.get('url'),
        'logo_url': _resolve_s3_url(
            item.get('logo_s3_bucket'), item.get('logo_s3_key'),
        ),
        'sort_order': int(item.get('sort_order', 0)),
    }


# ---------- Helpers ----------

def _negate_iso(iso_value: Optional[str]) -> str:
    '''
        Returns a sortable token where newer ISO timestamps come first.

        DynamoDB stores dates as ISO strings; ascending string sort gives
        oldest-first, so we invert the comparator by prepending a tilde
        (the highest printable ASCII char) for missing values and using
        the negated codepoint trick for present ones.
    '''
    if not iso_value:
        return '~'
    # Pad with `~` to ensure shorter dates sort the same way as longer ones.
    return ''.join(chr(0x10FFFF - ord(c)) for c in iso_value)
