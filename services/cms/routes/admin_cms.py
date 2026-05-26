'''
    Admin CMS endpoints. JWT-protected mutations + listings for the
    institutional CMS panel.

    Asset uploads are NOT handled here: the admin first uploads to the
    FILES microservice and then sends the resulting `*_s3_bucket` /
    `*_s3_key` references in the JSON body. This keeps the CMS focused
    on content metadata.
'''
from boto3.resources.base import ServiceResource
from fastapi import APIRouter, Depends, Path, Request, status

from controllers.cms_admin import (
    admin_list_news_controller,
    admin_create_news_controller,
    admin_get_news_controller,
    admin_update_news_controller,
    admin_delete_news_controller,
    admin_list_documents_controller,
    admin_create_document_controller,
    admin_get_document_controller,
    admin_update_document_controller,
    admin_delete_document_controller,
    admin_list_slides_controller,
    admin_create_slide_controller,
    admin_get_slide_controller,
    admin_update_slide_controller,
    admin_delete_slide_controller,
    admin_list_entities_controller,
    admin_create_entity_controller,
    admin_get_entity_controller,
    admin_update_entity_controller,
    admin_delete_entity_controller,
)
from schemas.cms_admin import (
    NewsCreate, NewsUpdate, NewsAdminItem, NewsAdminListResponse,
    DocumentCreate, DocumentUpdate, DocumentAdminItem, DocumentAdminListResponse,
    SlideCreate, SlideUpdate, SlideAdminItem, SlideAdminListResponse,
    EntityCreate, EntityUpdate, EntityAdminItem, EntityAdminListResponse,
    DeleteResponse,
)
from services.db_connection import get_db_dependency
from services.logger_config import custom_logger as logger
from services.security import get_current_user


router = APIRouter(
    prefix = '/v1/cms/admin',
    tags = ['Admin CMS'],
    dependencies = [Depends(get_current_user)],
)


# ============================================================
# News
# ============================================================

@router.get(
    '/news',
    response_model = NewsAdminListResponse,
    summary = 'List every news item (including drafts).',
)
async def admin_list_news(
    request: Request,
    dynamodb_resource: ServiceResource = Depends(get_db_dependency),
    current_user: str = Depends(get_current_user),
):
    '''
        Admin listing of all news items.
    '''
    logger.info('Admin news list requested by %s.', current_user)
    return await admin_list_news_controller(
        dynamodb_resource = dynamodb_resource,
        request = request, current_user = current_user,
    )


@router.post(
    '/news',
    response_model = NewsAdminItem,
    status_code = status.HTTP_201_CREATED,
    summary = 'Create a news item.',
)
async def admin_create_news(
    payload: NewsCreate,
    request: Request,
    dynamodb_resource: ServiceResource = Depends(get_db_dependency),
    current_user: str = Depends(get_current_user),
):
    '''
        Creates a news item from JSON payload (asset already uploaded to S3).
    '''
    return await admin_create_news_controller(
        dynamodb_resource = dynamodb_resource,
        request = request, current_user = current_user,
        payload = payload,
    )


@router.get(
    '/news/{news_id}',
    response_model = NewsAdminItem,
    summary = 'Retrieve a single news item by id.',
)
async def admin_get_news(
    request: Request,
    news_id: str = Path(..., min_length = 1),
    dynamodb_resource: ServiceResource = Depends(get_db_dependency),
    current_user: str = Depends(get_current_user),
):
    '''
        Returns a single news item.
    '''
    return await admin_get_news_controller(
        dynamodb_resource = dynamodb_resource,
        request = request, current_user = current_user,
        news_id = news_id,
    )


@router.put(
    '/news/{news_id}',
    response_model = NewsAdminItem,
    summary = 'Partial update of a news item.',
)
async def admin_update_news(
    payload: NewsUpdate,
    request: Request,
    news_id: str = Path(..., min_length = 1),
    dynamodb_resource: ServiceResource = Depends(get_db_dependency),
    current_user: str = Depends(get_current_user),
):
    '''
        Updates only the supplied fields on the target news item.
    '''
    return await admin_update_news_controller(
        dynamodb_resource = dynamodb_resource,
        request = request, current_user = current_user,
        news_id = news_id, payload = payload,
    )


@router.delete(
    '/news/{news_id}',
    response_model = DeleteResponse,
    summary = 'Delete a news item.',
)
async def admin_delete_news(
    request: Request,
    news_id: str = Path(..., min_length = 1),
    dynamodb_resource: ServiceResource = Depends(get_db_dependency),
    current_user: str = Depends(get_current_user),
):
    '''
        Deletes a news item by id.
    '''
    return await admin_delete_news_controller(
        dynamodb_resource = dynamodb_resource,
        request = request, current_user = current_user,
        news_id = news_id,
    )


# ============================================================
# Documents
# ============================================================

@router.get(
    '/documents',
    response_model = DocumentAdminListResponse,
    summary = 'List every document (including drafts).',
)
async def admin_list_documents(
    request: Request,
    dynamodb_resource: ServiceResource = Depends(get_db_dependency),
    current_user: str = Depends(get_current_user),
):
    '''
        Admin listing of all documents.
    '''
    return await admin_list_documents_controller(
        dynamodb_resource = dynamodb_resource,
        request = request, current_user = current_user,
    )


@router.post(
    '/documents',
    response_model = DocumentAdminItem,
    status_code = status.HTTP_201_CREATED,
    summary = 'Create a document.',
)
async def admin_create_document(
    payload: DocumentCreate,
    request: Request,
    dynamodb_resource: ServiceResource = Depends(get_db_dependency),
    current_user: str = Depends(get_current_user),
):
    '''
        Creates a document entry.
    '''
    return await admin_create_document_controller(
        dynamodb_resource = dynamodb_resource,
        request = request, current_user = current_user,
        payload = payload,
    )


@router.get(
    '/documents/{document_id}',
    response_model = DocumentAdminItem,
    summary = 'Retrieve a single document by id.',
)
async def admin_get_document(
    request: Request,
    document_id: str = Path(..., min_length = 1),
    dynamodb_resource: ServiceResource = Depends(get_db_dependency),
    current_user: str = Depends(get_current_user),
):
    '''
        Returns a single document.
    '''
    return await admin_get_document_controller(
        dynamodb_resource = dynamodb_resource,
        request = request, current_user = current_user,
        document_id = document_id,
    )


@router.put(
    '/documents/{document_id}',
    response_model = DocumentAdminItem,
    summary = 'Partial update of a document.',
)
async def admin_update_document(
    payload: DocumentUpdate,
    request: Request,
    document_id: str = Path(..., min_length = 1),
    dynamodb_resource: ServiceResource = Depends(get_db_dependency),
    current_user: str = Depends(get_current_user),
):
    '''
        Updates only the supplied fields on the target document.
    '''
    return await admin_update_document_controller(
        dynamodb_resource = dynamodb_resource,
        request = request, current_user = current_user,
        document_id = document_id, payload = payload,
    )


@router.delete(
    '/documents/{document_id}',
    response_model = DeleteResponse,
    summary = 'Delete a document.',
)
async def admin_delete_document(
    request: Request,
    document_id: str = Path(..., min_length = 1),
    dynamodb_resource: ServiceResource = Depends(get_db_dependency),
    current_user: str = Depends(get_current_user),
):
    '''
        Deletes a document by id.
    '''
    return await admin_delete_document_controller(
        dynamodb_resource = dynamodb_resource,
        request = request, current_user = current_user,
        document_id = document_id,
    )


# ============================================================
# Slides
# ============================================================

@router.get(
    '/slides',
    response_model = SlideAdminListResponse,
    summary = 'List every slide (including inactive).',
)
async def admin_list_slides(
    request: Request,
    dynamodb_resource: ServiceResource = Depends(get_db_dependency),
    current_user: str = Depends(get_current_user),
):
    '''
        Admin listing of all slides.
    '''
    return await admin_list_slides_controller(
        dynamodb_resource = dynamodb_resource,
        request = request, current_user = current_user,
    )


@router.post(
    '/slides',
    response_model = SlideAdminItem,
    status_code = status.HTTP_201_CREATED,
    summary = 'Create a slide.',
)
async def admin_create_slide(
    payload: SlideCreate,
    request: Request,
    dynamodb_resource: ServiceResource = Depends(get_db_dependency),
    current_user: str = Depends(get_current_user),
):
    '''
        Creates a slide.
    '''
    return await admin_create_slide_controller(
        dynamodb_resource = dynamodb_resource,
        request = request, current_user = current_user,
        payload = payload,
    )


@router.get(
    '/slides/{slide_id}',
    response_model = SlideAdminItem,
    summary = 'Retrieve a single slide by id.',
)
async def admin_get_slide(
    request: Request,
    slide_id: str = Path(..., min_length = 1),
    dynamodb_resource: ServiceResource = Depends(get_db_dependency),
    current_user: str = Depends(get_current_user),
):
    '''
        Returns a single slide.
    '''
    return await admin_get_slide_controller(
        dynamodb_resource = dynamodb_resource,
        request = request, current_user = current_user,
        slide_id = slide_id,
    )


@router.put(
    '/slides/{slide_id}',
    response_model = SlideAdminItem,
    summary = 'Partial update of a slide.',
)
async def admin_update_slide(
    payload: SlideUpdate,
    request: Request,
    slide_id: str = Path(..., min_length = 1),
    dynamodb_resource: ServiceResource = Depends(get_db_dependency),
    current_user: str = Depends(get_current_user),
):
    '''
        Updates only the supplied fields on the target slide.
    '''
    return await admin_update_slide_controller(
        dynamodb_resource = dynamodb_resource,
        request = request, current_user = current_user,
        slide_id = slide_id, payload = payload,
    )


@router.delete(
    '/slides/{slide_id}',
    response_model = DeleteResponse,
    summary = 'Delete a slide.',
)
async def admin_delete_slide(
    request: Request,
    slide_id: str = Path(..., min_length = 1),
    dynamodb_resource: ServiceResource = Depends(get_db_dependency),
    current_user: str = Depends(get_current_user),
):
    '''
        Deletes a slide by id.
    '''
    return await admin_delete_slide_controller(
        dynamodb_resource = dynamodb_resource,
        request = request, current_user = current_user,
        slide_id = slide_id,
    )


# ============================================================
# Entities
# ============================================================

@router.get(
    '/entities',
    response_model = EntityAdminListResponse,
    summary = 'List every entity (including inactive).',
)
async def admin_list_entities(
    request: Request,
    dynamodb_resource: ServiceResource = Depends(get_db_dependency),
    current_user: str = Depends(get_current_user),
):
    '''
        Admin listing of all entities.
    '''
    return await admin_list_entities_controller(
        dynamodb_resource = dynamodb_resource,
        request = request, current_user = current_user,
    )


@router.post(
    '/entities',
    response_model = EntityAdminItem,
    status_code = status.HTTP_201_CREATED,
    summary = 'Create an entity.',
)
async def admin_create_entity(
    payload: EntityCreate,
    request: Request,
    dynamodb_resource: ServiceResource = Depends(get_db_dependency),
    current_user: str = Depends(get_current_user),
):
    '''
        Creates an institutional entity.
    '''
    return await admin_create_entity_controller(
        dynamodb_resource = dynamodb_resource,
        request = request, current_user = current_user,
        payload = payload,
    )


@router.get(
    '/entities/{entity_id}',
    response_model = EntityAdminItem,
    summary = 'Retrieve a single entity by id.',
)
async def admin_get_entity(
    request: Request,
    entity_id: str = Path(..., min_length = 1),
    dynamodb_resource: ServiceResource = Depends(get_db_dependency),
    current_user: str = Depends(get_current_user),
):
    '''
        Returns a single entity.
    '''
    return await admin_get_entity_controller(
        dynamodb_resource = dynamodb_resource,
        request = request, current_user = current_user,
        entity_id = entity_id,
    )


@router.put(
    '/entities/{entity_id}',
    response_model = EntityAdminItem,
    summary = 'Partial update of an entity.',
)
async def admin_update_entity(
    payload: EntityUpdate,
    request: Request,
    entity_id: str = Path(..., min_length = 1),
    dynamodb_resource: ServiceResource = Depends(get_db_dependency),
    current_user: str = Depends(get_current_user),
):
    '''
        Updates only the supplied fields on the target entity.
    '''
    return await admin_update_entity_controller(
        dynamodb_resource = dynamodb_resource,
        request = request, current_user = current_user,
        entity_id = entity_id, payload = payload,
    )


@router.delete(
    '/entities/{entity_id}',
    response_model = DeleteResponse,
    summary = 'Delete an entity.',
)
async def admin_delete_entity(
    request: Request,
    entity_id: str = Path(..., min_length = 1),
    dynamodb_resource: ServiceResource = Depends(get_db_dependency),
    current_user: str = Depends(get_current_user),
):
    '''
        Deletes an entity by id.
    '''
    return await admin_delete_entity_controller(
        dynamodb_resource = dynamodb_resource,
        request = request, current_user = current_user,
        entity_id = entity_id,
    )
