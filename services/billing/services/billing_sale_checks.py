'''
    The checks a sale passes before any stock moves: who the buyer is, the
    card number it may carry, and lines that are not repeated.
'''
from schemas.billing import BillingError, PaymentMethod, SaleLineIn, SaleNoteIn, SettingsResponse
from services.billing_payments import paid_by_card
from services.billing_siat import mask_card
from services.exceptions import InvalidInputError

# The CI and the NIT in the SIN's catalogue of identity documents: the two the
# norm asks to be numeric.
NUMERIC_DOCUMENT_TYPES = (1, 5)


def require_buyer(
    note: SaleNoteIn,
    settings: SettingsResponse
) -> None:
    """
        Refuses a sale with no buyer document where the pharmacy needs one.

        Phase II of the Bolivian norm requires every invoice to be nominative
        whatever the amount, and it is explicit about what that means: the
        DOCUMENT NUMBER, not the name or business name (`docs/siat/SIAT.md`).
        So the document is demanded and the name is not — asking for both
        would refuse a sale the norm accepts, over a field the buyer is not
        obliged to give.

        It is a setting and not a constant because a pharmacy still issuing
        internal notes has to keep working until it is authorised. Invoicing
        demands it too, and also the document type: the XSD has no empty
        `codigoTipoDocumentoIdentidad`.

        Args:
            note (SaleNoteIn): What is being sold, with its buyer.
            settings (SettingsResponse): Whether this pharmacy must name the
                buyer, and whether it invoices.

        Raises:
            InvalidInputError: BUYER_REQUIRED when the document is missing.
    """
    if not (settings.buyer_required or settings.invoicing_enabled):
        return
    if not (note.buyer and (note.buyer.document or '').strip()):
        raise InvalidInputError(detail = BillingError.BUYER_REQUIRED.value)
    if settings.invoicing_enabled and note.buyer.document_type is None:
        raise InvalidInputError(detail = BillingError.BUYER_REQUIRED.value)
    # The norm: a CI or a NIT the SIN receives has to be a number.
    if settings.invoicing_enabled and note.buyer.document_type in NUMERIC_DOCUMENT_TYPES \
            and not note.buyer.document.strip().isdigit():
        raise InvalidInputError(detail = BillingError.BUYER_DOCUMENT_NOT_NUMERIC.value)


def masked_card(
    note: SaleNoteIn,
    methods: list[PaymentMethod]
) -> str | None:
    """
        The card number as it may be stored: masked, or nothing at all.

        Two rules of the norm, both in `docs/siat/SIAT.md`. A card number may
        only travel when the payment method IS a card — sending one with a
        cash sale is an error the tax office reports. And when it does travel
        it goes with the middle digits zeroed, first and last four in clear.

        Masking here, at the boundary, is deliberate: the full number never
        reaches the table, the log or the printed note, so there is no copy of
        it to leak later.

        Args:
            note (SaleNoteIn): The sale as it arrived.
            methods (list[PaymentMethod]): The methods it was paid with.

        Returns:
            str | None: The masked number, or None when there is none.

        Raises:
            InvalidInputError: A card number without a card payment, or a
                number too short to be one.
    """
    raw = (note.card_number or '').strip()
    is_card = paid_by_card(methods)
    if not raw:
        return None
    if not is_card:
        raise InvalidInputError(detail = BillingError.CARD_WITHOUT_CARD_PAYMENT.value)
    try:
        return mask_card(raw)
    except ValueError as error:
        raise InvalidInputError(
            detail = BillingError.INVALID_CARD_NUMBER.value
        ) from error


def reject_repeated_lines(lines: list[SaleLineIn]) -> None:
    '''
        A SKU twice in one note is a mistake at the till, not two sales: the
        second line would be priced against the batches the first already took.

        Args:
            lines (list[SaleLineIn]): Lines as sent.

        Raises:
            InvalidInputError: The same SKU appears more than once.
    '''
    seen = {line.sku for line in lines}
    if len(seen) != len(lines):
        raise InvalidInputError(detail = BillingError.DUPLICATE_LINE.value)
