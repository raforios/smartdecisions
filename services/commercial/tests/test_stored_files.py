'''
    Stored files reach COMMERCIAL as files: FILES signs a short-lived URL and
    the bytes come from the bucket, so a dataset larger than the 6 MB a Lambda
    can answer as rows still loads.
'''
from typing import Any

import pandas as pd
import pytest

from services import commercial_utils, utils
from services.exceptions import ServiceUnavailableError


class _Response:  # pylint: disable=too-few-public-methods
    '''
        A requests response, as much of it as the block reads.
    '''
    def __init__(
        self,
        status: int,
        payload: Any = None,
        content: bytes = b''
    ) -> None:
        '''
            Args:
                status (int): HTTP status.
                payload (Any): JSON body.
                content (bytes): Raw body.
        '''
        self.status_code, self.ok = status, status < 400
        self._payload, self.content, self.text = payload, content, ''

    def json(self) -> Any:
        '''The JSON body.'''
        return self._payload

    def raise_for_status(self) -> None:
        '''Fails as requests does on an error status.'''
        if not self.ok:
            raise utils.req.exceptions.HTTPError(f'{self.status_code}')


def test_a_stored_file_comes_through_the_url_files_signs(monkeypatch: pytest.MonkeyPatch):
    '''
        The block asks FILES for the URL, fetches the object from it, and the
        frame is read here; nothing travels as rows.
    '''
    asked: list[str] = []

    def _get(
        url: str,
        **_kwargs: Any
    ) -> _Response:
        asked.append(url)
        if '/v1/s3/download-url/' in url:
            return _Response(200, {'url': 'https://bucket/signed', 'file_key': 'k',
                                   'expires_in': 300})
        return _Response(200, content = b'order_id,total_amount\nF-1,10\nF-2,5\n')

    monkeypatch.setattr(utils, 'API_URL', 'https://api.test')
    monkeypatch.setattr(utils, 'BUCKET_NAME', 'bucket')
    monkeypatch.setattr(utils.req, 'get', _get)

    frame = commercial_utils.read_stored_frame('commercial/normalized/ventas.csv', 'Bearer t')

    assert list(frame['order_id']) == ['F-1', 'F-2']
    assert isinstance(frame, pd.DataFrame)
    assert asked == ['https://api.test/v1/s3/download-url/bucket/commercial/normalized/ventas.csv',
                     'https://bucket/signed']


def test_a_bucket_that_does_not_answer_is_unavailable(monkeypatch: pytest.MonkeyPatch):
    '''A signed URL that fails to deliver is FILES_SERVICE_UNREACHABLE, never a crash.'''
    def _get(
        url: str,
        **_kwargs: Any
    ) -> _Response:
        if '/v1/s3/download-url/' in url:
            return _Response(200, {'url': 'https://bucket/signed'})
        return _Response(403)

    monkeypatch.setattr(utils, 'API_URL', 'https://api.test')
    monkeypatch.setattr(utils, 'BUCKET_NAME', 'bucket')
    monkeypatch.setattr(utils.req, 'get', _get)

    with pytest.raises(ServiceUnavailableError) as raised:
        utils.download_file_bytes('k.csv', 'Bearer t')
    assert raised.value.detail == 'FILES_SERVICE_UNREACHABLE'


def test_a_stored_frame_goes_up_through_the_url_files_signs(monkeypatch: pytest.MonkeyPatch):
    '''
        The block asks FILES where to put the file and sends the bytes to the
        bucket with the MIME type FILES signs for the extension: a dataset
        larger than the 6 MB a Lambda takes in still gets stored.
    '''
    calls: list[tuple[str, Any]] = []

    def _post(
        url: str,
        **kwargs: Any
    ) -> _Response:
        calls.append(('post', url, kwargs['json']))
        return _Response(200, {'presigned_url': 'https://bucket/put', 'file_key': kwargs['json']
                               ['file_path'] + '/' + kwargs['json']['file_name']})

    def _put(
        url: str,
        **kwargs: Any
    ) -> _Response:
        calls.append(('put', url, kwargs['headers']['Content-Type'], len(kwargs['data'])))
        return _Response(200)

    monkeypatch.setattr(utils, 'API_URL', 'https://api.test')
    monkeypatch.setattr(utils, 'BUCKET_NAME', 'bucket')
    monkeypatch.setattr(utils.req, 'post', _post)
    monkeypatch.setattr(utils.req, 'put', _put)

    stored = utils.store_file('commercial/normalized/x.csv', b'a,b\n1,2\n', 'Bearer t')

    assert stored == 'commercial/normalized/x.csv'
    assert calls == [
        ('post', 'https://api.test/v1/s3/upload-presigned',
         {'bucket_name': 'bucket', 'file_path': 'commercial/normalized', 'file_name': 'x.csv'}),
        ('put', 'https://bucket/put', 'text/csv', 8)
    ]
