'''
    Entry point of the seed_portal package.

    Pulls content from the WordPress portal of the Ministry, downloads
    the binaries it references, and pushes everything into the local CMS
    via its admin endpoints. Designed as a one-shot.

    Usage:
        cd services/cms
        python -m scripts.seed_portal --wipe
        python -m scripts.seed_portal --only news --limit 5 --dry-run
'''
import argparse
import getpass
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import dotenv_values

from .auth import AuthClient
from .cms import CmsAdminClient
from .files import FilesClient
from .mappings import (
    DOCUMENT_SOURCES,
    ENTITY_SOURCE,
    NEWS_SOURCES,
)
from .wordpress import DetailPayload, WordPressClient, WpItem


DEFAULT_SOURCE_URL = 'https://www.mineria.gob.bo'
# AUTH and FILES microservices live on AWS Lambda (API Gateway). The CMS
# is still running locally during the greenfield phase, so its default
# stays on localhost.
DEFAULT_AUTH = 'https://32652ile50.execute-api.us-east-1.amazonaws.com/v1/auth'
DEFAULT_FILES = 'https://ek2xktuyr4.execute-api.us-east-1.amazonaws.com/v1/s3'
DEFAULT_CMS = 'http://localhost:3021/v1/cms'
DEFAULT_BUCKET = 'ml-data-file-handler'
DEFAULT_BASE_PATH = 'cms/'
DEFAULT_RATE_LIMIT_MS = 200
DEFAULT_MAX_UPLOAD_MB = 8  # API Gateway REST caps sync payloads at 10 MB.
SUMMARY_BODY_MAX = 480  # Pydantic NewsItem.summary is max 500.


# ---------- Top-level run state ----------

@dataclass
class Stats:
    created: int = 0
    skipped: int = 0
    failed: int = 0
    failures: List[str] = field(default_factory = list)

    def record_failure(self, source: str, item: WpItem, err: Exception) -> None:
        self.failed += 1
        self.failures.append(
            f'[{source}] id={item.id} "{item.title[:60]}" → {err}'
        )


# ---------- Wipe ----------

def wipe_tables(cms: CmsAdminClient, scope: List[str]) -> None:
    '''
        Deletes every item across the in-scope CMS tables. Required
        before re-seeding so the script stays idempotent.
    '''
    if 'news' in scope:
        items = cms.list_news()
        print(f'Wiping news ({len(items)} items)...')
        for item in items:
            cms.delete_news(item['id'])
    if 'documents' in scope:
        items = cms.list_documents()
        print(f'Wiping documents ({len(items)} items)...')
        for item in items:
            cms.delete_document(item['id'])
    if 'entities' in scope:
        items = cms.list_entities()
        print(f'Wiping entities ({len(items)} items)...')
        for item in items:
            cms.delete_entity(item['id'])


# ---------- News ----------

def seed_news(wp: WordPressClient, cms: CmsAdminClient, files: FilesClient,
              limit: Optional[int], dry_run: bool, stats: Stats) -> None:
    '''
        Walks every news-shaped CPT and creates one CMS news entry per
        item.
    '''
    for source in NEWS_SOURCES:
        rest_base = source['rest_base']
        cms_type = source['cms_type']
        sub_path = source['sub_path']
        print(f'\n=== News [{rest_base}] → type={cms_type}')
        for item in wp.list_items(rest_base, limit = limit):
            detail = wp.fetch_detail(item)
            try:
                payload = _build_news_payload(item, detail, cms_type)
                if detail and detail.image_url:
                    payload = _attach_image(files, payload, detail.image_url,
                                            sub_path, dry_run)
                _publish(cms.create_news, payload, dry_run, stats,
                         f'news/{rest_base}')
            except Exception as err:  # noqa: BLE001 (script must keep going)
                stats.record_failure(f'news/{rest_base}', item, err)


def _build_news_payload(item: WpItem, detail: Optional[DetailPayload],
                        cms_type: str) -> Dict:
    title = item.title or item.slug or f'#{item.id}'
    summary = ''
    body = ''
    if detail and detail.body_text:
        body = detail.body_text
        summary = body[:SUMMARY_BODY_MAX]
        if len(body) > SUMMARY_BODY_MAX:
            summary = summary.rstrip() + '…'
    payload: Dict = {
        'lang': 'es',
        'type': cms_type,
        'title': title[:255],
        'summary': summary or None,
        'body': body or None,
        'external_url': item.link or None,
        'published_at': item.date_iso,
        'is_published': True,
        'sort_order': 0,
    }
    return {k: v for k, v in payload.items() if v is not None}


def _attach_image(files: FilesClient, payload: Dict, image_url: str,
                  sub_path: str, dry_run: bool) -> Dict:
    if dry_run:
        # Honor --dry-run: don't write to S3. The news schema has no
        # external_url fallback for the image field, so the dry preview
        # simply omits it.
        return payload
    try:
        bucket, key = files.upload_from_url(image_url, sub_path = sub_path)
        payload['image_s3_bucket'] = bucket
        payload['image_s3_key'] = key
    except RuntimeError as err:
        # An asset that fails to upload is not worth dropping the whole
        # item; log and keep going with the source URL only.
        print(f'  ! image upload failed for {image_url}: {err}')
    return payload


# ---------- Documents ----------

def seed_documents(wp: WordPressClient, cms: CmsAdminClient,
                   files: FilesClient, limit: Optional[int], dry_run: bool,
                   stats: Stats) -> None:
    '''
        Walks every document-shaped CPT. PDFs are intentionally NOT
        uploaded: the user retrieves them through other channels, so we
        keep only the metadata plus a link back to the WP post for
        reference.
    '''
    del files  # signature kept for symmetry with the other seed_* helpers.
    for source in DOCUMENT_SOURCES:
        rest_base = source['rest_base']
        doc_type = source['doc_type']
        print(f'\n=== Documents [{rest_base}] → doc_type={doc_type}')
        for item in wp.list_items(rest_base, limit = limit):
            try:
                payload = _build_document_payload(item, doc_type)
                payload['file_external_url'] = item.link
                _publish(cms.create_document, payload, dry_run, stats,
                         f'documents/{rest_base}')
            except Exception as err:  # noqa: BLE001
                stats.record_failure(f'documents/{rest_base}', item, err)


def _build_document_payload(item: WpItem, doc_type: str) -> Dict:
    title = item.title or item.slug or f'#{item.id}'
    doc_date = (item.date_iso or '')[:10] or None
    payload: Dict = {
        'lang': 'es',
        'title': title[:255],
        'doc_type': doc_type[:50],
        'doc_date': doc_date,
        'is_published': True,
        'sort_order': 0,
    }
    return {k: v for k, v in payload.items() if v is not None}


# ---------- Entities ----------

def seed_entities(wp: WordPressClient, cms: CmsAdminClient,
                  files: FilesClient, limit: Optional[int], dry_run: bool,
                  stats: Stats) -> None:
    '''
        Single CPT (enlace_interes). The external URL is recovered from
        the body — if none can be found, the entity is skipped to avoid
        polluting the CMS with broken links.
    '''
    rest_base = ENTITY_SOURCE['rest_base']
    sub_path = ENTITY_SOURCE['sub_path']
    print(f'\n=== Entities [{rest_base}]')
    for item in wp.list_items(rest_base, limit = limit):
        detail = wp.fetch_detail(item)
        external_url = detail.external_url if detail else None
        try:
            if not external_url:
                raise RuntimeError('no external URL found in body')
            payload = {
                'name': (item.title or item.slug)[:100],
                'short_description': (detail.body_text[:200]
                                      if detail and detail.body_text
                                      else None),
                'url': external_url[:500],
                'is_active': True,
                'sort_order': 0,
            }
            payload = {k: v for k, v in payload.items() if v is not None}
            if detail and detail.image_url and not dry_run:
                try:
                    bucket, key = files.upload_from_url(
                        detail.image_url, sub_path = sub_path,
                    )
                    payload['logo_s3_bucket'] = bucket
                    payload['logo_s3_key'] = key
                except RuntimeError as err:
                    print(f'  ! logo upload failed for {detail.image_url}: {err}')
            _publish(cms.create_entity, payload, dry_run, stats,
                     f'entities/{rest_base}')
        except Exception as err:  # noqa: BLE001
            stats.record_failure(f'entities/{rest_base}', item, err)


# ---------- Publishing ----------

def _publish(create_fn, payload: Dict, dry_run: bool, stats: Stats,
             source_label: str) -> None:
    label = (payload.get('title') or payload.get('name') or '?')[:60]
    if dry_run:
        print(f'  [DRY] {source_label}: {label}')
        stats.skipped += 1
        return
    create_fn(payload)
    stats.created += 1
    print(f'  ✓ {source_label}: {label}')


# ---------- CLI ----------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description = 'Seed the CMS from the Ministry WordPress portal.')
    parser.add_argument('--source-url', default = DEFAULT_SOURCE_URL,
                        help = 'Base URL of the WP install (default: '
                               f'{DEFAULT_SOURCE_URL}).')
    parser.add_argument('--auth-url', default = DEFAULT_AUTH,
                        help = f'AUTH base URL (default: {DEFAULT_AUTH}).')
    parser.add_argument('--cms-url', default = DEFAULT_CMS,
                        help = f'CMS base URL (default: {DEFAULT_CMS}).')
    parser.add_argument('--files-url', default = DEFAULT_FILES,
                        help = f'FILES base URL (default: {DEFAULT_FILES}).')
    parser.add_argument('--bucket', default = DEFAULT_BUCKET,
                        help = f'Assets S3 bucket (default: {DEFAULT_BUCKET}).')
    parser.add_argument('--base-path', default = DEFAULT_BASE_PATH,
                        help = f'S3 base path (default: {DEFAULT_BASE_PATH}).')
    parser.add_argument('--rate-limit-ms', type = int,
                        default = DEFAULT_RATE_LIMIT_MS,
                        help = 'Milliseconds to sleep between detail fetches.')
    parser.add_argument('--only',
                        help = 'Comma-separated scope: news,documents,entities '
                               '(default: all).')
    parser.add_argument('--limit', type = int, default = None,
                        help = 'Cap items per CPT (smoke runs).')
    parser.add_argument('--wipe', action = 'store_true',
                        help = 'Delete every CMS item in scope before seeding.')
    parser.add_argument('--dry-run', action = 'store_true',
                        help = 'Skip CMS writes; just report what would happen.')
    return parser.parse_args()


def _scope(only_value: Optional[str]) -> List[str]:
    default = ['news', 'documents', 'entities']
    if not only_value:
        return default
    requested = [s.strip() for s in only_value.split(',') if s.strip()]
    invalid = [s for s in requested if s not in default]
    if invalid:
        raise SystemExit(f'Unknown --only value(s): {invalid}. '
                         f'Allowed: {default}.')
    return requested


def _load_credentials() -> tuple[str, str]:
    file_env = dotenv_values('.env') if Path('.env').exists() else {}
    email = (os.environ.get('SCRAPER_ADMIN_EMAIL')
             or file_env.get('SCRAPER_ADMIN_EMAIL')
             or input('Admin email: ').strip())
    password = (os.environ.get('SCRAPER_ADMIN_PASSWORD')
                or file_env.get('SCRAPER_ADMIN_PASSWORD')
                or getpass.getpass('Admin password: '))
    if not email or not password:
        raise SystemExit('Missing admin credentials.')
    return email, password


def main() -> int:
    args = parse_args()
    scope = _scope(args.only)
    print(f'Scope: {scope} | dry_run={args.dry_run} | wipe={args.wipe}')

    email, password = _load_credentials()
    auth = AuthClient(args.auth_url)
    token = auth.login(email, password)
    print(f'Logged in as {email}.')

    cms = CmsAdminClient(args.cms_url, token)
    files = FilesClient(args.files_url, token, args.bucket, args.base_path)
    wp = WordPressClient(args.source_url, rate_limit_ms = args.rate_limit_ms)

    if args.wipe and not args.dry_run:
        wipe_tables(cms, scope)

    stats = Stats()
    started = time.perf_counter()
    if 'news' in scope:
        seed_news(wp, cms, files, args.limit, args.dry_run, stats)
    if 'documents' in scope:
        seed_documents(wp, cms, files, args.limit, args.dry_run, stats)
    if 'entities' in scope:
        seed_entities(wp, cms, files, args.limit, args.dry_run, stats)

    elapsed = time.perf_counter() - started
    print('\n========== Summary ==========')
    print(f'Created : {stats.created}')
    print(f'Skipped : {stats.skipped}')
    print(f'Failed  : {stats.failed}')
    print(f'Elapsed : {elapsed:.1f}s')
    if stats.failures:
        print('\nFailures (first 20):')
        for line in stats.failures[:20]:
            print('  -', line)
    return 0 if stats.failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
