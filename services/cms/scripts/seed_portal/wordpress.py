'''
    WordPress client used by the seeder.

    Two surfaces:
      - REST discovery: paginated listing per Custom Post Type so we can
        enumerate every item without scraping listing pages.
      - HTML detail fetch + parsing: the CPTs do not expose `content`
        through REST, so we hit each post URL and pull the body, the
        hero image, and the "best matching" external link out of the
        `.detalle-nota` container.

    The portal's WP theme injects shared chrome (carousels, sidebars) at
    the bottom of every detail page, so we cut the body before those
    markers and we match anchors by visible text against the post title
    to pick the right external URL for entities.
'''
from dataclasses import dataclass
from html import unescape
from time import sleep
from typing import Iterable, List, Optional
from unicodedata import normalize
from urllib.parse import urljoin, urlparse
import re

import requests
from bs4 import BeautifulSoup

from .mappings import is_theme_asset


DEFAULT_PER_PAGE = 50
DEFAULT_USER_AGENT = 'Mozilla/5.0 Chrome/130'

# Markers used by the WP theme to introduce recurring side carousels at
# the end of each detail page. Anything past these belongs to chrome, not
# to the post itself.
CHROME_MARKERS = (
    'Notas recientes', 'Comunicados recientes', 'Enlaces de interés',
    'Direcciones recientes', 'Ver todas las notas',
    'Ver todos los comunicados', 'Ver todas los enlaces',
    'Ver todas las direcciones',
)


@dataclass
class WpItem:
    '''
        Lightweight record returned by the REST discovery step.
    '''
    id: int
    title: str
    slug: str
    link: str
    date_iso: Optional[str]


@dataclass
class DetailPayload:
    '''
        Result of parsing a WP detail page.
    '''
    body_text: str
    image_url: Optional[str]
    pdf_url: Optional[str]
    external_url: Optional[str]


class WordPressClient:
    '''
        Reads the WP REST API and parses the matching HTML detail pages.
    '''

    def __init__(self, source_url: str, rate_limit_ms: int = 200,
                 timeout: int = 30,
                 user_agent: str = DEFAULT_USER_AGENT):
        self.source_url = source_url.rstrip('/')
        self.rate_limit_sec = max(rate_limit_ms, 0) / 1000.0
        self.timeout = timeout
        self.headers = {'User-Agent': user_agent}
        self.source_host = urlparse(self.source_url).netloc.lower()

    # ---------- REST ----------

    def list_items(self, rest_base: str, limit: Optional[int] = None
                   ) -> Iterable[WpItem]:
        '''
            Yields every post in the given CPT, page by page.
        '''
        page = 1
        yielded = 0
        while True:
            params = {'per_page': DEFAULT_PER_PAGE, 'page': page,
                      'orderby': 'date', 'order': 'asc'}
            response = requests.get(
                f'{self.source_url}/wp-json/wp/v2/{rest_base}',
                params = params, headers = self.headers,
                timeout = self.timeout,
            )
            if response.status_code == 400:
                # WP returns 400 when paging past the end.
                return
            response.raise_for_status()
            items = response.json()
            if not items:
                return
            for raw in items:
                yield WpItem(
                    id = raw.get('id'),
                    title = _decode_title(raw),
                    slug = raw.get('slug', ''),
                    link = raw.get('link', ''),
                    date_iso = raw.get('date'),
                )
                yielded += 1
                if limit is not None and yielded >= limit:
                    return
            total_pages = int(response.headers.get('X-WP-TotalPages') or 0)
            if total_pages and page >= total_pages:
                return
            page += 1

    # ---------- HTML detail ----------

    def fetch_detail(self, item: WpItem) -> Optional[DetailPayload]:
        '''
            Fetches and parses the post's detail page. Returns None when
            the page is unreachable so the caller can skip without
            blowing up the whole run.
        '''
        if self.rate_limit_sec:
            sleep(self.rate_limit_sec)
        try:
            response = requests.get(item.link, headers = self.headers,
                                    timeout = self.timeout)
        except requests.RequestException:
            return None
        if not response.ok:
            return None
        return self._parse_detail(response.text, item)

    def _parse_detail(self, html: str, item: WpItem) -> DetailPayload:
        soup = BeautifulSoup(html, 'html.parser')
        container = soup.find(class_ = 'detalle-nota') or soup

        body_text = _trim_to_chrome(container.get_text(' ', strip = True))
        image_url = self._first_image(container, item.link)
        pdf_url = self._first_pdf(container, item.link)
        external_url = self._best_external_link(container, item)
        return DetailPayload(
            body_text = body_text,
            image_url = image_url,
            pdf_url = pdf_url,
            external_url = external_url,
        )

    def _first_image(self, container, page_url: str) -> Optional[str]:
        for img in container.find_all('img'):
            src = img.get('src') or img.get('data-src')
            if not src:
                continue
            absolute = urljoin(page_url, src)
            if is_theme_asset(absolute):
                continue
            return absolute
        return None

    def _first_pdf(self, container, page_url: str) -> Optional[str]:
        for anchor in container.find_all('a', href = True):
            href = anchor['href'].strip()
            if href.lower().split('?', 1)[0].endswith('.pdf'):
                return urljoin(page_url, href)
        return None

    def _best_external_link(self, container, item: WpItem) -> Optional[str]:
        '''
            Picks the anchor whose visible text best matches the post
            title. Falls back to the slug/title token match against the
            hostname. Returns None when nothing reasonable is found.

            The WP theme inserts a global "Enlaces de interés" carousel
            on every detail page, so plain "first external link" is not
            sufficient — that always returns the first carousel entry.
        '''
        title_norm = _normalize(item.title)
        slug_tokens = {t for t in _normalize(item.slug).split() if t}
        title_tokens = {t for t in title_norm.split() if t}
        wanted_tokens = title_tokens | slug_tokens

        candidates: list[tuple[int, str]] = []
        for anchor in container.find_all('a', href = True):
            href = anchor['href'].strip()
            if not href.startswith(('http://', 'https://')):
                continue
            host = urlparse(href).netloc.lower()
            if not host or host == self.source_host \
                    or host.endswith('.' + self.source_host):
                continue
            text_norm = _normalize(anchor.get_text(' ', strip = True))
            score = 0
            if title_norm and title_norm in text_norm:
                score += 100
            elif text_norm and text_norm in title_norm:
                score += 80
            score += sum(1 for t in wanted_tokens if t and t in text_norm)
            host_stem = host.split('.', 1)[0].replace('www', '').strip('-')
            if host_stem and host_stem in wanted_tokens:
                score += 50
            candidates.append((score, href))

        if not candidates:
            return None
        candidates.sort(key = lambda pair: pair[0], reverse = True)
        best_score, best_href = candidates[0]
        # Only accept matches that scored something — picking a random
        # carousel entry is worse than dropping the field.
        return best_href if best_score > 0 else None


def _decode_title(raw: dict) -> str:
    title = raw.get('title')
    if isinstance(title, dict):
        return unescape(title.get('rendered') or '').strip()
    return unescape(str(title or '')).strip()


def _normalize(text: str) -> str:
    '''
        Lowercases, strips diacritics, replaces non-alphanumerics with
        spaces, and collapses repeated whitespace. Suitable for fuzzy
        token matching.
    '''
    if not text:
        return ''
    decomposed = normalize('NFD', text)
    stripped = ''.join(c for c in decomposed if not (0x300 <= ord(c) <= 0x36F))
    cleaned = re.sub(r'[^a-z0-9]+', ' ', stripped.lower()).strip()
    return ' '.join(cleaned.split())


def _trim_to_chrome(text: str) -> str:
    '''
        The WP theme appends shared sidebars/carousels after each post.
        We cut at the first known chrome marker so summaries do not bleed
        into navigation copy.
    '''
    if not text:
        return ''
    cleaned = ' '.join(text.split())
    cut_at = len(cleaned)
    for marker in CHROME_MARKERS:
        idx = cleaned.find(marker)
        if idx >= 0 and idx < cut_at:
            cut_at = idx
    return cleaned[:cut_at].strip()
