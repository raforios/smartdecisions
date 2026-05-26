'''
    CMS Controllers.

    Thin orchestrators between routes and services. Wrapped by
    `handle_service_errors` so exceptions are translated into proper HTTP
    responses and usage logs are emitted via the shared decorator.
'''
from typing import Optional
from boto3.resources.base import ServiceResource
from fastapi import Request

from services.utils import handle_service_errors
from services.logger_config import custom_logger as logger
from services.cms import (
    list_published_news_service,
    list_published_documents_service,
    list_active_slides_service,
    list_active_entities_service,
    get_published_news_service,
    get_published_document_service,
    get_active_slide_service,
    get_active_entity_service,
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


@handle_service_errors('CMS')
async def get_public_news_controller(
    dynamodb_resource: ServiceResource,
    request: Request, # pylint: disable=unused-argument
    current_user: str,
    lang: str,
    news_type: Optional[str] = None,
    limit: int = 50,
) -> NewsListResponse:
    '''
        Returns the published news list. Public endpoint, `current_user`
        is the literal 'public'.
    '''
    message = (f'User {current_user} requested news lang={lang} '
               f'type={news_type} limit={limit}.')
    logger.info(message)
    result = await list_published_news_service(
        dynamodb_resource = dynamodb_resource,
        lang = lang, news_type = news_type, limit = limit,
    )
    return NewsListResponse(**result)


@handle_service_errors('CMS')
async def get_public_documents_controller(
    dynamodb_resource: ServiceResource,
    request: Request, # pylint: disable=unused-argument
    current_user: str,
    lang: str,
    doc_type: Optional[str] = None,
    limit: int = 100,
) -> DocumentListResponse:
    '''
        Returns the published documents list.
    '''
    message = (f'User {current_user} requested documents lang={lang} '
               f'doc_type={doc_type} limit={limit}.')
    logger.info(message)
    result = await list_published_documents_service(
        dynamodb_resource = dynamodb_resource,
        lang = lang, doc_type = doc_type, limit = limit,
    )
    return DocumentListResponse(**result)


@handle_service_errors('CMS')
async def get_public_slides_controller(
    dynamodb_resource: ServiceResource,
    request: Request, # pylint: disable=unused-argument
    current_user: str,
    lang: str,
    limit: int = 20,
) -> SlideListResponse:
    '''
        Returns the active hero slides list.
    '''
    message = (f'User {current_user} requested slides lang={lang} '
               f'limit={limit}.')
    logger.info(message)
    result = await list_active_slides_service(
        dynamodb_resource = dynamodb_resource, lang = lang, limit = limit,
    )
    return SlideListResponse(**result)


@handle_service_errors('CMS')
async def get_public_entities_controller(
    dynamodb_resource: ServiceResource,
    request: Request, # pylint: disable=unused-argument
    current_user: str,
    limit: int = 50,
) -> EntityListResponse:
    '''
        Returns the active institutional entities list.
    '''
    message = f'User {current_user} requested entities limit={limit}.'
    logger.info(message)
    result = await list_active_entities_service(
        dynamodb_resource = dynamodb_resource, limit = limit,
    )
    return EntityListResponse(**result)


# ---------- Public get-by-id ----------

@handle_service_errors('CMS')
async def get_public_news_by_id_controller(
    dynamodb_resource: ServiceResource,
    request: Request, # pylint: disable=unused-argument
    current_user: str,
    news_id: str,
) -> NewsItem:
    '''
        Returns a single published news item for the detail page.
    '''
    message = f'User {current_user} requested news id={news_id}.'
    logger.info(message)
    item = await get_published_news_service(
        dynamodb_resource = dynamodb_resource, news_id = news_id,
    )
    return NewsItem.model_validate(item)


@handle_service_errors('CMS')
async def get_public_document_by_id_controller(
    dynamodb_resource: ServiceResource,
    request: Request, # pylint: disable=unused-argument
    current_user: str,
    document_id: str,
) -> DocumentItem:
    '''
        Returns a single published document for the detail page.
    '''
    message = f'User {current_user} requested document id={document_id}.'
    logger.info(message)
    item = await get_published_document_service(
        dynamodb_resource = dynamodb_resource, document_id = document_id,
    )
    return DocumentItem.model_validate(item)


@handle_service_errors('CMS')
async def get_public_slide_by_id_controller(
    dynamodb_resource: ServiceResource,
    request: Request, # pylint: disable=unused-argument
    current_user: str,
    slide_id: str,
) -> SlideItem:
    '''
        Returns a single active slide for the detail page.
    '''
    message = f'User {current_user} requested slide id={slide_id}.'
    logger.info(message)
    item = await get_active_slide_service(
        dynamodb_resource = dynamodb_resource, slide_id = slide_id,
    )
    return SlideItem.model_validate(item)


@handle_service_errors('CMS')
async def get_public_entity_by_id_controller(
    dynamodb_resource: ServiceResource,
    request: Request, # pylint: disable=unused-argument
    current_user: str,
    entity_id: str,
) -> EntityItem:
    '''
        Returns a single active entity for the detail page.
    '''
    message = f'User {current_user} requested entity id={entity_id}.'
    logger.info(message)
    item = await get_active_entity_service(
        dynamodb_resource = dynamodb_resource, entity_id = entity_id,
    )
    return EntityItem.model_validate(item)
