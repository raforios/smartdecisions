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

from schemas.files import S3FileRequest
from services import files
from services.exceptions import (
    ForbiddenError,
    InvalidInputError,
    ResourceNotFoundError,
    ServiceUnavailableError
)
from services.utils import handle_aws_client_error


@pytest.fixture(autouse = True)
def _buckets(monkeypatch: pytest.MonkeyPatch) -> None:
    '''
        The buckets these tests name, allowed whatever the .env says.

        Args:
            monkeypatch (pytest.MonkeyPatch): Replaces the allowed buckets.
    '''
    monkeypatch.setattr(files, 'ALLOWED_BUCKETS', frozenset({'bucket', 'b',
                                                             'ml-data-file-handler'}))


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
            dict[str, Any]: What the response carries: the route sends only the
                field of the file's kind.
    '''
    monkeypatch.setattr(files, 's3_client', _FakeS3(content))
    return asyncio.run(files.read_file('bucket', file_key, 'acme')).model_dump(exclude_none = True)


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
    result = asyncio.run(files.read_file('bucket', 'carga.csv', 'acme', ';'))
    assert result.data == [{'codigo': 'A', 'monto': 1}]


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
        asyncio.run(files.read_file('bucket', 'carga.csv', 'acme'))


class _MissingS3:  # pylint: disable=too-few-public-methods
    '''
        Stands in for an S3 client whose key does not exist.
    '''
    def get_object(
        self,
        **_: Any
    ) -> dict[str, Any]:
        '''
            Fails as S3 does for a missing key.
        '''
        raise _client_error('NoSuchKey')


def test_missing_file_answers_a_code_and_logs_bucket_and_key(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture
) -> None:
    '''
        The caller receives FILE_NOT_FOUND; the log says which file was
        missing, not "Bucket None or file None" (Rafael, 19-oct-2026).
    '''
    monkeypatch.setattr(files, 's3_client', _MissingS3())
    with pytest.raises(ResourceNotFoundError) as raised:
        asyncio.run(files.read_file('ml-data-file-handler', 'carga.csv', 'acme'))
    assert raised.value.detail == 'FILE_NOT_FOUND'
    assert 'ml-data-file-handler' in caplog.text and 'carga.csv' in caplog.text


class _RecordingS3:  # pylint: disable=too-few-public-methods
    '''
        Stands in for S3 on the writing side: records what it is asked.
    '''
    def __init__(self) -> None:
        '''Starts with nothing asked.'''
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def put_object(
        self,
        **kwargs: Any
    ) -> None:
        '''Records a put.'''
        self.calls.append(('put', kwargs))

    def delete_object(
        self,
        **kwargs: Any
    ) -> None:
        '''Records a delete.'''
        self.calls.append(('delete', kwargs))

    def generate_presigned_url(
        self,
        **kwargs: Any
    ) -> str:
        '''Records a signature and answers a URL.'''
        self.calls.append(('sign', kwargs))
        return 'https://signed'

    def get_paginator(
        self,
        _name: str
    ) -> Any:
        '''A paginator over two keys, one of them a folder.'''
        class _Pages:  # pylint: disable=too-few-public-methods
            '''One page of a listing.'''
            def paginate(
                self,
                **_kwargs: Any
            ) -> list[dict[str, Any]]:
                '''The page.'''
                return [{'Contents': [{'Key': 'raw/'}, {'Key': 'raw/a.csv'}]}]
        return _Pages()


def test_the_writing_side_answers_codes_and_refuses_what_it_does_not_take(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    '''
        Store, delete, list and sign answer their DTOs with codes; a MIME type
        or an extension outside the allowed list is refused before S3 is asked.
    '''
    # pylint: disable=import-outside-toplevel
    from schemas.files import FileUploadData, PresignedUrlRequest

    s3 = _RecordingS3()
    monkeypatch.setattr(files, 's3_client', s3)
    upload = FileUploadData(bucket_name = 'b', file_path = 'raw', file_name = 'a.csv',
                            file_content = b'x', content_type = 'text/csv')

    stored = asyncio.run(files.store_file(upload, 'acme'))
    deleted = asyncio.run(files.delete_file('b', 'raw/a.csv', 'acme'))
    listed = asyncio.run(files.list_files('b', 'raw/', 'acme'))
    signed = asyncio.run(files.presigned_upload_url(PresignedUrlRequest(
        bucket_name = 'b', file_path = 'raw', file_name = 'a.csv'), 'acme'))

    assert (stored.message, stored.file_key) == ('UPLOADED', 'raw/a.csv')
    assert deleted.message == 'DELETED'
    assert listed == ['raw/a.csv']
    assert signed.presigned_url == 'https://signed'
    assert s3.calls[-1][1]['Params']['ContentType'] == 'text/csv'
    with pytest.raises(InvalidInputError) as raised:
        asyncio.run(files.store_file(upload.model_copy(update = {'content_type': 'app/x'}),
                                     'acme'))
    assert raised.value.detail == 'UNSUPPORTED_FORMAT'
    with pytest.raises(InvalidInputError):
        asyncio.run(files.presigned_upload_url(PresignedUrlRequest(
            bucket_name = 'b', file_name = 'run.exe'), 'acme'))
    # put, delete and sign: the two refusals never reached S3.
    assert [kind for kind, _ in s3.calls] == ['put', 'delete', 'sign']


def test_files_works_only_on_its_buckets_and_decides_the_type(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    '''
        A bucket outside ALLOWED_BUCKETS is refused before S3 is asked, for
        every operation; a presigned URL signs the MIME type of its extension,
        whatever an old client still sends; an upload checks the extension
        and not only the type it claims.
    '''
    # pylint: disable=import-outside-toplevel
    from schemas.files import FileUploadData, PresignedUrlRequest

    s3 = _RecordingS3()
    monkeypatch.setattr(files, 's3_client', s3)
    for call in (files.read_file('other-bucket', 'a.csv', 'acme'),
                 files.delete_file('other-bucket', 'a.csv', 'acme'),
                 files.list_files('other-bucket', '', 'acme'),
                 files.presigned_upload_url(PresignedUrlRequest(
                     bucket_name = 'other-bucket', file_name = 'a.csv'), 'acme')):
        with pytest.raises(ForbiddenError) as raised:
            asyncio.run(call)
        assert raised.value.detail == 'BUCKET_NOT_ALLOWED'

    asyncio.run(files.presigned_upload_url(PresignedUrlRequest.model_validate(
        {'bucket_name': 'b', 'file_name': 'book.xlsx', 'validation': False,
         'content_type': 'text/html'}), 'acme'))
    assert s3.calls[-1][1]['Params']['ContentType'] == (
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    with pytest.raises(InvalidInputError):
        asyncio.run(files.store_file(FileUploadData(
            bucket_name = 'b', file_name = 'page.html', file_content = b'<html>',
            content_type = 'text/csv'), 'acme'))
    assert [kind for kind, _ in s3.calls] == ['sign']


def test_a_large_file_reaches_its_caller_through_a_short_lived_url(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    '''
        FILES signs a GET of the object instead of returning its rows, so the
        size of the file has no ceiling; the bucket and the extension are
        checked as for every other operation.
    '''
    s3 = _RecordingS3()
    monkeypatch.setattr(files, 's3_client', s3)

    signed = asyncio.run(files.download_url('b', 'commercial/normalized/ventas.csv', 'acme'))

    assert signed.url == 'https://signed' and signed.file_key == 'commercial/normalized/ventas.csv'
    assert s3.calls[-1][1]['ClientMethod'] == 'get_object'
    assert signed.expires_in == files.ENV_VARS['DOWNLOAD_URL_SECONDS']
    with pytest.raises(ForbiddenError):
        asyncio.run(files.download_url('other-bucket', 'a.csv', 'acme'))
    with pytest.raises(InvalidInputError):
        asyncio.run(files.download_url('b', 'run.exe', 'acme'))
