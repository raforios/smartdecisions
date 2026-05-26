'''
    Mapping table: WordPress CPT → CMS entity.

    Each entry declares which CMS table receives the item and the fixed
    fields to attach (news.type, documents.doc_type). The seeder loops
    over this list and calls the matching CMS endpoint.

    `THEME_ASSET_PATTERNS` lists URL substrings that mark images
    belonging to the WordPress theme (logos, banners, decorative footer
    art) — they are skipped when picking the hero image of an item.
'''
from typing import Dict, List, Optional


# Path inside the source URL that indicates the asset is part of the WP
# theme / repeated chrome, not the post's own content.
THEME_ASSET_PATTERNS = (
    '/wp-content/themes/',
    '/wp-content/plugins/',
    '/assets/images/bandera',
    '/assets/images/alpha-web',
    '/cropped-escudo',
    '/escudo_contraste',
)


# ---------- News ----------
# Each "news" CPT maps to the value of `NewsType` enforced by the CMS schema
# (press | communique | photo | article).
NEWS_SOURCES: List[Dict[str, str]] = [
    {'rest_base': 'nota_prensa', 'cms_type': 'press',      'sub_path': 'news/press'},
    {'rest_base': 'comunicados', 'cms_type': 'communique', 'sub_path': 'news/communique'},
    {'rest_base': 'galeria',     'cms_type': 'photo',      'sub_path': 'news/photo'},
    {'rest_base': 'campania',    'cms_type': 'article',    'sub_path': 'news/article'},
]


# ---------- Documents ----------
# CPTs whose items are official documents. `doc_type` is the short string
# rendered on the public portal as the tag (PDF, LEY, REGLAMENTO, ...).
DOCUMENT_SOURCES: List[Dict[str, str]] = [
    {'rest_base': 'normativa',           'doc_type': 'LEY',          'sub_path': 'documents/leyes'},
    {'rest_base': 'normativa-inter',     'doc_type': 'REGLAMENTO',   'sub_path': 'documents/reglamentos'},
    {'rest_base': 'boletin',             'doc_type': 'BOLETIN',      'sub_path': 'documents/boletines'},
    {'rest_base': 'memoria',             'doc_type': 'MEMORIA',      'sub_path': 'documents/memorias'},
    {'rest_base': 'auditoria',           'doc_type': 'AUDITORIA',    'sub_path': 'documents/auditorias'},
    {'rest_base': 'manual_organizacion', 'doc_type': 'MANUAL',       'sub_path': 'documents/manuales'},
    {'rest_base': 'procedimientos',      'doc_type': 'PROCEDIMIENTO','sub_path': 'documents/procedimientos'},
    {'rest_base': 'poa',                 'doc_type': 'POA',          'sub_path': 'documents/poa'},
    {'rest_base': 'presupuesto',         'doc_type': 'PRESUPUESTO',  'sub_path': 'documents/presupuesto'},
    {'rest_base': 'rendicion_cuenta',    'doc_type': 'RENDICION',    'sub_path': 'documents/rendicion'},
    {'rest_base': 'investigacion',       'doc_type': 'INVESTIGACION','sub_path': 'documents/investigacion'},
    {'rest_base': 'documentos',          'doc_type': 'DOCUMENTO',    'sub_path': 'documents/general'},
]


# ---------- Entities ----------
# Single CPT; URL is extracted from the post body (first external link
# that is not the source portal itself).
ENTITY_SOURCE: Dict[str, str] = {
    'rest_base': 'enlace_interes', 'sub_path': 'entities',
}


def is_theme_asset(url: Optional[str]) -> bool:
    '''
        True when the URL matches a WordPress theme/chrome asset.
    '''
    if not url:
        return True
    return any(pattern in url for pattern in THEME_ASSET_PATTERNS)
