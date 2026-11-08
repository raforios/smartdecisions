'''
    SmartBilling → SmartDecisions, as it happens (Rafael, 6-nov-2026).

    When a shop turns `send_to_smartdecisions` on, every sale it issues and
    every product it saves also reaches its SmartDecisions: the sale lines go
    to the company's most recent dataset (`/v1/commercial/sales/live`) and the
    product to its master (`/v1/commercial/products`). A cancellation or a
    return —and undoing either— goes to `/v1/commercial/reversals`: recorded
    apart, with the sale's lines as they now stand, so SmartDecisions counts
    net sales and still knows what was undone (Rafael, 6-nov-2026). Both are
    built from what BILLING stored, so the state of the sale or the note says
    whether the cancellation or the return still stands.

    The request does not go out over HTTP from here: a Lambda freezes as soon
    as it answers, so a call left running after the sale may never leave
    (seen live on 6-nov). It is queued instead —the path, the body and the
    cashier's own token, so SmartDecisions files it under the same company— in
    a FIFO queue grouped by shop, which COMMERCIAL drains in order: two sales
    of one shop never rewrite its dataset at the same time. Queuing takes
    milliseconds and never holds the sale back; a failure is only logged.
'''
import hashlib
import json
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from boto3.resources.base import ServiceResource
from fastapi import Request

from models.billing import LOTS_TABLE
from schemas.billing import PaymentMethod, ProductOut, PurchaseNoteOut, SaleNoteOut, SaleStatus
from schemas.billing_returns import CreditNoteOut
from schemas.billing_siat import InvoiceState, SiatCatalog
from services.billing import (
    MONEY_DECIMALS,
    expiry_order,
    get_settings,
    new_id,
    products_by_sku,
    read_partition
)
from services.billing_returns import net_of_returns
from services.billing_sales import read_sale, sale_out
from services.billing_siat_codes import get_catalog
from services.environment import load_and_validate_env_vars
from services.exceptions import RegisterNotFoundError
from services.logger_config import custom_logger as logger
from services.utils import get_current_time_gmt

LIVE_QUEUE_URL = load_and_validate_env_vars({'COMMERCIAL_LIVE_QUEUE_URL': str})[
    'COMMERCIAL_LIVE_QUEUE_URL']

LIVE_SALES_PATH = '/v1/commercial/sales/live'
PRODUCTS_PATH = '/v1/commercial/products'
REVERSALS_PATH = '/v1/commercial/reversals'
STOCK_PATH = '/v1/commercial/stock/live'
PURCHASES_PATH = '/v1/commercial/purchases/live'
# What BILLING records every amount in.
CURRENCY = 'BOB'

# The till's means of payment in SmartDecisions' codes: it keeps one card.
PAYMENT_CODES: dict[PaymentMethod, str] = {
    PaymentMethod.CASH: 'CASH',
    PaymentMethod.DEBIT_CARD: 'CARD',
    PaymentMethod.CREDIT_CARD: 'CARD',
    PaymentMethod.BANK_TRANSFER: 'BANK_TRANSFER',
    PaymentMethod.MOBILE_WALLET: 'MOBILE_WALLET',
}
# A counter sale is paid at once.
CASH_TERMS = 'CASH'


def sale_rows(sale: SaleNoteOut) -> list[dict[str, Any]]:
    '''
        The sale as SmartDecisions' sales lines: one per product sold.

        Args:
            sale (SaleNoteOut): The sale issued.

        Returns:
            list[dict[str, Any]]: The lines, in SmartDecisions' sales contract.
    '''
    return [{
        'date': sale.created_at[:10],
        'order_id': sale.number,
        # The buyer's NIT or CI is the client's code, so SmartDecisions' client
        # card is the same client BILLING invoices (Rafael, 8-nov-2026).
        'pos_id': sale.buyer.document or None,
        'pos_name': sale.buyer.name or None,
        'seller': sale.created_by,
        'product_id': line.sku,
        'product_name': line.description,
        'quantity': line.quantity,
        'unit_price': round(line.subtotal / line.quantity, MONEY_DECIMALS),
        'unit_cost': round(line.cost / line.quantity, MONEY_DECIMALS),
        'total_amount': line.total,
        'payment_terms': CASH_TERMS,
        'payment_method': PAYMENT_CODES[sale.payment_method]
    } for line in sale.lines]


def product_record(product: ProductOut) -> dict[str, Any]:
    '''
        The product as SmartDecisions' master keeps it.

        Args:
            product (ProductOut): The product saved.

        Returns:
            dict[str, Any]: The product, in SmartDecisions' master contract.
    '''
    return {
        'sku': product.sku,
        'description': product.description,
        'supplier': product.laboratory,
        'category': product.category,
        'unit': product.unit.value,
        'suggested_price': product.suggested_price
    }


def _undone_lines(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    '''
        Stored sale or note lines as SmartDecisions' undone lines.

        Args:
            lines (list[dict[str, Any]]): Lines with sku, description,
                quantity and total.

        Returns:
            list[dict[str, Any]]: Product, units and bolivianos per line.
    '''
    return [{'product_id': line['sku'], 'product_name': line['description'],
             'quantity': line['quantity'], 'amount': line['total']} for line in lines]


def _standing_rows(stored: dict[str, Any]) -> list[dict[str, Any]]:
    '''
        The sale's lines as they now stand: nothing when it is cancelled,
        what the buyer kept after the returns the SIN holds.

        Args:
            stored (dict[str, Any]): The sale as stored.

        Returns:
            list[dict[str, Any]]: Its lines in SmartDecisions' sales contract.
    '''
    if stored['status'] == SaleStatus.CANCELLED.value:
        return []
    kept = net_of_returns(stored)
    return sale_rows(sale_out(kept)) if kept else []


def _reason(
    dynamodb_resource: ServiceResource,
    owner: str,
    code: Any
) -> str | None:
    '''
        What the SIN's cancellation catalogue calls a reason: data the SIN
        publishes, not wording of ours.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            code (Any): The reason code; None for an internal note.

        Returns:
            str | None: Its description; None without a code or a synced catalogue.
    '''
    if code is None:
        return None
    try:
        entries = get_catalog(dynamodb_resource, owner, SiatCatalog.CANCELLATION_REASONS).entries
    except RegisterNotFoundError:
        return None
    return next((entry.description for entry in entries if entry.code == str(code)), None)


def cancellation_record(
    dynamodb_resource: ServiceResource,
    owner: str,
    stored: dict[str, Any]
) -> dict[str, Any]:
    '''
        A sale's cancellation as SmartDecisions records it; standing while the
        sale is cancelled, reverted once it is valid again.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            stored (dict[str, Any]): The sale as stored after the change.

        Returns:
            dict[str, Any]: The record, in SmartDecisions' reversal contract.
    '''
    code = (stored.get('invoice') or {}).get('cancellation_reason')
    return {
        'reversal_id': stored['number'], 'kind': 'CANCELLATION',
        'state': 'ACTIVE' if stored['status'] == SaleStatus.CANCELLED.value else 'REVERTED',
        'order_id': stored['number'],
        'date': str(stored.get('cancelled_at') or stored['created_at'])[:10],
        'reason_code': int(code) if code else None,
        'reason': _reason(dynamodb_resource, owner, code),
        # What the cancellation undid: what the buyer still had of the sale.
        'lines': _undone_lines((net_of_returns(stored) or stored)['lines']),
        'rows': _standing_rows(stored)
    }


def return_record(
    stored: dict[str, Any],
    note: dict[str, Any]
) -> dict[str, Any]:
    '''
        A credit note's return as SmartDecisions records it; standing while
        the SIN holds the note, reverted once the note is cancelled.

        Args:
            stored (dict[str, Any]): The sale as stored after the change.
            note (dict[str, Any]): The credit note, as stored in the sale.

        Returns:
            dict[str, Any]: The record, in SmartDecisions' reversal contract.
    '''
    return {
        'reversal_id': f'NC-{note["number"]}', 'kind': 'RETURN',
        'state': 'REVERTED' if note['state'] == InvoiceState.CANCELLED.value else 'ACTIVE',
        'order_id': stored['number'], 'date': str(note['issued_at'])[:10],
        'lines': _undone_lines(note['lines']), 'rows': _standing_rows(stored)
    }


def queue_group(owner: str) -> str:
    '''
        The shop's line in the FIFO queue. SQS takes only letters, digits and
        punctuation there, and a company's name has spaces ("The Pharma"), so
        the line is named by the name's fingerprint: always valid, the same
        for the same shop, different between shops.

        Args:
            owner (str): The shop.

        Returns:
            str: Its message group id.
    '''
    return hashlib.sha256(owner.encode('utf-8')).hexdigest()


def queue_request(
    queue_url: str,
    owner: str,
    request: dict[str, Any]
) -> None:
    '''
        Leaves one request for SmartDecisions in the shop's line; never raises.

        Args:
            queue_url (str): The receiving service's queue.
            owner (str): The shop, which orders its own requests.
            request (dict[str, Any]): `path`, `body` and `authorization`.
    '''
    try:
        boto3.client('sqs').send_message(
            QueueUrl = queue_url, MessageBody = json.dumps(request),
            MessageGroupId = queue_group(owner), MessageDeduplicationId = new_id()
        )
    except (BotoCoreError, ClientError) as error:
        error_msg = f'SmartDecisions request {request["path"]} not queued: {error}'
        logger.error(error_msg)
        return
    message = f'Queued for SmartDecisions {request["path"]}.'
    logger.info(message)


def share_if_wanted(
    dynamodb_resource: ServiceResource,
    owner: str,
    request: Request | None,
    delivery: tuple[str, str, dict[str, Any]]
) -> None:
    '''
        Queues one delivery when the shop has the switch on.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            request (Request | None): The incoming request, for the token.
            delivery (tuple[str, str, dict[str, Any]]): The queue, the path
                and the body.
    '''
    authorization = request.headers.get('Authorization') if request is not None else None
    if not authorization:
        return
    try:
        wanted = get_settings(dynamodb_resource, owner).send_to_smartdecisions
    except RegisterNotFoundError:
        # A shop not set up yet has not turned the switch on either.
        return
    if not wanted:
        return
    queue_url, path, body = delivery
    queue_request(queue_url, owner, {'path': path, 'body': body, 'authorization': authorization})


def share_sale(
    dynamodb_resource: ServiceResource,
    owner: str,
    sale: SaleNoteOut,
    request: Request | None
) -> None:
    '''
        Sends a sale just issued to SmartDecisions, when the shop wants it.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            sale (SaleNoteOut): The sale issued.
            request (Request | None): The incoming request, for the token.
    '''
    share_if_wanted(dynamodb_resource, owner, request,
                    (LIVE_QUEUE_URL, LIVE_SALES_PATH, {'rows': sale_rows(sale)}))


def share_product(
    dynamodb_resource: ServiceResource,
    owner: str,
    product: ProductOut,
    request: Request | None
) -> None:
    '''
        Sends a product just saved to SmartDecisions' master, when the shop
        wants it.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            product (ProductOut): The product saved.
            request (Request | None): The incoming request, for the token.
    '''
    share_if_wanted(dynamodb_resource, owner, request,
                    (LIVE_QUEUE_URL, PRODUCTS_PATH, {'products': [product_record(product)]}))


def share_cancellation(
    dynamodb_resource: ServiceResource,
    owner: str,
    sale_id: str,
    request: Request | None
) -> None:
    '''
        Sends a sale's cancellation —or its reversion— to SmartDecisions, when
        the shop wants it.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            sale_id (str): The sale just cancelled or made valid again.
            request (Request | None): The incoming request, for the token.
    '''
    stored = read_sale(dynamodb_resource, owner, sale_id)
    if stored:
        share_if_wanted(dynamodb_resource, owner, request,
                        (LIVE_QUEUE_URL, REVERSALS_PATH,
                         cancellation_record(dynamodb_resource, owner, stored)))


def share_return(
    dynamodb_resource: ServiceResource,
    owner: str,
    note: CreditNoteOut,
    request: Request | None
) -> None:
    '''
        Sends a return —or its cancellation, or that cancellation reverted— to
        SmartDecisions, when the shop wants it.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            note (CreditNoteOut): The credit note just issued or changed.
            request (Request | None): The incoming request, for the token.
    '''
    stored = read_sale(dynamodb_resource, owner, note.sale_id)
    stored_note = next((item for item in (stored or {}).get('credit_notes', [])
                        if item['credit_note_id'] == note.credit_note_id), None)
    if stored_note:
        share_if_wanted(dynamodb_resource, owner, request,
                        (LIVE_QUEUE_URL, REVERSALS_PATH, return_record(stored, stored_note)))


def stock_rows(
    dynamodb_resource: ServiceResource,
    owner: str,
    day: str
) -> list[dict[str, Any]]:
    '''
        Today's photo of every product on the shelf: units, cost and the price
        the next batch sells at (Rafael, 8-nov-2026).

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            day (str): The photo's day, ISO date.

        Returns:
            list[dict[str, Any]]: Rows in SmartDecisions' stock contract.
    '''
    lots: dict[str, list[dict[str, Any]]] = {}
    for lot in read_partition(dynamodb_resource, LOTS_TABLE, owner):
        if float(lot['quantity_remaining']) > 0:
            lots.setdefault(lot['sku'], []).append(lot)
    rows = []
    for sku, product in products_by_sku(dynamodb_resource, owner).items():
        held = sorted(lots.get(sku, []), key = expiry_order)
        units = sum(float(lot['quantity_remaining']) for lot in held)
        cost = sum(float(lot['quantity_remaining']) * float(lot['unit_cost']) for lot in held)
        price = float(held[0]['sale_price']) if held else float(
            product.get('suggested_price') or 0)
        rows.append({'snapshot_date': day, 'product_id': sku,
                     'product_name': product['description'], 'on_hand': units,
                     'unit_cost': round(cost / units, MONEY_DECIMALS) if units else None,
                     'unit_price': price})
    return rows


def share_stock(
    dynamodb_resource: ServiceResource,
    owner: str,
    request: Request | None
) -> None:
    '''
        Sends today's shelf to SmartDecisions, when the shop wants it.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            request (Request | None): The incoming request, for the token.
    '''
    rows = stock_rows(dynamodb_resource, owner, get_current_time_gmt().date().isoformat())
    if rows:
        share_if_wanted(dynamodb_resource, owner, request,
                        (LIVE_QUEUE_URL, STOCK_PATH, {'mode': 'APPEND', 'rows': rows}))


def share_purchase(
    dynamodb_resource: ServiceResource,
    owner: str,
    purchase: PurchaseNoteOut,
    request: Request | None
) -> None:
    '''
        Sends a purchase just received to SmartDecisions, when the shop wants it.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            purchase (PurchaseNoteOut): The purchase.
            request (Request | None): The incoming request, for the token.
    '''
    products = products_by_sku(dynamodb_resource, owner)
    rows = [{'purchase_date': purchase.created_at[:10], 'supplier': purchase.supplier_name,
             'product_id': line.sku,
             'product_name': products.get(line.sku, {}).get('description', line.sku),
             'quantity': line.quantity, 'unit_cost': line.unit_cost, 'currency': CURRENCY}
            for line in purchase.lines]
    share_if_wanted(dynamodb_resource, owner, request,
                    (LIVE_QUEUE_URL, PURCHASES_PATH, {'mode': 'APPEND', 'rows': rows}))
