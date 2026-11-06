'''
    A load that replaces a stored file removes the previous one through FILES,
    and a failure to remove it never undoes the load.
'''
from controllers import common
from services.exceptions import ServiceUnavailableError


def test_the_replaced_file_is_removed_through_files(monkeypatch):
    '''The key the dataset held goes; a dataset with none removes nothing.'''
    removed: list = []
    monkeypatch.setattr(common, 'delete_stored_file',
                        lambda key, token: removed.append((key, token)))
    common.retire_replaced_file('commercial/normalized/old.csv', 'Bearer t')
    common.retire_replaced_file(None, 'Bearer t')
    assert removed == [('commercial/normalized/old.csv', 'Bearer t')]


def test_a_failed_removal_is_logged_and_never_raises(monkeypatch):
    '''The new file is in place: raising would make the queue append the load twice.'''
    def _refuse(
        _key,
        _token
    ):
        raise ServiceUnavailableError(detail = 'FILES_UNAVAILABLE')
    monkeypatch.setattr(common, 'delete_stored_file', _refuse)
    common.retire_replaced_file('commercial/normalized/old.csv', 'Bearer t')
