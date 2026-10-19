'''
    services/files/tests/test_files.py

    Pure tests: S3 is replaced by a stand-in, and nothing imported reads the
    configuration, because the CI of GitHub Actions runs them with no .env.
'''
import asyncio
import base64
from io import BytesIO
from typing import Any

import pytest
from botocore.exceptions import ClientError

from controllers import files
from schemas.files import S3FileRequest
from services.exceptions import (
    ForbiddenError,
    InvalidInputError,
    ResourceNotFoundError,
    ServiceUnavailableError
)
from services.utils import handle_aws_client_error


class _FakeS3:  # pylint: disable=too-few-public-methods
    '''
        Stands in for the S3 client: every key holds the same bytes.
    '''
    def __init__(
        self,
        content: bytes
    ) -> None:
        self.content = content

    def get_object(
        self,
        **_: Any
    ) -> dict[str, Any]:
        '''
            Returns the stored bytes as S3 returns an object.
        '''
        return {'Body': BytesIO(self.content)}


def _read(
    monkeypatch: pytest.MonkeyPatch,
    file_key: str,
    content: bytes
) -> dict[str, Any]:
    '''
        Reads `file_key` through the controller with S3 holding `content`.

        Args:
            monkeypatch (pytest.MonkeyPatch): Replaces the S3 client.
            file_key (str): The key to read; its extension picks the reader.
            content (bytes): What the object holds.

        Returns:
            dict[str, Any]: What the controller returns.
    '''
    monkeypatch.setattr(files, 's3_client', _FakeS3(content))
    return asyncio.run(files.read_data_from_s3('bucket', file_key, 'acme'))


def _client_error(code: str) -> ClientError:
    '''
        A boto3 ClientError carrying `code`.

        Args:
            code (str): The AWS error code.

        Returns:
            ClientError: The error.
    '''
    return ClientError({'Error': {'Code': code, 'Message': code}}, 'GetObject')


def test_csv_comes_back_as_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    '''A CSV is read into one dictionary per row.'''
    result = _read(monkeypatch, 'carga.csv', b'cuenta,monto\n1.1.01,100\n4.1.01,250\n')
    assert result == {'filename': 'carga.csv',
                      'data': [{'cuenta': '1.1.01', 'monto': 100},
                               {'cuenta': '4.1.01', 'monto': 250}]}


def test_csv_honours_the_delimiter(monkeypatch: pytest.MonkeyPatch) -> None:
    '''A file separated by semicolons is read with the delimiter the caller gives.'''
    monkeypatch.setattr(files, 's3_client', _FakeS3(b'codigo;monto\nA;1\n'))
    result = asyncio.run(files.read_data_from_s3('bucket', 'carga.csv', 'acme', ';'))
    assert result['data'] == [{'codigo': 'A', 'monto': 1}]


def test_text_comes_back_whole(monkeypatch: pytest.MonkeyPatch) -> None:
    '''A text file is returned as it is.'''
    assert _read(monkeypatch, 'nota.txt', 'línea'.encode())['content'] == 'línea'


def test_binary_comes_back_in_base64(monkeypatch: pytest.MonkeyPatch) -> None:
    '''A PDF or an image travels as base64.'''
    result = _read(monkeypatch, 'factura.pdf', b'%PDF-1.7')
    assert base64.b64decode(result['content_base64']) == b'%PDF-1.7'


def test_empty_csv_is_invalid_input(monkeypatch: pytest.MonkeyPatch) -> None:
    '''An empty CSV is the caller's mistake, not a server failure.'''
    with pytest.raises(InvalidInputError):
        _read(monkeypatch, 'vacio.csv', b'')


def test_unknown_extension_is_invalid_input(monkeypatch: pytest.MonkeyPatch) -> None:
    '''Only the listed formats are read.'''
    with pytest.raises(InvalidInputError):
        _read(monkeypatch, 'programa.exe', b'MZ')


@pytest.mark.parametrize('code, expected', [
    ('NoSuchKey', ResourceNotFoundError),
    ('NoSuchBucket', ResourceNotFoundError),
    ('AccessDenied', ForbiddenError),
    ('SlowDown', ServiceUnavailableError)
])
def test_aws_errors_become_http_errors(
    code: str,
    expected: type
) -> None:
    '''Each S3 failure answers with the HTTP error that describes it.'''
    with pytest.raises(expected):
        handle_aws_client_error(_client_error(code), {'bucket_name': 'b', 'file_key': 'k'})


def test_file_key_joins_path_and_name() -> None:
    '''With no path the file sits at the root of the bucket.'''
    assert S3FileRequest(bucket_name = 'b', file_name = 'a.csv').file_key == 'a.csv'
    assert S3FileRequest(bucket_name = 'b', file_path = 'ingest/raw',
                         file_name = 'a.csv').file_key == 'ingest/raw/a.csv'


class _BrokenS3:  # pylint: disable=too-few-public-methods
    '''
        Stands in for an S3 client that fails in a way nobody foresaw.
    '''
    def get_object(
        self,
        **_: Any
    ) -> dict[str, Any]:
        '''
            Fails like an unexpected library error.
        '''
        raise RuntimeError('connection reset')


def test_unexpected_failure_is_still_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    '''Only the caller's mistakes are 400: anything unforeseen stays a 503.'''
    monkeypatch.setattr(files, 's3_client', _BrokenS3())
    with pytest.raises(ServiceUnavailableError):
        asyncio.run(files.read_data_from_s3('bucket', 'carga.csv', 'acme'))
