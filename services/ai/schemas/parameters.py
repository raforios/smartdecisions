'''
    Error codes of the conversation with PARAMETERS.

    They travel as the error `detail`, so the caller reads a stable code. A
    missing parameter stops the request instead of running on a value nobody
    chose: there is no default in the code.
'''
from enum import Enum


class ParametersError(str, Enum):
    '''
        Why the business values could not be read.
    '''
    NOT_CONFIGURED = 'PARAMETERS_SERVICE_NOT_CONFIGURED'
    UNREACHABLE = 'PARAMETERS_SERVICE_UNREACHABLE'
    REJECTED = 'PARAMETERS_SERVICE_REJECTED'
    MISSING = 'PARAMETER_MISSING'
