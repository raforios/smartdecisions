'''
    CMS Admin Schemas (Create / Update / AdminItem).

    Update schemas have every field Optional so the admin UI can issue
    partial updates (PATCH-like semantics on a PUT verb).

    Asset references travel as `*_s3_bucket` + `*_s3_key` pairs. The admin
    uploads the binary to the FILES microservice in a separate step and
    only sends the resulting references here; the CMS never proxies file
    bytes.
'''
from datetime import datetime, date
from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


# Canonical set of news classifications. Kept here (instead of in models/)
# because it's a presentation/business constraint that belongs with the
# request validation layer.
NewsType = Literal['press', 'communique', 'photo', 'article']


class CmsAdminBaseSchema(BaseModel):
    '''
        Base schema for admin payloads. Allows extra=ignore so future
        front-end fields don't break older deploys.
    '''
    model_config = ConfigDict(extra = 'ignore')


# ============================================================
# News
# ============================================================

class NewsCreate(CmsAdminBaseSchema):
    '''
        Payload to create a news entry.
    '''
    lang: str = Field('es', max_length = 2)
    type: NewsType = Field(...,
                           description = 'press | communique | photo | article.')
    title: str = Field(..., max_length = 255)
    summary: Optional[str] = Field(None, max_length = 500)
    body: Optional[str] = None
    image_s3_bucket: Optional[str] = Field(None, max_length = 100)
    image_s3_key: Optional[str] = Field(None, max_length = 500)
    external_url: Optional[str] = Field(None, max_length = 500)
    published_at: Optional[datetime] = None
    is_published: bool = True
    sort_order: int = 0


class NewsUpdate(CmsAdminBaseSchema):
    '''
        Partial update payload. Only non-None fields are persisted.
    '''
    lang: Optional[str] = Field(None, max_length = 2)
    type: Optional[NewsType] = None
    title: Optional[str] = Field(None, max_length = 255)
    summary: Optional[str] = Field(None, max_length = 500)
    body: Optional[str] = None
    image_s3_bucket: Optional[str] = Field(None, max_length = 100)
    image_s3_key: Optional[str] = Field(None, max_length = 500)
    external_url: Optional[str] = Field(None, max_length = 500)
    published_at: Optional[datetime] = None
    is_published: Optional[bool] = None
    sort_order: Optional[int] = None


class NewsAdminItem(CmsAdminBaseSchema):
    '''
        Admin-facing news item. Exposes raw asset refs *and* the resolved
        public URL so the panel can show a thumbnail without re-resolving.
    '''
    id: str
    lang: str
    type: NewsType
    title: str
    summary: Optional[str] = None
    body: Optional[str] = None
    image_s3_bucket: Optional[str] = None
    image_s3_key: Optional[str] = None
    image_url: Optional[str] = None
    external_url: Optional[str] = None
    published_at: Optional[datetime] = None
    is_published: bool
    sort_order: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class NewsAdminListResponse(BaseModel):
    '''
        Envelope for the admin news listing.
    '''
    status: str = 'success'
    message: str = 'News retrieved.'
    items: List[NewsAdminItem]


# ============================================================
# Documents
# ============================================================

class DocumentCreate(CmsAdminBaseSchema):
    '''
        Payload to create a document entry.
    '''
    lang: str = Field('es', max_length = 2)
    title: str = Field(..., max_length = 255)
    doc_type: str = Field(..., max_length = 50)
    doc_date: Optional[date] = None
    file_s3_bucket: Optional[str] = Field(None, max_length = 100)
    file_s3_key: Optional[str] = Field(None, max_length = 500)
    file_external_url: Optional[str] = Field(None, max_length = 500)
    is_published: bool = True
    sort_order: int = 0


class DocumentUpdate(CmsAdminBaseSchema):
    '''
        Partial update payload.
    '''
    lang: Optional[str] = Field(None, max_length = 2)
    title: Optional[str] = Field(None, max_length = 255)
    doc_type: Optional[str] = Field(None, max_length = 50)
    doc_date: Optional[date] = None
    file_s3_bucket: Optional[str] = Field(None, max_length = 100)
    file_s3_key: Optional[str] = Field(None, max_length = 500)
    file_external_url: Optional[str] = Field(None, max_length = 500)
    is_published: Optional[bool] = None
    sort_order: Optional[int] = None


class DocumentAdminItem(CmsAdminBaseSchema):
    '''
        Admin-facing document item.
    '''
    id: str
    lang: str
    title: str
    doc_type: str
    doc_date: Optional[date] = None
    file_s3_bucket: Optional[str] = None
    file_s3_key: Optional[str] = None
    file_external_url: Optional[str] = None
    file_url: Optional[str] = None
    is_published: bool
    sort_order: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DocumentAdminListResponse(BaseModel):
    '''
        Envelope for the admin documents listing.
    '''
    status: str = 'success'
    message: str = 'Documents retrieved.'
    items: List[DocumentAdminItem]


# ============================================================
# Slides
# ============================================================

class SlideCreate(CmsAdminBaseSchema):
    '''
        Payload to create a slide.
    '''
    lang: str = Field('es', max_length = 2)
    title: str = Field(..., max_length = 255)
    description: Optional[str] = Field(None, max_length = 500)
    image_s3_bucket: Optional[str] = Field(None, max_length = 100)
    image_s3_key: Optional[str] = Field(None, max_length = 500)
    link_url: Optional[str] = Field(None, max_length = 500)
    is_active: bool = True
    sort_order: int = 0


class SlideUpdate(CmsAdminBaseSchema):
    '''
        Partial update payload.
    '''
    lang: Optional[str] = Field(None, max_length = 2)
    title: Optional[str] = Field(None, max_length = 255)
    description: Optional[str] = Field(None, max_length = 500)
    image_s3_bucket: Optional[str] = Field(None, max_length = 100)
    image_s3_key: Optional[str] = Field(None, max_length = 500)
    link_url: Optional[str] = Field(None, max_length = 500)
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


class SlideAdminItem(CmsAdminBaseSchema):
    '''
        Admin-facing slide item.
    '''
    id: str
    lang: str
    title: str
    description: Optional[str] = None
    image_s3_bucket: Optional[str] = None
    image_s3_key: Optional[str] = None
    image_url: Optional[str] = None
    link_url: Optional[str] = None
    is_active: bool
    sort_order: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SlideAdminListResponse(BaseModel):
    '''
        Envelope for the admin slides listing.
    '''
    status: str = 'success'
    message: str = 'Slides retrieved.'
    items: List[SlideAdminItem]


# ============================================================
# Entities
# ============================================================

class EntityCreate(CmsAdminBaseSchema):
    '''
        Payload to create an entity.
    '''
    name: str = Field(..., max_length = 100)
    short_description: Optional[str] = Field(None, max_length = 255)
    url: str = Field(..., max_length = 500)
    logo_s3_bucket: Optional[str] = Field(None, max_length = 100)
    logo_s3_key: Optional[str] = Field(None, max_length = 500)
    is_active: bool = True
    sort_order: int = 0


class EntityUpdate(CmsAdminBaseSchema):
    '''
        Partial update payload.
    '''
    name: Optional[str] = Field(None, max_length = 100)
    short_description: Optional[str] = Field(None, max_length = 255)
    url: Optional[str] = Field(None, max_length = 500)
    logo_s3_bucket: Optional[str] = Field(None, max_length = 100)
    logo_s3_key: Optional[str] = Field(None, max_length = 500)
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


class EntityAdminItem(CmsAdminBaseSchema):
    '''
        Admin-facing entity item.
    '''
    id: str
    name: str
    short_description: Optional[str] = None
    url: str
    logo_s3_bucket: Optional[str] = None
    logo_s3_key: Optional[str] = None
    logo_url: Optional[str] = None
    is_active: bool
    sort_order: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class EntityAdminListResponse(BaseModel):
    '''
        Envelope for the admin entities listing.
    '''
    status: str = 'success'
    message: str = 'Entities retrieved.'
    items: List[EntityAdminItem]


# ============================================================
# Common
# ============================================================

class DeleteResponse(BaseModel):
    '''
        Standard response for delete operations.
    '''
    status: str = 'success'
    message: str
    id: str
