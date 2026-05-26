'''
    CMS DynamoDB models.

    Per-entity table design (4 tables, partition key = id). Sorting and
    filtering happen in Python after Scan because the public read workload
    is low volume and the access pattern is "list everything published".
    When growth justifies it, switch each table to a GSI on (lang, sort_order)
    and replace the scans with queries.
'''
from typing import Optional, TypedDict


CMS_NEWS_TABLE = 't_cms_news'
CMS_DOCUMENTS_TABLE = 't_cms_documents'
CMS_SLIDES_TABLE = 't_cms_slides'
CMS_ENTITIES_TABLE = 't_cms_entities'


class CmsNewsItem(TypedDict, total = False):
    '''
        News entry document.

        Table: t_cms_news
        Partition Key: id (String, uuid)

        Types: press | communique | photo | article.
    '''
    id: str
    lang: str
    type: str
    title: str
    summary: Optional[str]
    body: Optional[str]
    image_s3_bucket: Optional[str]
    image_s3_key: Optional[str]
    external_url: Optional[str]
    published_at: Optional[str] # ISO 8601 datetime.
    is_published: bool
    sort_order: int
    created_at: str
    updated_at: str


class CmsDocumentItem(TypedDict, total = False):
    '''
        Downloadable publication document.

        Table: t_cms_documents
        Partition Key: id (String, uuid)
    '''
    id: str
    lang: str
    title: str
    doc_type: str # PDF | DOC | LEY | ...
    doc_date: Optional[str] # ISO date (YYYY-MM-DD).
    file_s3_bucket: Optional[str]
    file_s3_key: Optional[str]
    file_external_url: Optional[str]
    is_published: bool
    sort_order: int
    created_at: str
    updated_at: str


class CmsSlideItem(TypedDict, total = False):
    '''
        Hero slider entry shown on the landing page.

        Table: t_cms_slides
        Partition Key: id (String, uuid)
    '''
    id: str
    lang: str
    title: str
    description: Optional[str]
    image_s3_bucket: Optional[str]
    image_s3_key: Optional[str]
    link_url: Optional[str]
    sort_order: int
    is_active: bool
    created_at: str
    updated_at: str


class CmsEntityItem(TypedDict, total = False):
    '''
        Affiliated institutional entity (VINTO, COMIBOL, AJAM...).

        Table: t_cms_entities
        Partition Key: id (String, uuid)

        Entity names are not translated, so this document is language-agnostic.
    '''
    id: str
    name: str
    short_description: Optional[str]
    url: str
    logo_s3_bucket: Optional[str]
    logo_s3_key: Optional[str]
    sort_order: int
    is_active: bool
    created_at: str
    updated_at: str
