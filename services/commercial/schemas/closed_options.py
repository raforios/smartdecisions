'''
    The codes of the closed-option columns of the contracts, and the Spanish
    word the template shows for each: the codes are English, the template is
    Spanish (CLAUDE.md §1), and `TEMPLATE_WORDS` is the mapper between them.
'''
from enum import Enum

from schemas.localization import VisitOutcome


class PaymentTerms(str, Enum):
    '''
        How a sale is paid: at once, or on credit.
    '''
    CASH = 'CASH'
    CREDIT = 'CREDIT'


class PaymentMethod(str, Enum):
    '''
        The means of payment a sale accepts: the ones SmartBilling's till
        records, cards as one.
    '''
    CASH = 'CASH'
    QR = 'QR'
    CARD = 'CARD'
    BANK_TRANSFER = 'BANK_TRANSFER'
    MOBILE_WALLET = 'MOBILE_WALLET'


class PurchaseCurrency(str, Enum):
    '''
        The currencies a purchase is paid in; the analysis brings each to
        bolivianos at the rate of the purchase day.
    '''
    BOB = 'BOB'
    USD = 'USD'
    USDT = 'USDT'


# How the client writes each code in the template: the codes are English, the
# template is Spanish (CLAUDE.md §1), and this is the mapper between them. A
# code without a word here is written as it is (the currencies). One map per
# enum: a `str` Enum equals its value, so PaymentTerms.CASH and
# PaymentMethod.CASH would be the same key of one map.
TEMPLATE_WORDS: dict[type[Enum], dict[Enum, str]] = {
    PaymentTerms: {PaymentTerms.CASH: 'Contado', PaymentTerms.CREDIT: 'Crédito'},
    PaymentMethod: {
        PaymentMethod.CASH: 'Efectivo',
        PaymentMethod.QR: 'QR',
        PaymentMethod.CARD: 'Tarjeta',
        PaymentMethod.BANK_TRANSFER: 'Transferencia',
        PaymentMethod.MOBILE_WALLET: 'Billetera móvil',
    },
    VisitOutcome: {
        VisitOutcome.SALE: 'Venta',
        VisitOutcome.NO_SALE: 'Sin venta',
        VisitOutcome.CLOSED: 'Cerrado',
        VisitOutcome.NOT_FOUND: 'No encontrado',
    },
}
