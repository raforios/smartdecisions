'''
    The read route takes the whole object key, folders included.

    `/read/{bucket}/{file_key}` did not match a key with a slash, so a file kept
    in a folder (`ingest/normalized/<id>.csv`) answered 404 before reaching the
    reader (23-oct-2026, the first read of COMMERCIAL through FILES).
'''
from starlette.routing import Match

from routes.files import router


def test_a_key_with_folders_reaches_the_reader() -> None:
    '''The nested key is matched whole and handed over as one parameter.'''
    scope = {'type': 'http', 'method': 'GET',
             'path': '/v1/s3/read/ml-data-file-handler/ingest/normalized/abc.csv'}
    route = next(route for route in router.routes
                 if getattr(route, 'name', '') == 'read_s3_file_route')
    match, child = route.matches(scope)
    assert match is Match.FULL
    assert child['path_params']['file_key'] == 'ingest/normalized/abc.csv'
