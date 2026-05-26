'''
    CMS Schemas (Request/Response).

    These DTOs are exposed by the public read endpoints consumed by the
    institutional portal. Asset references (S3 bucket/key) are resolved into
    a single `*_url` string by the service layer before reaching this schema.
'''
from datetime import datetime, date
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class CmsBaseSchema(BaseModel):
    '''
        Base schema enabling ORM attribute mapping for nested models.
    '''
    model_config = ConfigDict(from_attributes = True)


# ---------- News ----------

class NewsItem(CmsBaseSchema):
    '''
        Editorial entry shown in the portal news section.

        `image_url` is the resolved asset URL (S3 public URL if available);
        `external_url` is the article destination when the news links out.
    '''
    id: str
    lang: str = Field(..., max_length = 2)
    type: str = Field(..., max_length = 50,
                      description = 'press | communique | photo | article.')
    title: str = Field(..., max_length = 255)
    summary: Optional[str] = Field(None, max_length = 500)
    body: Optional[str] = None
    image_url: Optional[str] = None
    external_url: Optional[str] = None
    published_at: Optional[datetime] = None
    sort_order: int = 0


class NewsListResponse(BaseModel):
    '''
        Paginated-style envelope for the public news list endpoint.
    '''
    status: str = 'success'
    message: str = 'News retrieved.'
    lang: str
    items: List[NewsItem]


# ---------- Documents ----------

class DocumentItem(CmsBaseSchema):
    '''
        Downloadable publication exposed on the portal.

        `file_url` resolves the S3 reference or the external URL fallback.
    '''
    id: str
    lang: str = Field(..., max_length = 2)
    title: str = Field(..., max_length = 255)
    doc_type: str = Field(..., max_length = 50,
                          description = 'Format / classification (PDF, DOC, LEY...).')
    doc_date: Optional[date] = None
    file_url: Optional[str] = None
    sort_order: int = 0


class DocumentListResponse(BaseModel):
    '''
        Envelope for the public documents endpoint.
    '''
    status: str = 'success'
    message: str = 'Documents retrieved.'
    lang: str
    items: List[DocumentItem]


# ---------- Slides ----------

class SlideItem(CmsBaseSchema):
    '''
        Hero slider entry shown on the portal landing page.
    '''
    id: str
    lang: str = Field(..., max_length = 2)
    title: str = Field(..., max_length = 255)
    description: Optional[str] = Field(None, max_length = 500)
    image_url: Optional[str] = None
    link_url: Optional[str] = None
    sort_order: int = 0


class SlideListResponse(BaseModel):
    '''
        Envelope for the public slides endpoint.
    '''
    status: str = 'success'
    message: str = 'Slides retrieved.'
    lang: str
    items: List[SlideItem]


# ---------- Entities ----------

class EntityItem(CmsBaseSchema):
    '''
        Affiliated institutional entity.

        Entity names are not translated, so this DTO has no `lang` field.
    '''
    id: str
    name: str = Field(..., max_length = 100)
    short_description: Optional[str] = Field(None, max_length = 255)
    url: str = Field(..., max_length = 500)
    logo_url: Optional[str] = None
    sort_order: int = 0


class EntityListResponse(BaseModel):
    '''
        Envelope for the public entities endpoint.
    '''
    status: str = 'success'
    message: str = 'Entities retrieved.'
    items: List[EntityItem]
