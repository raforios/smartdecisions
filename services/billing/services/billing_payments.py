'''
    How a sale was paid, and how the SIN calls that.

    A sale may combine up to three methods. The parts add up to the total, a
    method appears once, and the one that paid the most stands for the sale on
    the screens that show a single method. What each method brought in is
    counted here too, the same way for the till and for the dashboard.

    The SIN has no field per method: `codigoMetodoPago` is one code from its
    PAYMENT_METHODS catalogue, and every combination has its own entry —
    "EFECTIVO-TARJETA" is 10. The code is found in the synchronised catalogue
    by the names of its parts, so a combination the SIN adds is read rather
    than written here. The catalogue writes the same part several ways
    ("VALE" and "VALES", "GIFT-CARD" and "GIFT CARD", hyphens and dashes);
    the names are normalised before comparing.
'''
import re
from typing import Any, Final

from schemas.billing import (
    CARD_METHODS,
    SIN_PAYMENT_CODES,
    BillingError,
    MethodTotal,
    Payment,
    PaymentMethod,
    SaleNoteIn
)
from schemas.billing_siat import CatalogEntry
from services.billing import MONEY_DECIMALS, stored_payments
from services.exceptions import InvalidInputError
from services.logger_config import custom_logger as logger


# The separators the catalogue uses between the parts of a combination.
_PARTS: Final[re.Pattern] = re.compile(r'\s*[-–]\s*')

# The same part as the catalogue spells it in different entries.
_ALIASES: Final[dict[str, str]] = {
    'VALE': 'VALES', 'OTRO': 'OTROS', 'BILLETERA': 'BILLETERA MOVIL',
    'CANAL': 'CANAL DE PAGO', 'CANAL PAGO': 'CANAL DE PAGO', 'GIFT': 'GIFT CARD',
    'SWIFT': 'TRANSFERENCIA SWIFT', 'TRANSFERENCIA BANCARIA SWIFT': 'TRANSFERENCIA SWIFT'
}


def resolve_payments(
    note: SaleNoteIn,
    total: float
) -> list[Payment]:
    '''
        The parts a sale was paid with.

        Args:
            note (SaleNoteIn): The sale as it arrived.
            total (float): What the sale charges, already priced.

        Returns:
            list[Payment]: One per method; a single one for the whole total
                when the sale sent none.

        Raises:
            InvalidInputError: A method repeated, or parts that do not add up
                to the total.
    '''
    if not note.payments:
        return [Payment(method = note.payment_method, amount = total)]
    methods = [payment.method for payment in note.payments]
    if len(set(methods)) != len(methods):
        raise InvalidInputError(detail = BillingError.PAYMENT_REPEATED.value)
    paid = round(sum(payment.amount for payment in note.payments), MONEY_DECIMALS)
    if paid != round(total, MONEY_DECIMALS):
        error_msg = f'Payments add up to {paid} for a sale of {total}.'
        logger.warning(error_msg)
        raise InvalidInputError(detail = BillingError.PAYMENTS_DO_NOT_ADD_UP.value)
    return list(note.payments)


def primary_method(payments: list[Payment]) -> PaymentMethod:
    '''
        The method that paid the most, the first one on a tie.

        Args:
            payments (list[Payment]): The parts.

        Returns:
            PaymentMethod: The method.
    '''
    return max(payments, key = lambda payment: payment.amount).method


def paid_by_card(methods: list[PaymentMethod]) -> bool:
    '''
        Whether any part was paid by card — the only case a card number may
        travel.

        Args:
            methods (list[PaymentMethod]): The methods used.

        Returns:
            bool: True with a card among them.
    '''
    return any(method in CARD_METHODS for method in methods)


def sin_payment_code(
    catalogue: list[CatalogEntry],
    methods: list[PaymentMethod]
) -> int:
    '''
        The SIN's `codigoMetodoPago` of a payment, single or combined.

        Args:
            catalogue (list[CatalogEntry]): The PAYMENT_METHODS catalogue.
            methods (list[PaymentMethod]): The methods used.

        Returns:
            int: The code.

        Raises:
            InvalidInputError: PAYMENT_COMBINATION_UNKNOWN, the SIN has no
                entry for that combination.
    '''
    by_code = {entry.code: _parts(entry.description) for entry in catalogue}
    wanted = frozenset(part for method in methods
                       for part in by_code.get(str(SIN_PAYMENT_CODES[method]), ()))
    for code, parts in by_code.items():
        if parts == wanted:
            return int(code)
    error_msg = f'The SIN has no payment code for {sorted(wanted)}.'
    logger.warning(error_msg)
    raise InvalidInputError(detail = BillingError.PAYMENT_COMBINATION_UNKNOWN.value)


def _parts(description: str) -> frozenset[str]:
    '''
        The parts of a catalogue entry, normalised.

        Args:
            description (str): As the SIN writes it.

        Returns:
            frozenset[str]: The part names.
    '''
    # "GIFT-CARD" is one part written with a hyphen, not two.
    text = ' '.join(description.upper().replace('GIFT-CARD', 'GIFT CARD').split())
    return frozenset(_ALIASES.get(part, part) for part in _PARTS.split(text) if part)


def method_totals(sales: list[Any]) -> list[MethodTotal]:
    '''
        What each payment method brought in. Works on stored items and on
        `SaleNoteOut`, so the till and the daily report count the same way.

        Args:
            sales (list[Any]): Issued sales.

        Returns:
            list[MethodTotal]: One row per method used, in the enum's order;
                `count` is how many sales used it.
    '''
    totals: dict[str, list[float]] = {}
    for sale in sales:
        for method, amount in _paid_parts(sale):
            totals.setdefault(method, []).append(amount)
    return [MethodTotal(payment_method = method, count = len(totals[method.value]),
                        total = round(sum(totals[method.value]), MONEY_DECIMALS))
            for method in PaymentMethod if method.value in totals]


def _paid_parts(sale: Any) -> list[tuple[str, float]]:
    '''
        What each method paid of one sale. A combined payment counts in every
        method it used, each with its own amount; a note issued before
        payments were combined paid its total one way.

        Args:
            sale (Any): A stored item or a `SaleNoteOut`.

        Returns:
            list[tuple[str, float]]: (method, amount) pairs.
    '''
    if isinstance(sale, dict):
        return [(part['method'], part['amount']) for part in stored_payments(sale)]
    return [(part.method.value, part.amount) for part in sale.payments] or \
        [(sale.payment_method.value, sale.total)]
