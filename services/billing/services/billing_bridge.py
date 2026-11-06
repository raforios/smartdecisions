'''
    SmartBilling → SmartDecisions, as it happens (Rafael, 6-nov-2026).

    When a shop turns `send_to_smartdecisions` on, every sale it issues and
    every product it saves also reaches its SmartDecisions: the sale lines go
    to the company's most recent dataset (`/v1/commercial/sales/live`) and the
    product to its master (`/v1/commercial/products`).

    The request does not go out over HTTP from here: a Lambda freezes as soon
    as it answers, so a call left running after the sale may never leave
    (seen live on 6-nov). It is queued instead —the path, the body and the
    cashier's own token, so SmartDecisions files it under the same company— in
    a FIFO queue grouped by shop, which COMMERCIAL drains in order: two sales
    of one shop never rewrite its dataset at the same time. Queuing takes
    milliseconds and never holds the sale back; a failure is only logged.
'''
import json
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from boto3.resources.base import ServiceResource
from fastapi import Request

from schemas.billing import PaymentMethod, ProductOut, SaleNoteOut
from services.billing import MONEY_DECIMALS, get_settings, new_id
from services.environment import load_and_validate_env_vars
from services.exceptions import RegisterNotFoundError
from services.logger_config import custom_logger as logger

LIVE_QUEUE_URL = load_and_validate_env_vars({'COMMERCIAL_LIVE_QUEUE_URL': str})[
    'COMMERCIAL_LIVE_QUEUE_URL']

LIVE_SALES_PATH = '/v1/commercial/sales/live'
PRODUCTS_PATH = '/v1/commercial/products'

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
        'unit': product.unit.value,
        'suggested_price': product.suggested_price
    }


def _queue(
    owner: str,
    request: dict[str, Any]
) -> None:
    '''
        Leaves one request for COMMERCIAL in the shop's line; never raises.

        Args:
            owner (str): The shop, which orders its own requests.
            request (dict[str, Any]): `path`, `body` and `authorization`.
    '''
    try:
        boto3.client('sqs').send_message(
            QueueUrl = LIVE_QUEUE_URL, MessageBody = json.dumps(request),
            MessageGroupId = owner, MessageDeduplicationId = new_id()
        )
    except (BotoCoreError, ClientError) as error:
        error_msg = f'SmartDecisions request {request["path"]} not queued: {error}'
        logger.error(error_msg)
        return
    message = f'Queued for SmartDecisions {request["path"]}.'
    logger.info(message)


def _share(
    dynamodb_resource: ServiceResource,
    owner: str,
    request: Request | None,
    delivery: tuple[str, dict[str, Any]]
) -> None:
    '''
        Queues one delivery when the shop has the switch on.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            request (Request | None): The incoming request, for the token.
            delivery (tuple[str, dict[str, Any]]): The path and the body.
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
    path, body = delivery
    _queue(owner, {'path': path, 'body': body, 'authorization': authorization})


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
    _share(dynamodb_resource, owner, request, (LIVE_SALES_PATH, {'rows': sale_rows(sale)}))


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
    _share(dynamodb_resource, owner, request,
           (PRODUCTS_PATH, {'products': [product_record(product)]}))
