'''
    Reverting the cancellation of an invoice or of a Nota de Crédito-Débito.

    The SIN lets a cancelled fiscal document become valid again, once, until
    the ninth of the month after it was issued, and a document reverted can
    never be cancelled again; the buyer must be told (siatinfo, «Reversión de
    anulación»; `docs/siat/SIAT.md`). Reverted, everything the cancellation
    undid is done again: the units leave the shelf for a sale, come back for a
    return, and the till counts the money again.
'''
from enum import Enum


class ReversalError(str, Enum):
    '''
        Why a reversal was refused, or why a reverted document cannot be
        cancelled.
    '''
    DOCUMENT_NOT_CANCELLED = 'DOCUMENT_NOT_CANCELLED'
    NOT_CANCELLED_AT_SIN = 'NOT_CANCELLED_AT_SIN'
    ALREADY_REVERTED = 'ALREADY_REVERTED'
    REVERSAL_DEADLINE_PASSED = 'REVERSAL_DEADLINE_PASSED'
    CANCELLATION_REVERTED = 'CANCELLATION_REVERTED'
