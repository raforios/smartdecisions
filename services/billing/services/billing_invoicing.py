'''
    Turning a sale into an invoice the SIN receives.

    Two halves, because stock sits between them. `prepare_invoice` runs before
    a single unit moves: the codes in force, the SIN codes of every product
    and the legend. A sale that cannot be invoiced is refused there, with the
    shelf untouched. `issue_invoice` runs once the note exists: it numbers the
    invoice, builds its CUF and XML, and hands it to the tax office.

    An invoice the SIN refuses or cannot receive is not kept as pending: the
    caller gives the stock back and the sale is not issued. Issuing offline
    and sending in packages is contingency, which comes later.
'''
import gzip
import random
from urllib.parse import urlencode
from dataclasses import dataclass
from typing import Any, Final

import segno
from boto3.resources.base import ServiceResource

from schemas.billing import (
    BillingError,
    CufInput,
    InvoiceContext,
    InvoiceLine,
    SaleLineOut,
    SaleNoteOut,
    SettingsResponse
)
from schemas.billing_siat import InvoiceState, SaleInvoice, SiatCatalog, SiatCodesOut
from services import billing_siat_client as siat_client
from services.billing import take_counter
from services.billing_invoice_xml import build_invoice_xml, require_homologated
from services.billing_siat import build_cuf
from services.billing_siat_client import Emitter, InvoiceCancellation, InvoiceSubmission
from services.billing_siat_codes import current_codes, emitter_for, get_catalog
from services.environment import load_and_validate_env_vars
from services.exceptions import InvalidInputError
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

# The invoice number is the SIN's sequence, apart from the shop's note series,
# and one per branch and point of sale: each issues its own CUFD.
INVOICE_COUNTER_PREFIX = 'counter#invoice#'

MONEY_DECIMALS = 2

# Medium error correction: the roll is thermal paper, and a smudged corner
# must still scan. The SIN asks for at least 3 x 3 cm; the ticket sizes it.
QR_ERROR_CORRECTION = 'm'
QR_BORDER_MODULES = 2


@dataclass(frozen = True)
class InvoicePlan:
    '''
        What an invoice needs, gathered before the stock moves.
    '''
    emitter: Emitter
    codes: SiatCodesOut
    settings: SettingsResponse
    lines: list[InvoiceLine]
    legend: str


def prepare_invoice(
    dynamodb_resource: ServiceResource,
    owner: str,
    settings: SettingsResponse,
    lines: list[SaleLineOut],
    products: dict[str, dict[str, Any]]
) -> InvoicePlan:
    '''
        Everything the invoice of a sale needs, or the reason it cannot have one.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            settings (SettingsResponse): The shop's settings.
            lines (list[SaleLineOut]): The priced lines of the sale.
            products (dict[str, dict[str, Any]]): The catalogue by SKU.

        Returns:
            InvoicePlan: Ready to issue.

        Raises:
            InvalidInputError: The shop lacks its municipality or NIT, a product
                is not homologated, or there is no legend for its activity.
            RegisterNotFoundError: The legends were never synchronised.
            ServiceUnavailableError: The SIAT is unreachable for a new code.
    '''
    if not settings.municipality:
        raise InvalidInputError(detail = BillingError.SIAT_ISSUER_INCOMPLETE.value)
    invoice_lines = [detail for line in lines
                     for detail in _invoice_lines(line, products[line.sku])]
    require_homologated(invoice_lines)
    return InvoicePlan(
        emitter = emitter_for(dynamodb_resource, owner),
        codes = current_codes(dynamodb_resource, owner),
        settings = settings, lines = invoice_lines,
        legend = _legend(dynamodb_resource, owner, invoice_lines[0].sin_activity_code)
    )


def issue_invoice(
    dynamodb_resource: ServiceResource,
    owner: str,
    plan: InvoicePlan,
    sale: SaleNoteOut
) -> SaleInvoice:
    '''
        Numbers the invoice of a sale, builds it and hands it to the SIN.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            plan (InvoicePlan): What `prepare_invoice` gathered.
            sale (SaleNoteOut): The note, as it is about to be stored.

        Returns:
            SaleInvoice: The invoice the SIN accepted.

        Raises:
            InvalidInputError: SIAT_REFUSED, with the SIN's messages in the log.
            ServiceUnavailableError: The SIAT is unreachable.
    '''
    emitter = plan.emitter
    number = take_counter(dynamodb_resource, owner, f'{INVOICE_COUNTER_PREFIX}'
                          f'{emitter.branch}#{emitter.point_of_sale or 0}')
    now = get_current_time_gmt()
    # The CUF carries milliseconds and the XML carries the same moment: cut
    # once, so both say exactly the same instant.
    moment = now.replace(microsecond = now.microsecond // 1000 * 1000)
    issued_at = moment.strftime('%Y-%m-%dT%H:%M:%S.') + f'{moment.microsecond // 1000:03d}'
    cuf = build_cuf(CufInput(nit = emitter.nit, issued_at = moment, invoice_number = number,
                             branch = emitter.branch,
                             point_of_sale = emitter.point_of_sale or 0),
                    plan.codes.control_code)

    xml = build_invoice_xml(sale, InvoiceContext(
        issuer_document = emitter.nit, trade_name = plan.settings.trade_name,
        municipality = plan.settings.municipality, phone = plan.settings.phone,
        address = plan.codes.address, branch = emitter.branch,
        point_of_sale = emitter.point_of_sale, invoice_number = number,
        cuf = cuf, cufd = plan.codes.cufd, issued_at = issued_at, legend = plan.legend,
        currency_code = CURRENCY_BOLIVIANO, exchange_rate = EXCHANGE_RATE_BOLIVIANO
    ), plan.lines)

    receipt = siat_client.send_invoice(emitter, InvoiceSubmission(
        cuis = plan.codes.cuis, cufd = plan.codes.cufd,
        archive = gzip.compress(xml.encode('utf-8')), sent_at = issued_at
    ))
    if not receipt.accepted:
        error_msg = (f'SIAT refused invoice {number} of sale {sale.number} for {owner}: '
                     f'{receipt.messages or "no messages"}')
        logger.error(error_msg)
        raise InvalidInputError(detail = BillingError.SIAT_REFUSED.value)

    message = f'Invoice {number} of sale {sale.number} accepted for {owner}.'
    logger.info(message)
    return SaleInvoice(number = number, cuf = cuf, cufd = plan.codes.cufd,
                       issued_at = issued_at, legend = plan.legend,
                       address = plan.codes.address, branch = emitter.branch,
                       point_of_sale = emitter.point_of_sale or 0,
                       state = InvoiceState.ACCEPTED,
                       reception_code = receipt.reception_code, siat_state = receipt.state,
                       qr_url = _qr_url(emitter.nit, cuf, number))


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
