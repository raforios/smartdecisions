'''
    FILES microservice client.

    Downloads remote binaries (PDFs, images) from the source portal and
    re-uploads them via POST /v1/s3/upload so the CMS only references
    assets that live in our own bucket.
'''
from typing import Optional, Tuple
import mimetypes
import os
from urllib.parse import urlparse, unquote

import requests


class FilesClient:
    '''
        Wraps the FILES upload endpoint with a download-then-upload helper.

        The API Gateway in front of the FILES Lambda enforces a 10 MB
        payload limit, so a HEAD precheck is run first: when the remote
        size is known and exceeds `max_size_bytes`, the upload is skipped
        with a clear "too large" error so the caller can fall back to a
        plain external URL without wasting a download round-trip.
    '''

    def __init__(self, base_url: str, token: str, bucket: str,
                 base_path: str = 'cms/', timeout: int = 60,
                 max_size_bytes: int = 8 * 1024 * 1024,
                 download_user_agent: str = 'Mozilla/5.0 Chrome/130'):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.bucket = bucket
        self.base_path = _normalize_path(base_path)
        self.timeout = timeout
        self.max_size_bytes = max_size_bytes
        self.download_ua = download_user_agent

    def upload_from_url(self, source_url: str, sub_path: str = '',
                        ) -> Optional[Tuple[str, str]]:
        '''
            Downloads `source_url`, uploads to S3 under
            `${base_path}${sub_path}/`, returns `(bucket, key)` or raises
            RuntimeError on download / upload / size-check failure.
        '''
        size = self._check_size(source_url)
        if size is not None and size > self.max_size_bytes:
            actual_mb = size / 1024 / 1024
            limit_mb = self.max_size_bytes / 1024 / 1024
            raise RuntimeError(
                f'size {actual_mb:.1f}MB exceeds upload limit '
                f'{limit_mb:.1f}MB (skipped to avoid API Gateway 413)')

        try:
            file_bytes, content_type, file_name = self._download(source_url)
        except RuntimeError as err:
            raise RuntimeError(
                f'Download failed for {source_url}: {err}') from err

        return self._upload(file_bytes, file_name, content_type, sub_path)

    # ---------- helpers ----------
    def _check_size(self, source_url: str) -> Optional[int]:
        '''
            Returns the Content-Length advertised by HEAD, or None when
            the server does not expose it (in which case we fall through
            to the regular download and the upload may still 413).
        '''
        try:
            response = requests.head(
                source_url, allow_redirects = True,
                timeout = self.timeout,
                headers = {'User-Agent': self.download_ua},
            )
        except requests.RequestException:
            return None
        if not response.ok:
            return None
        raw = response.headers.get('Content-Length')
        if not raw:
            return None
        try:
            return int(raw)
        except ValueError:
            return None

    def _download(self, source_url: str) -> Tuple[bytes, str, str]:
        response = requests.get(
            source_url, timeout = self.timeout,
            headers = {'User-Agent': self.download_ua}, stream = True,
        )
        if not response.ok:
            raise RuntimeError(f'HTTP {response.status_code}')
        body = response.content
        content_type = (response.headers.get('Content-Type', '')
                        .split(';', 1)[0].strip())
        if not content_type:
            content_type = mimetypes.guess_type(source_url)[0] \
                or 'application/octet-stream'
        file_name = _derive_filename(source_url, content_type)
        return body, content_type, file_name

    def _upload(self, file_bytes: bytes, file_name: str, content_type: str,
                sub_path: str) -> Tuple[str, str]:
        full_path = _normalize_path(f'{self.base_path}{sub_path}')
        files = {'file': (file_name, file_bytes, content_type)}
        data = {'bucket_name': self.bucket, 'file_path': full_path}
        headers = {'Authorization': f'Bearer {self.token}'}
        response = requests.post(
            f'{self.base_url}/upload',
            headers = headers, files = files, data = data,
            timeout = self.timeout,
        )
        if not response.ok:
            raise RuntimeError(
                f'FILES upload {response.status_code}: {response.text[:200]}')
        payload = response.json()
        return self.bucket, payload['file_key']


def _normalize_path(path: str) -> str:
    cleaned = path.strip('/')
    return cleaned + '/' if cleaned else ''


def _derive_filename(source_url: str, content_type: str) -> str:
    parsed = urlparse(source_url)
    name = unquote(os.path.basename(parsed.path)) or 'asset'
    if '.' in name:
        return name
    ext = mimetypes.guess_extension(content_type) or ''
    return f'{name}{ext}'
