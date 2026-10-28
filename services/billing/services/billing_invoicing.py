'''
    Turning a sale into an invoice the SIN receives.

    Two halves, because stock sits between them. `prepare_invoice` runs before
    a single unit moves: the codes, the SIN codes of every product and the
    legend. A sale that cannot be invoiced is refused there, with the shelf
    untouched. `issue_invoice` runs once the note exists: it numbers the
    invoice, builds its CUF and XML, and hands it to the tax office.

    An invoice the SIN refuses is not issued: the caller gives the stock back.
    One that cannot reach the SIN is issued offline instead, and the point of
    sale enters contingency until the SIN answers again
    (`billing_contingency.py`): the till keeps selling.
'''
import gzip
import random
from datetime import date
from urllib.parse import urlencode
from dataclasses import dataclass
from typing import Any, Final

import segno
from boto3.resources.base import ServiceResource

from schemas.billing import (
    EMISSION_OFFLINE,
    EMISSION_ONLINE,
    BillingError,
    CufInput,
    InvoiceContext,
    InvoiceLine,
    Payment,
    SaleLineOut,
    SaleNoteOut,
    SettingsResponse
)
from schemas.billing_siat import (
    InvoiceState,
    SaleInvoice,
    SiatCatalog,
    SiatCodesOut,
    SignificantEvent
)
from services import billing_siat_client as siat_client
from services.billing import take_counter
from services.billing_contingency import active_contingency, enter_contingency
from services.billing_invoice_xml import build_invoice_xml, require_homologated
from services.billing_payments import sin_payment_code
from services.billing_siat import build_cuf, siat_stamp
from services.billing_siat_client import Emitter, InvoiceCancellation, InvoiceSubmission
from services.billing_siat_codes import current_codes, emitter_for, get_catalog, last_codes
from services.environment import load_and_validate_env_vars
from services.exceptions import InvalidInputError, ServiceUnavailableError
from services.logger_config import custom_logger as logger
from services.utils import get_current_time_gmt

# Where the SIN checks an invoice from its QR. It changes with the SIN's
# environment, so it is configuration and not a constant.
ENV_VARS = load_and_validate_env_vars({'SIAT_QR_URL': str})

# The QR's `t`: how the SIN's page previews the invoice, 1 being the roll the
# till prints on.
QR_ROLL_PREVIEW: Final[int] = 1

# Code of the boliviano in the SIN's currency catalogue. Every note of the
# shop is charged in bolivianos, so the rate against itself is one.
CURRENCY_BOLIVIANO: Final[int] = 1
EXCHANGE_RATE_BOLIVIANO: Final[float] = 1.0

# Day of the month after the issue up to which an invoice may be cancelled,
# fixed by the norm.
CANCELLATION_LAST_DAY: Final[int] = 9

# The NIT in the SIN's catalogue of identity documents. Invoiced offline, the
# SIN cannot have validated it, and the norm asks for the exception code 1.
DOCUMENT_TYPE_NIT: Final[int] = 5

# The invoice number is the SIN's sequence, apart from the shop's note series,
# and one per branch and point of sale: each issues its own CUFD.
INVOICE_COUNTER_PREFIX = 'counter#invoice#'

MONEY_DECIMALS = 2

# Medium error correction: the roll is thermal paper, and a smudged corner
# must still scan. The SIN asks for at least 3 x 3 cm; the ticket sizes it.
QR_ERROR_CORRECTION = 'm'
QR_BORDER_MODULES = 2

# The codes a contingency keeps, which are the codes its invoices carry.
CONTINGENCY_CODES = ('cuis', 'cuis_valid_until', 'cufd', 'control_code',
                     'cufd_valid_until', 'address')


@dataclass(frozen = True)
class InvoiceDraft:
    '''
        The sale as the invoice needs it before stock moves: its priced lines,
        the catalogue they came from and how it is being paid.
    '''
    lines: list[SaleLineOut]
    products: dict[str, dict[str, Any]]
    payments: list[Payment]


@dataclass(frozen = True)
class InvoicePlan:
    '''
        What an invoice needs, gathered before the stock moves. `offline` is
        known already: a point of sale in contingency does not try the SIN.
    '''
    emitter: Emitter
    codes: SiatCodesOut
    settings: SettingsResponse
    lines: list[InvoiceLine]
    legend: str
    payment_code: int
    offline: bool = False


@dataclass(frozen = True)
class IssuedInvoice:
    '''
        The invoice a sale became, and the XML that is its legal document: the
        one a package carries and the buyer receives.
    '''
    invoice: SaleInvoice
    xml: str


@dataclass(frozen = True)
class _Document:
    '''
        One invoice built: its CUF, its moment and its XML.
    '''
    cuf: str
    issued_at: str
    xml: str


def prepare_invoice(
    dynamodb_resource: ServiceResource,
    owner: str,
    settings: SettingsResponse,
    draft: InvoiceDraft
) -> InvoicePlan:
    '''
        Everything the invoice of a sale needs, or the reason it cannot have one.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            settings (SettingsResponse): The shop's settings.
            draft (InvoiceDraft): The priced sale and how it is paid.

        Returns:
            InvoicePlan: Ready to issue.

        Raises:
            InvalidInputError: The shop lacks its municipality or NIT, a product
                is not homologated, there is no legend for its activity, or
                the SIN has no code for the combination of payments.
            RegisterNotFoundError: The legends or the payment methods were
                never synchronised.
            ServiceUnavailableError: The SIAT is unreachable and there is no
                CUFD to issue offline with.
    '''
    if not settings.municipality:
        raise InvalidInputError(detail = BillingError.SIAT_ISSUER_INCOMPLETE.value)
    invoice_lines = [detail for line in draft.lines
                     for detail in _invoice_lines(line, draft.products[line.sku])]
    require_homologated(invoice_lines)
    payment_code = sin_payment_code(
        get_catalog(dynamodb_resource, owner, SiatCatalog.PAYMENT_METHODS).entries,
        [payment.method for payment in draft.payments]
    )
    emitter = emitter_for(dynamodb_resource, owner)
    codes, offline = _codes_for_sale(dynamodb_resource, owner, emitter)
    return InvoicePlan(
        emitter = emitter, codes = codes, settings = settings, lines = invoice_lines,
        legend = _legend(dynamodb_resource, owner, invoice_lines[0].sin_activity_code),
        payment_code = payment_code, offline = offline
    )


def issue_invoice(
    dynamodb_resource: ServiceResource,
    owner: str,
    plan: InvoicePlan,
    sale: SaleNoteOut
) -> IssuedInvoice:
    '''
        Numbers the invoice of a sale, builds it and hands it to the SIN — or
        issues it offline when the SIN cannot be reached.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            plan (InvoicePlan): What `prepare_invoice` gathered.
            sale (SaleNoteOut): The note, as it is about to be stored.

        Returns:
            IssuedInvoice: The invoice, accepted or issued offline, and its XML.

        Raises:
            InvalidInputError: SIAT_REFUSED, with the SIN's messages in the log.
    '''
    emitter = plan.emitter
    number = take_counter(dynamodb_resource, owner, f'{INVOICE_COUNTER_PREFIX}'
                          f'{emitter.branch}#{emitter.point_of_sale or 0}')
    if not plan.offline:
        document = _build(plan, sale, number, EMISSION_ONLINE)
        try:
            receipt = siat_client.send_invoice(emitter, InvoiceSubmission(
                cuis = plan.codes.cuis, cufd = plan.codes.cufd,
                archive = gzip.compress(document.xml.encode('utf-8')),
                sent_at = document.issued_at
            ))
        except ServiceUnavailableError:
            # Cut with no answer: the SIN may have registered it. The same
            # number is issued offline with its own CUF, and the doubt is
            # settled when the SIN answers again.
            enter_contingency(dynamodb_resource, owner, plan.codes,
                              SignificantEvent.SIN_UNREACHABLE, uncertain_cuf = document.cuf)
        else:
            if not receipt.accepted:
                error_msg = (f'SIAT refused invoice {number} of sale {sale.number} for '
                             f'{owner}: {receipt.messages or "no messages"}')
                logger.error(error_msg)
                raise InvalidInputError(detail = BillingError.SIAT_REFUSED.value)
            message = f'Invoice {number} of sale {sale.number} accepted for {owner}.'
            logger.info(message)
            return IssuedInvoice(invoice = _sale_invoice(plan, number, document, {
                'state': InvoiceState.ACCEPTED, 'reception_code': receipt.reception_code,
                'siat_state': receipt.state, 'emission_type': EMISSION_ONLINE
            }), xml = document.xml)

    document = _build(plan, sale, number, EMISSION_OFFLINE)
    message = f'Invoice {number} of sale {sale.number} issued offline for {owner}.'
    logger.info(message)
    return IssuedInvoice(invoice = _sale_invoice(plan, number, document, {
        'state': InvoiceState.OFFLINE, 'emission_type': EMISSION_OFFLINE
    }), xml = document.xml)


def _codes_for_sale(
    dynamodb_resource: ServiceResource,
    owner: str,
    emitter: Emitter
) -> tuple[SiatCodesOut, bool]:
    '''
        The codes the next invoice carries, and whether it is issued offline.

        In contingency, the codes it entered with, without trying the SIN.
        Otherwise the codes in force; and if the SIN cannot issue a CUFD that
        is due, the last one, stretched as the norm allows, and the point of
        sale enters contingency.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            emitter (Emitter): Who is issuing.

        Returns:
            tuple[SiatCodesOut, bool]: The codes, and True when offline.

        Raises:
            ServiceUnavailableError: The SIN is away and no CUFD is usable.
    '''
    record = active_contingency(dynamodb_resource, owner, emitter)
    if record is not None:
        return SiatCodesOut(branch = emitter.branch, point_of_sale = emitter.point_of_sale or 0,
                            **{field: record[field] for field in CONTINGENCY_CODES}), True
    try:
        return current_codes(dynamodb_resource, owner), False
    except ServiceUnavailableError:
        codes = last_codes(dynamodb_resource, owner)
        if codes is None:
            raise
        enter_contingency(dynamodb_resource, owner, codes, SignificantEvent.SIN_UNREACHABLE)
        return codes, True


def _build(
    plan: InvoicePlan,
    sale: SaleNoteOut,
    number: int,
    emission_type: int
) -> _Document:
    '''
        The CUF and the XML of one invoice, online or offline.

        Args:
            plan (InvoicePlan): What `prepare_invoice` gathered.
            sale (SaleNoteOut): The note.
            number (int): The invoice number.
            emission_type (int): 1 online, 2 offline; it goes into the CUF.

        Returns:
            _Document: The document.
    '''
    emitter = plan.emitter
    now = get_current_time_gmt()
    # The CUF carries milliseconds and the XML carries the same moment: cut
    # once, so both say exactly the same instant.
    moment = now.replace(microsecond = now.microsecond // 1000 * 1000)
    issued_at = siat_stamp(moment)
    cuf = build_cuf(CufInput(nit = emitter.nit, issued_at = moment, invoice_number = number,
                             branch = emitter.branch,
                             point_of_sale = emitter.point_of_sale or 0,
                             emission_type = emission_type),
                    plan.codes.control_code)
    offline_nit = (emission_type == EMISSION_OFFLINE
                   and sale.buyer.document_type == DOCUMENT_TYPE_NIT)
    xml = build_invoice_xml(sale, InvoiceContext(
        issuer_document = emitter.nit, trade_name = plan.settings.trade_name,
        municipality = plan.settings.municipality, phone = plan.settings.phone,
        address = plan.codes.address, branch = emitter.branch,
        point_of_sale = emitter.point_of_sale, invoice_number = number,
        cuf = cuf, cufd = plan.codes.cufd, issued_at = issued_at, legend = plan.legend,
        currency_code = CURRENCY_BOLIVIANO, exchange_rate = EXCHANGE_RATE_BOLIVIANO,
        exception_code = 1 if offline_nit else 0, payment_method_code = plan.payment_code
    ), plan.lines)
    return _Document(cuf = cuf, issued_at = issued_at, xml = xml)


def _sale_invoice(
    plan: InvoicePlan,
    number: int,
    document: _Document,
    outcome: dict[str, Any]
) -> SaleInvoice:
    '''
        The invoice as the sale stores it.

        Args:
            plan (InvoicePlan): What `prepare_invoice` gathered.
            number (int): The invoice number.
            document (_Document): The document built.
            outcome (dict[str, Any]): Its state and what the SIN answered.

        Returns:
            SaleInvoice: The invoice.
    '''
    emitter = plan.emitter
    return SaleInvoice(number = number, cuf = document.cuf, cufd = plan.codes.cufd,
                       issued_at = document.issued_at, legend = plan.legend,
                       address = plan.codes.address, branch = emitter.branch,
                       point_of_sale = emitter.point_of_sale or 0,
                       qr_url = _qr_url(emitter.nit, document.cuf, number), **outcome)


def cancellation_deadline(issued_at: str) -> date:
    '''
        The last day an invoice can be cancelled: the ninth of the month after
        the one it was issued in (the SIN's page on cancelling fiscal
        documents, `docs/siat/SIAT.md`).

        Args:
            issued_at (str): The invoice's fechaEmision.

        Returns:
            date: The last day, inclusive.
    '''
    issued = date.fromisoformat(issued_at[:10])
    following = date(issued.year + issued.month // 12, issued.month % 12 + 1, 1)
    return following.replace(day = CANCELLATION_LAST_DAY)


def cancel_at_sin(
    dynamodb_resource: ServiceResource,
    owner: str,
    invoice: SaleInvoice,
    reason_code: int
) -> SaleInvoice:
    '''
        Cancels an accepted invoice at the SIN, with the codes in force today.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            invoice (SaleInvoice): The invoice, as the sale stored it.
            reason_code (int): Code of CANCELLATION_REASONS.

        Returns:
            SaleInvoice: The same invoice, cancelled.

        Raises:
            InvalidInputError: SIAT_REFUSED, with the SIN's messages in the log.
            ServiceUnavailableError: The SIAT is unreachable.
    '''
    codes = current_codes(dynamodb_resource, owner)
    receipt = siat_client.cancel_invoice(
        emitter_for(dynamodb_resource, owner),
        InvoiceCancellation(cuis = codes.cuis, cufd = codes.cufd, cuf = invoice.cuf,
                            reason_code = reason_code)
    )
    if not receipt.accepted:
        error_msg = (f'SIAT refused to cancel invoice {invoice.number} for {owner}: '
                     f'{receipt.messages or "no messages"}')
        logger.error(error_msg)
        raise InvalidInputError(detail = BillingError.SIAT_REFUSED.value)

    message = f'Invoice {invoice.number} cancelled at the SIN for {owner}.'
    logger.info(message)
    return invoice.model_copy(update = {'state': InvoiceState.CANCELLED,
                                        'cancellation_reason': reason_code,
                                        'siat_state': receipt.state})


def qr_svg(url: str) -> str:
    '''
        The QR of a link, as inline SVG.

        Drawn on demand from the stored link rather than stored itself: the
        link is the data, the picture is how one ticket shows it.

        Args:
            url (str): The link the QR carries.

        Returns:
            str: An `<svg>` element with no fixed size, so it fills its box.
    '''
    return segno.make(url, error = QR_ERROR_CORRECTION).svg_inline(
        omitsize = True, border = QR_BORDER_MODULES
    )


def _qr_url(
    nit: str,
    cuf: str,
    number: int
) -> str:
    '''
        The link the invoice's QR carries, to check it at the SIN.

        Args:
            nit (str): The issuer's NIT.
            cuf (str): The invoice's CUF.
            number (int): The invoice number.

        Returns:
            str: The URL, as the SIN documents it.
    '''
    query = urlencode({'nit': nit, 'cuf': cuf, 'numero': number, 't': QR_ROLL_PREVIEW})
    return f'{ENV_VARS["SIAT_QR_URL"]}?{query}'


def _invoice_lines(
    line: SaleLineOut,
    product: dict[str, Any]
) -> list[InvoiceLine]:
    '''
        The invoice details of one sale line: one per price it was sold at.

        A line may leave several lots at different prices, and the SIN checks
        quantity times unit price against the subtotal; a single detail with
        an averaged price would not add up. The line's discount is taken from
        the first details until it is spent.

        Args:
            line (SaleLineOut): The priced line.
            product (dict[str, Any]): Its product, with the SIN codes.

        Returns:
            list[InvoiceLine]: The details.
    '''
    by_price: dict[float, float] = {}
    for allocation in line.allocations:
        by_price[allocation.unit_price] = by_price.get(allocation.unit_price, 0) \
            + allocation.quantity

    remaining = line.discount
    details: list[InvoiceLine] = []
    for price, quantity in by_price.items():
        amount = round(price * quantity, MONEY_DECIMALS)
        discount = round(min(remaining, amount), MONEY_DECIMALS)
        remaining -= discount
        details.append(InvoiceLine(
            sku = line.sku, description = line.description, quantity = quantity,
            unit_price = price, discount = discount,
            subtotal = round(amount - discount, MONEY_DECIMALS),
            sin_activity_code = product.get('sin_activity_code'),
            sin_product_code = product.get('sin_product_code'),
            sin_unit_code = product.get('sin_unit_code')
        ))
    return details


def _legend(
    dynamodb_resource: ServiceResource,
    owner: str,
    activity_code: str | None
) -> str:
    '''
        One of the legends of the activity, at random.

        Law 453 asks the legends to rotate from one invoice to the next, and
        the SIN publishes them per economic activity.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            activity_code (str | None): Activity of the invoice.

        Returns:
            str: The legend.

        Raises:
            InvalidInputError: LEGEND_NOT_FOUND for that activity.
            RegisterNotFoundError: The legends were never synchronised.
    '''
    legends = [entry.description
               for entry in get_catalog(dynamodb_resource, owner, SiatCatalog.LEGENDS).entries
               if entry.activity_code == activity_code]
    if not legends:
        error_msg = f'No SIN legend for activity {activity_code} of {owner}.'
        logger.warning(error_msg)
        raise InvalidInputError(detail = BillingError.LEGEND_NOT_FOUND.value)
    return random.choice(legends)
