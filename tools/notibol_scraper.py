'''
    Notibol news scraper by date.

    Scrapes the economy section of https://notibol.com for a given day and writes
    an Excel file with one row per news item:
        Fecha · Medio · Titular · Enlace

    The listing is paginated (page N is the base URL with a trailing '/N'); the
    scraper follows the 'next page' links until there are no more.

    Usage (run from the app root):
        python tools/notibol_scraper.py --fecha 2026-08-04
        python tools/notibol_scraper.py --fecha 2026-08-04 --out /ruta/noticias.xlsx
        python tools/notibol_scraper.py --fecha 2026-08-04 --base https://notibol.com/bolivia/economia

    Requires: requests, beautifulsoup4, openpyxl.
'''
import argparse
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from urllib.parse import urljoin

import openpyxl
import requests
from bs4 import BeautifulSoup
from openpyxl.styles import Alignment, Font, PatternFill

BASE_URL = 'https://notibol.com/bolivia/economia'
SITE_ROOT = 'https://notibol.com'
REQUEST_TIMEOUT = 20
PAGE_DELAY_SECONDS = 1.0  # be polite between page requests
USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36'
)

_HEADER_FILL = PatternFill('solid', fgColor = '0D1E4C')
_HEADER_FONT = Font(bold = True, color = 'FFFFFF')
COLUMNS = ['Fecha', 'Medio', 'Titular', 'Enlace']


def _fetch(url: str) -> str:
    '''
        Downloads a page and returns its HTML, raising for non-2xx responses.
    '''
    response = requests.get(url, headers = {'User-Agent': USER_AGENT}, timeout = REQUEST_TIMEOUT)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or 'utf-8'
    return response.text


_redirect_cache: dict = {}


def _resolve_original_url(go_url: str) -> str:
    '''
        Resolves a Notibol '/go/bo/<hash>' redirect to the original article URL
        on the source outlet. Results are cached; on any failure the redirect
        URL itself is returned so a row is never left without a link.
    '''
    if not go_url:
        return ''
    if go_url in _redirect_cache:
        return _redirect_cache[go_url]
    try:
        # Short timeout: a slow outlet must not stall the whole batch (we keep
        # the redirect URL as fallback on timeout).
        response = requests.head(
            go_url, headers = {'User-Agent': USER_AGENT},
            allow_redirects = True, timeout = 8
        )
        resolved = response.url or go_url
    except requests.RequestException:
        resolved = go_url
    _redirect_cache[go_url] = resolved
    return resolved


def _absolute(href: str) -> str:
    '''Turns a site-relative or protocol-relative href into an absolute URL.'''
    if not href:
        return ''
    if href.startswith('//'):
        return 'https:' + href
    return urljoin(SITE_ROOT + '/', href.lstrip('/'))


def _parse_news_item(block, fecha: str) -> dict:
    '''
        Extracts one news row from a `.noticia` block.

        Args:
            block: BeautifulSoup node for a single `.noticia` container.
            fecha (str): The queried date (yyyy-mm-dd), used for the Fecha column.

        Returns:
            dict: Row keyed by the Spanish column names.
    '''
    title_link = block.select_one('h3.titular a')
    titular = title_link.get_text(strip = True) if title_link else ''

    # Headline link -> the news page on Notibol (the site we scrape).
    notibol_link = block.select_one('a[href^="/noticia/bo/"]')
    enlace_notibol = _absolute(notibol_link['href']) if notibol_link else ''

    # "Enlace a la noticia" -> the ORIGINAL article on the source outlet. Stored
    # here as Notibol's '/go/bo/<hash>' redirect; resolved to the final media URL
    # in parallel after all pages are parsed (see scrape_date).
    go_href = title_link['href'] if title_link and title_link.has_attr('href') else ''
    go_url = _absolute(go_href) if go_href else ''

    # Source outlet that published the original story (e.g. "Agencia de Noticias
    # Fides"), shown on the page next to the headline.
    medio_link = block.select_one('a[href^="/medio/"]')
    medio = medio_link.get_text(strip = True) if medio_link else ''

    return {
        'Fecha': fecha,
        'Medio': medio,
        'Titular': titular,
        'Titular_link': enlace_notibol,   # hyperlink target for the headline
        'Enlace': go_url,                 # resolved to the media URL later
    }


def _has_next_page(soup, current_page: int) -> bool:
    '''
        Tells whether a link to page `current_page + 1` exists in the pagination.
    '''
    target = f'/{current_page + 1}'
    for link in soup.select('.pagination a[href]'):
        if link['href'].rstrip('/').endswith(target):
            return True
    return False


def scrape_date(fecha: str, base: str = BASE_URL) -> list:
    '''
        Scrapes every page of the listing for the given date.

        Args:
            fecha (str): Date in yyyy-mm-dd format.
            base (str): Section base URL (without the date).

        Returns:
            list[dict]: One row per news item, de-duplicated by news link.
    '''
    rows = []
    seen_links = set()
    page = 1
    while True:
        url = f'{base}/{fecha}' if page == 1 else f'{base}/{fecha}/{page}'
        print(f'  Página {page}: {url}')
        soup = BeautifulSoup(_fetch(url), 'html.parser')

        blocks = soup.select('.noticia')
        if not blocks:
            break
        for block in blocks:
            row = _parse_news_item(block, fecha)
            # De-duplicate across pages by the Notibol news page (fallback title).
            key = row.get('Titular_link') or row['Titular']
            if key and key not in seen_links:
                seen_links.add(key)
                rows.append(row)

        if not _has_next_page(soup, page):
            break
        page += 1
        time.sleep(PAGE_DELAY_SECONDS)

    _resolve_original_links(rows)
    return rows


def _resolve_original_links(rows: list) -> None:
    '''
        Resolves every row's 'Enlace a la noticia' from the Notibol redirect to
        the original media URL, in parallel (a few threads) so ~70 lookups take
        seconds instead of minutes. Mutates the rows in place.
    '''
    go_urls = {row['Enlace'] for row in rows if row['Enlace']}
    if not go_urls:
        return
    print(f'  Resolviendo {len(go_urls)} enlace(s) a la fuente original...')
    with ThreadPoolExecutor(max_workers = 8) as pool:
        resolved = dict(zip(go_urls, pool.map(_resolve_original_url, go_urls)))
    for row in rows:
        row['Enlace'] = resolved.get(row['Enlace'], row['Enlace'])


def write_excel(rows: list, output_path: str) -> str:
    '''
        Writes the scraped rows to a styled .xlsx and returns the path.
    '''
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = 'Noticias'

    for col_index, header in enumerate(COLUMNS, start = 1):
        cell = worksheet.cell(row = 1, column = col_index, value = header)
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
    worksheet.freeze_panes = 'A2'

    link_font = Font(color = '0563C1', underline = 'single')
    for row_index, row in enumerate(rows, start = 2):
        for col_index, header in enumerate(COLUMNS, start = 1):
            cell = worksheet.cell(row = row_index, column = col_index, value = row[header])
            cell.alignment = Alignment(vertical = 'top')
            # Titular -> Notibol news page (the scraped site);
            # Enlace -> original article on the source outlet.
            if header == 'Titular' and row.get('Titular_link'):
                cell.hyperlink = row['Titular_link']
                cell.font = link_font
            elif header == 'Enlace' and row['Enlace']:
                cell.hyperlink = row['Enlace']
                cell.font = link_font

    widths = {'Fecha': 12, 'Medio': 26, 'Titular': 55, 'Enlace': 60}
    for col_index, header in enumerate(COLUMNS, start = 1):
        worksheet.column_dimensions[worksheet.cell(row = 1, column = col_index).column_letter].width = \
            widths[header]

    workbook.save(output_path)
    return output_path


def main() -> None:
    '''Entry point: scrape the given date and write the Excel file.'''
    parser = argparse.ArgumentParser(description = 'Scrapea noticias de Notibol por fecha.')
    parser.add_argument('--fecha', required = True, help = 'Fecha en formato yyyy-mm-dd.')
    parser.add_argument('--base', default = BASE_URL, help = f'URL base (default: {BASE_URL}).')
    parser.add_argument('--out', default = None, help = 'Ruta del .xlsx de salida.')
    args = parser.parse_args()

    # Validate the date format so a typo fails fast instead of scraping garbage.
    try:
        datetime.strptime(args.fecha, '%Y-%m-%d')
    except ValueError:
        parser.error('--fecha debe tener el formato yyyy-mm-dd (ej. 2026-08-04).')

    output_path = args.out or f'notibol_economia_{args.fecha}.xlsx'
    print(f'Scrapeando {args.base} para la fecha {args.fecha}...')
    rows = scrape_date(args.fecha, args.base)
    write_excel(rows, output_path)
    print(f'\nListo: {len(rows)} noticia(s) -> {output_path}')


if __name__ == '__main__':
    main()
