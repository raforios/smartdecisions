'''
    Public CMS endpoints consumed by the institutional portal (demo/).

    Mirror the JWT-protected admin routes that will live in routes/cms.py
    but skip the auth dependency so the portal can fetch content
    anonymously.
'''
from typing import Optional

from boto3.resources.base import ServiceResource
from fastapi import APIRouter, Depends, Query, Request

from controllers.cms import (
    get_public_news_controller,
    get_public_documents_controller,
    get_public_slides_controller,
    get_public_entities_controller,
    get_public_news_by_id_controller,
    get_public_document_by_id_controller,
    get_public_slide_by_id_controller,
    get_public_entity_by_id_controller,
)
from schemas.cms import (
    NewsListResponse,
    DocumentListResponse,
    SlideListResponse,
    EntityListResponse,
    NewsItem,
    DocumentItem,
    SlideItem,
    EntityItem,
)
from fastapi import Path
from services.db_connection import get_db_dependency
from services.logger_config import custom_logger as logger


router = APIRouter(
    prefix = '/v1/cms/public',
    tags = ['Public CMS'],
)


PUBLIC_USER = 'public'


@router.get(
    '/news',
    response_model = NewsListResponse,
    summary = 'Published news (press, communiques, photos, articles).',
)
async def public_news(
    request: Request,
    lang: str = Query('es', max_length = 2,
                      description = 'ISO 2-letter language code.'),
    news_type: Optional[str] = Query(
        None, alias = 'type',
        description = 'Filter by type: press | communique | photo | article.'),
    limit: int = Query(50, ge = 1, le = 200),
    dynamodb_resource: ServiceResource = Depends(get_db_dependency),
):
    '''
        Returns the latest published news for the requested language.
    '''
    logger.info('Public news requested lang=%s type=%s.', lang, news_type)
    return await get_public_news_controller(
        dynamodb_resource = dynamodb_resource,
        request = request, current_user = PUBLIC_USER,
        lang = lang, news_type = news_type, limit = limit,
    )


@router.get(
    '/documents',
    response_model = DocumentListResponse,
    summary = 'Published documents (regulations, manuals, laws...).',
)
async def public_documents(
    request: Request,
    lang: str = Query('es', max_length = 2),
    doc_type: Optional[str] = Query(
        None, alias = 'type',
        description = 'Filter by classification (PDF, DOC, LEY, ...).'),
    limit: int = Query(100, ge = 1, le = 500),
    dynamodb_resource: ServiceResource = Depends(get_db_dependency),
):
    '''
        Returns the published documents catalog ordered by sort_order.
    '''
    logger.info('Public documents requested lang=%s doc_type=%s.', lang, doc_type)
    return await get_public_documents_controller(
        dynamodb_resource = dynamodb_resource,
        request = request, current_user = PUBLIC_USER,
        lang = lang, doc_type = doc_type, limit = limit,
    )


@router.get(
    '/slides',
    response_model = SlideListResponse,
    summary = 'Active hero slides for the portal landing page.',
)
async def public_slides(
    request: Request,
    lang: str = Query('es', max_length = 2),
    limit: int = Query(20, ge = 1, le = 50),
    dynamodb_resource: ServiceResource = Depends(get_db_dependency),
):
    '''
        Returns the active hero slides ordered by sort_order.
    '''
    logger.info('Public slides requested lang=%s.', lang)
    return await get_public_slides_controller(
        dynamodb_resource = dynamodb_resource,
        request = request, current_user = PUBLIC_USER,
        lang = lang, limit = limit,
    )


@router.get(
    '/entities',
    response_model = EntityListResponse,
    summary = 'Affiliated institutional entities (VINTO, COMIBOL, AJAM...).',
)
async def public_entities(
    request: Request,
    limit: int = Query(50, ge = 1, le = 200),
    dynamodb_resource: ServiceResource = Depends(get_db_dependency),
):
    '''
        Returns the active institutional entities. Names are language-agnostic.
    '''
    logger.info('Public entities requested.')
    return await get_public_entities_controller(
        dynamodb_resource = dynamodb_resource,
        request = request, current_user = PUBLIC_USER,
        limit = limit,
    )


# ---------- Public get-by-id ----------

@router.get(
    '/news/{news_id}',
    response_model = NewsItem,
    summary = 'Single published news item by id (detail page).',
)
async def public_news_detail(
    request: Request,
    news_id: str = Path(..., min_length = 1),
    dynamodb_resource: ServiceResource = Depends(get_db_dependency),
):
    '''
        Returns the news item powering the detail page. 404 when missing
        or unpublished — never leaks drafts via id-guessing.
    '''
    logger.info('Public news detail requested id=%s.', news_id)
    return await get_public_news_by_id_controller(
        dynamodb_resource = dynamodb_resource,
        request = request, current_user = PUBLIC_USER,
        news_id = news_id,
    )


@router.get(
    '/documents/{document_id}',
    response_model = DocumentItem,
    summary = 'Single published document by id (detail page).',
)
async def public_document_detail(
    request: Request,
    document_id: str = Path(..., min_length = 1),
    dynamodb_resource: ServiceResource = Depends(get_db_dependency),
):
    '''
        Returns the document item powering the detail page.
    '''
    logger.info('Public document detail requested id=%s.', document_id)
    return await get_public_document_by_id_controller(
        dynamodb_resource = dynamodb_resource,
        request = request, current_user = PUBLIC_USER,
        document_id = document_id,
    )


@router.get(
    '/slides/{slide_id}',
    response_model = SlideItem,
    summary = 'Single active slide by id.',
)
async def public_slide_detail(
    request: Request,
    slide_id: str = Path(..., min_length = 1),
    dynamodb_resource: ServiceResource = Depends(get_db_dependency),
):
    '''
        Returns one active slide. Used rarely; included for symmetry.
    '''
    logger.info('Public slide detail requested id=%s.', slide_id)
    return await get_public_slide_by_id_controller(
        dynamodb_resource = dynamodb_resource,
        request = request, current_user = PUBLIC_USER,
        slide_id = slide_id,
    )


@router.get(
    '/entities/{entity_id}',
    response_model = EntityItem,
    summary = 'Single active entity by id (detail page).',
)
async def public_entity_detail(
    request: Request,
    entity_id: str = Path(..., min_length = 1),
    dynamodb_resource: ServiceResource = Depends(get_db_dependency),
):
    '''
        Returns one active entity for the detail page.
    '''
    logger.info('Public entity detail requested id=%s.', entity_id)
    return await get_public_entity_by_id_controller(
        dynamodb_resource = dynamodb_resource,
        request = request, current_user = PUBLIC_USER,
        entity_id = entity_id,
    )
