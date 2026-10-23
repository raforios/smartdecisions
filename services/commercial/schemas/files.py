'''
    Error codes of the conversation with FILES.

    They travel as the error `detail`, so the caller reads a stable code and
    renders its own wording. They live here and not next to the helper that
    raises them because a code is contract, and `CLAUDE.md` §3 puts contracts
    in `schemas/`.
'''
from enum import Enum


class FilesError(str, Enum):
    '''
        Why a conversation with FILES could not happen.
    '''
    NOT_CONFIGURED = 'FILES_SERVICE_NOT_CONFIGURED'
    UNREACHABLE = 'FILES_SERVICE_UNREACHABLE'
    REJECTED = 'FILES_SERVICE_REJECTED'
