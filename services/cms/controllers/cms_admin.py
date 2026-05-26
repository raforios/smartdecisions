'''
    CMS Admin Controllers.

    Thin orchestrators between the JWT-protected routes and the write
    services. All controllers are wrapped by `handle_service_errors` so
    exceptions become proper HTTP responses and usage logs are emitted.
'''
from boto3.resources.base import ServiceResource
from fastapi import Request

from schemas.cms_admin import (
    NewsCreate, NewsUpdate, NewsAdminItem, NewsAdminListResponse,
    DocumentCreate, DocumentUpdate, DocumentAdminItem, DocumentAdminListResponse,
    SlideCreate, SlideUpdate, SlideAdminItem, SlideAdminListResponse,
    EntityCreate, EntityUpdate, EntityAdminItem, EntityAdminListResponse,
    DeleteResponse,
)
from services.utils import handle_service_errors
from services.logger_config import custom_logger as logger
from services.cms_admin import (
    create_news_service, get_news_service, update_news_service,
    delete_news_service, admin_list_news_service,
    create_document_service, get_document_service, update_document_service,
    delete_document_service, admin_list_documents_service,
    create_slide_service, get_slide_service, update_slide_service,
    delete_slide_service, admin_list_slides_service,
    create_entity_service, get_entity_service, update_entity_service,
    delete_entity_service, admin_list_entities_service,
)


# ============================================================
# News
# ============================================================

@handle_service_errors('CMS')
async def admin_list_news_controller(
    dynamodb_resource: ServiceResource,
    request: Request, # pylint: disable=unused-argument
    current_user: str,
) -> NewsAdminListResponse:
    '''
        Returns every news item for the admin panel.
    '''
    message = f'User {current_user} requested admin news list.'
    logger.info(message)
    result = await admin_list_news_service(dynamodb_resource = dynamodb_resource)
    return NewsAdminListResponse(**result)


@handle_service_errors('CMS')
async def admin_create_news_controller(
    dynamodb_resource: ServiceResource,
    request: Request, # pylint: disable=unused-argument
    current_user: str,
    payload: NewsCreate,
) -> NewsAdminItem:
    '''
        Creates a news entry.
    '''
    message = f'User {current_user} creating news title={payload.title}.'
    logger.info(message)
    item = await create_news_service(
        dynamodb_resource = dynamodb_resource, payload = payload,
    )
    return NewsAdminItem.model_validate(item)


@handle_service_errors('CMS')
async def admin_get_news_controller(
    dynamodb_resource: ServiceResource,
    request: Request, # pylint: disable=unused-argument
    current_user: str,
    news_id: str,
) -> NewsAdminItem:
    '''
        Retrieves a single news item.
    '''
    message = f'User {current_user} fetching news id={news_id}.'
    logger.info(message)
    item = await get_news_service(
        dynamodb_resource = dynamodb_resource, news_id = news_id,
    )
    return NewsAdminItem.model_validate(item)


@handle_service_errors('CMS')
async def admin_update_news_controller(
    dynamodb_resource: ServiceResource,
    request: Request, # pylint: disable=unused-argument
    current_user: str,
    news_id: str,
    payload: NewsUpdate,
) -> NewsAdminItem:
    '''
        Partial update of a news item.
    '''
    message = f'User {current_user} updating news id={news_id}.'
    logger.info(message)
    item = await update_news_service(
        dynamodb_resource = dynamodb_resource,
        news_id = news_id, payload = payload,
    )
    return NewsAdminItem.model_validate(item)


@handle_service_errors('CMS')
async def admin_delete_news_controller(
    dynamodb_resource: ServiceResource,
    request: Request, # pylint: disable=unused-argument
    current_user: str,
    news_id: str,
) -> DeleteResponse:
    '''
        Deletes a news item.
    '''
    message = f'User {current_user} deleting news id={news_id}.'
    logger.info(message)
    await delete_news_service(
        dynamodb_resource = dynamodb_resource, news_id = news_id,
    )
    return DeleteResponse(message = 'News deleted.', id = news_id)


# ============================================================
# Documents
# ============================================================

@handle_service_errors('CMS')
async def admin_list_documents_controller(
    dynamodb_resource: ServiceResource,
    request: Request, # pylint: disable=unused-argument
    current_user: str,
) -> DocumentAdminListResponse:
    '''
        Returns every document for the admin panel.
    '''
    message = f'User {current_user} requested admin documents list.'
    logger.info(message)
    result = await admin_list_documents_service(
        dynamodb_resource = dynamodb_resource,
    )
    return DocumentAdminListResponse(**result)


@handle_service_errors('CMS')
async def admin_create_document_controller(
    dynamodb_resource: ServiceResource,
    request: Request, # pylint: disable=unused-argument
    current_user: str,
    payload: DocumentCreate,
) -> DocumentAdminItem:
    '''
        Creates a document entry.
    '''
    message = f'User {current_user} creating document title={payload.title}.'
    logger.info(message)
    item = await create_document_service(
        dynamodb_resource = dynamodb_resource, payload = payload,
    )
    return DocumentAdminItem.model_validate(item)


@handle_service_errors('CMS')
async def admin_get_document_controller(
    dynamodb_resource: ServiceResource,
    request: Request, # pylint: disable=unused-argument
    current_user: str,
    document_id: str,
) -> DocumentAdminItem:
    '''
        Retrieves a single document.
    '''
    message = f'User {current_user} fetching document id={document_id}.'
    logger.info(message)
    item = await get_document_service(
        dynamodb_resource = dynamodb_resource, document_id = document_id,
    )
    return DocumentAdminItem.model_validate(item)


@handle_service_errors('CMS')
async def admin_update_document_controller(
    dynamodb_resource: ServiceResource,
    request: Request, # pylint: disable=unused-argument
    current_user: str,
    document_id: str,
    payload: DocumentUpdate,
) -> DocumentAdminItem:
    '''
        Partial update of a document.
    '''
    message = f'User {current_user} updating document id={document_id}.'
    logger.info(message)
    item = await update_document_service(
        dynamodb_resource = dynamodb_resource,
        document_id = document_id, payload = payload,
    )
    return DocumentAdminItem.model_validate(item)


@handle_service_errors('CMS')
async def admin_delete_document_controller(
    dynamodb_resource: ServiceResource,
    request: Request, # pylint: disable=unused-argument
    current_user: str,
    document_id: str,
) -> DeleteResponse:
    '''
        Deletes a document.
    '''
    message = f'User {current_user} deleting document id={document_id}.'
    logger.info(message)
    await delete_document_service(
        dynamodb_resource = dynamodb_resource, document_id = document_id,
    )
    return DeleteResponse(message = 'Document deleted.', id = document_id)


# ============================================================
# Slides
# ============================================================

@handle_service_errors('CMS')
async def admin_list_slides_controller(
    dynamodb_resource: ServiceResource,
    request: Request, # pylint: disable=unused-argument
    current_user: str,
) -> SlideAdminListResponse:
    '''
        Returns every slide for the admin panel.
    '''
    message = f'User {current_user} requested admin slides list.'
    logger.info(message)
    result = await admin_list_slides_service(
        dynamodb_resource = dynamodb_resource,
    )
    return SlideAdminListResponse(**result)


@handle_service_errors('CMS')
async def admin_create_slide_controller(
    dynamodb_resource: ServiceResource,
    request: Request, # pylint: disable=unused-argument
    current_user: str,
    payload: SlideCreate,
) -> SlideAdminItem:
    '''
        Creates a slide.
    '''
    message = f'User {current_user} creating slide title={payload.title}.'
    logger.info(message)
    item = await create_slide_service(
        dynamodb_resource = dynamodb_resource, payload = payload,
    )
    return SlideAdminItem.model_validate(item)


@handle_service_errors('CMS')
async def admin_get_slide_controller(
    dynamodb_resource: ServiceResource,
    request: Request, # pylint: disable=unused-argument
    current_user: str,
    slide_id: str,
) -> SlideAdminItem:
    '''
        Retrieves a single slide.
    '''
    message = f'User {current_user} fetching slide id={slide_id}.'
    logger.info(message)
    item = await get_slide_service(
        dynamodb_resource = dynamodb_resource, slide_id = slide_id,
    )
    return SlideAdminItem.model_validate(item)


@handle_service_errors('CMS')
async def admin_update_slide_controller(
    dynamodb_resource: ServiceResource,
    request: Request, # pylint: disable=unused-argument
    current_user: str,
    slide_id: str,
    payload: SlideUpdate,
) -> SlideAdminItem:
    '''
        Partial update of a slide.
    '''
    message = f'User {current_user} updating slide id={slide_id}.'
    logger.info(message)
    item = await update_slide_service(
        dynamodb_resource = dynamodb_resource,
        slide_id = slide_id, payload = payload,
    )
    return SlideAdminItem.model_validate(item)


@handle_service_errors('CMS')
async def admin_delete_slide_controller(
    dynamodb_resource: ServiceResource,
    request: Request, # pylint: disable=unused-argument
    current_user: str,
    slide_id: str,
) -> DeleteResponse:
    '''
        Deletes a slide.
    '''
    message = f'User {current_user} deleting slide id={slide_id}.'
    logger.info(message)
    await delete_slide_service(
        dynamodb_resource = dynamodb_resource, slide_id = slide_id,
    )
    return DeleteResponse(message = 'Slide deleted.', id = slide_id)


# ============================================================
# Entities
# ============================================================

@handle_service_errors('CMS')
async def admin_list_entities_controller(
    dynamodb_resource: ServiceResource,
    request: Request, # pylint: disable=unused-argument
    current_user: str,
) -> EntityAdminListResponse:
    '''
        Returns every entity for the admin panel.
    '''
    message = f'User {current_user} requested admin entities list.'
    logger.info(message)
    result = await admin_list_entities_service(
        dynamodb_resource = dynamodb_resource,
    )
    return EntityAdminListResponse(**result)


@handle_service_errors('CMS')
async def admin_create_entity_controller(
    dynamodb_resource: ServiceResource,
    request: Request, # pylint: disable=unused-argument
    current_user: str,
    payload: EntityCreate,
) -> EntityAdminItem:
    '''
        Creates an entity.
    '''
    message = f'User {current_user} creating entity name={payload.name}.'
    logger.info(message)
    item = await create_entity_service(
        dynamodb_resource = dynamodb_resource, payload = payload,
    )
    return EntityAdminItem.model_validate(item)


@handle_service_errors('CMS')
async def admin_get_entity_controller(
    dynamodb_resource: ServiceResource,
    request: Request, # pylint: disable=unused-argument
    current_user: str,
    entity_id: str,
) -> EntityAdminItem:
    '''
        Retrieves a single entity.
    '''
    message = f'User {current_user} fetching entity id={entity_id}.'
    logger.info(message)
    item = await get_entity_service(
        dynamodb_resource = dynamodb_resource, entity_id = entity_id,
    )
    return EntityAdminItem.model_validate(item)


@handle_service_errors('CMS')
async def admin_update_entity_controller(
    dynamodb_resource: ServiceResource,
    request: Request, # pylint: disable=unused-argument
    current_user: str,
    entity_id: str,
    payload: EntityUpdate,
) -> EntityAdminItem:
    '''
        Partial update of an entity.
    '''
    message = f'User {current_user} updating entity id={entity_id}.'
    logger.info(message)
    item = await update_entity_service(
        dynamodb_resource = dynamodb_resource,
        entity_id = entity_id, payload = payload,
    )
    return EntityAdminItem.model_validate(item)


@handle_service_errors('CMS')
async def admin_delete_entity_controller(
    dynamodb_resource: ServiceResource,
    request: Request, # pylint: disable=unused-argument
    current_user: str,
    entity_id: str,
) -> DeleteResponse:
    '''
        Deletes an entity.
    '''
    message = f'User {current_user} deleting entity id={entity_id}.'
    logger.info(message)
    await delete_entity_service(
        dynamodb_resource = dynamodb_resource, entity_id = entity_id,
    )
    return DeleteResponse(message = 'Entity deleted.', id = entity_id)
