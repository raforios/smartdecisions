'''
    Contingency: issuing while the SIN cannot be reached, and catching up.

    A point of sale enters it on its own the moment an invoice cannot reach the
    tax office, and from then on issues offline with the CUFD it had: the till
    keeps selling and nobody waits on a service we do not control. It leaves it
    on its own too: a scheduled run checks the SIN every few minutes and, once
    it answers, asks for a new CUFD, registers the significant event, settles
    the sendings that were cut without an answer, and sends the offline
    invoices in packages.

    Stored beside the codes, in `billing_settings`:

    | setting_key                              | What                              |
    |------------------------------------------|-----------------------------------|
    | siat#contingency#<branch>#<point_of_sale>| The contingency in course         |
    | siat#package#<reception_code>            | A package the SIN has not settled |

    The order of a recovery is the SIN's own (`docs/siat/SIAT.md` and its
    pages on contingency): a new CUFD first, then the event, then the
    packages. The event's reception code is stored as soon as the SIN gives
    it, so a recovery cut halfway does not register the same event twice.
'''
from datetime import timedelta
from typing import Any

from boto3.dynamodb.conditions import Attr
from boto3.resources.base import ServiceResource
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException

from models.billing import OWNER_KEY, SALES_TABLE, SALE_SORT_KEY, SETTINGS_TABLE, SETTING_SORT_KEY
from schemas.billing import BillingError
from schemas.billing_siat import (
    ContingencyOut,
    ContingencyStatus,
    InvoiceState,
    PackageReceipt,
    RecoveryOut,
    SiatCatalog,
    SiatCodesOut,
    SignificantEvent
)
from services import billing_siat_client as siat_client
from services import billing_siat_packages as packages
from services.billing import SortBounds, date_window, from_dynamo, read_partition, write_item
from services.billing_siat import siat_stamp
from services.billing_siat_client import Emitter, InvoiceCancellation
from services.billing_siat_codes import current_codes, emitter_for, get_catalog, last_codes
from services.exceptions import RegisterNotFoundError, ServiceUnavailableError
from services.logger_config import custom_logger as logger
from services.utils import get_current_time_gmt, load_parameters

PARAMETERS = load_parameters({'BILLING_OFFLINE_RETRY_MINUTES': int})
RETRY_MINUTES = PARAMETERS['BILLING_OFFLINE_RETRY_MINUTES']

CONTINGENCY_PREFIX = 'siat#contingency#'
PACKAGE_PREFIX = 'siat#package#'

# What the SIN answers about a package or an invoice.
STATE_PENDING = '901'
STATE_OBSERVED = '904'
STATE_VALID = '908'

# The reason an online sending the SIN did register is cancelled with: its
# offline twin, with another CUF, is the invoice the buyer holds.
DUPLICATE_REASON = 1


def contingency_key(emitter: Emitter) -> str:
    '''
        Where the contingency of one branch and point of sale is stored.

        Args:
            emitter (Emitter): Who is issuing.

        Returns:
            str: The setting key.
    '''
    return f'{CONTINGENCY_PREFIX}{emitter.branch}#{emitter.point_of_sale or 0}'


def active_contingency(
    dynamodb_resource: ServiceResource,
    owner: str,
    emitter: Emitter
) -> dict[str, Any] | None:
    '''
        The contingency in course at this point of sale, if any.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            emitter (Emitter): Its branch and point of sale.

        Returns:
            dict[str, Any] | None: The stored record.
    '''
    return from_dynamo(dynamodb_resource.Table(SETTINGS_TABLE).get_item(
        Key = {OWNER_KEY: owner, SETTING_SORT_KEY: contingency_key(emitter)}
    ).get('Item'))


def enter_contingency(
    dynamodb_resource: ServiceResource,
    owner: str,
    codes: SiatCodesOut,
    event: SignificantEvent,
    uncertain_cuf: str | None = None
) -> dict[str, Any]:
    '''
        Starts issuing offline at the shop's point of sale, or adds to the
        contingency already in course.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            codes (SiatCodesOut): The codes in force; the offline invoices
                carry its CUFD.
            event (SignificantEvent): Why.
            uncertain_cuf (str | None): An online sending cut with no answer:
                the SIN may have registered it, and that is settled on recovery.

        Returns:
            dict[str, Any]: The contingency record.
    '''
    emitter = emitter_for(dynamodb_resource, owner)
    record = active_contingency(dynamodb_resource, owner, emitter)
    if record is None:
        record = {OWNER_KEY: owner, SETTING_SORT_KEY: contingency_key(emitter),
                  'event': int(event), 'started_at': siat_stamp(get_current_time_gmt()),
                  'last_check_at': siat_stamp(get_current_time_gmt()),
                  'uncertain_cufs': [],
                  **codes.model_dump(include = {'cuis', 'cuis_valid_until', 'cufd',
                                                'control_code', 'address', 'cufd_valid_until'})}
        error_msg = f'{owner} enters contingency ({event.name}) at {record[SETTING_SORT_KEY]}.'
        logger.warning(error_msg)
    if uncertain_cuf and uncertain_cuf not in record['uncertain_cufs']:
        record['uncertain_cufs'].append(uncertain_cuf)
    write_item(dynamodb_resource, SETTINGS_TABLE, record)
    return record


def start_contingency(
    dynamodb_resource: ServiceResource,
    owner: str,
    event: SignificantEvent
) -> ContingencyStatus:
    '''
        Enters contingency by hand: the shop knows before the system does —
        a point of sale with no internet.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            event (SignificantEvent): Why, one of the four issued offline.

        Returns:
            ContingencyStatus: The contingency in course.

        Raises:
            ServiceUnavailableError: The SIN is away and no CUFD is usable.
    '''
    try:
        codes = current_codes(dynamodb_resource, owner)
    except ServiceUnavailableError:
        codes = last_codes(dynamodb_resource, owner)
        if codes is None:
            raise
    enter_contingency(dynamodb_resource, owner, codes, event)
    return contingency_status(dynamodb_resource, owner)


def contingency_status(
    dynamodb_resource: ServiceResource,
    owner: str
) -> ContingencyStatus:
    '''
        Whether the shop's point of sale is offline.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.

        Returns:
            ContingencyStatus: The contingency and its invoices waiting.
    '''
    emitter = emitter_for(dynamodb_resource, owner)
    record = active_contingency(dynamodb_resource, owner, emitter)
    if record is None:
        return ContingencyStatus(offline = False)
    return ContingencyStatus(offline = True, contingency = ContingencyOut(
        branch = emitter.branch, point_of_sale = emitter.point_of_sale or 0,
        event = record['event'], started_at = record['started_at'], cufd = record['cufd'],
        last_check_at = record.get('last_check_at'),
        pending_invoices = len(_offline_sales(dynamodb_resource, owner, record))
    ))


def recover(
    dynamodb_resource: ServiceResource,
    owner: str
) -> RecoveryOut:
    '''
        Tries to leave contingency: when the SIN answers, registers the event
        and sends the offline invoices.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.

        Returns:
            RecoveryOut: What was done; `recovered` False while the SIN is away.

        Raises:
            RegisterNotFoundError: The SIGNIFICANT_EVENTS catalogue was never
                synchronised.
            InvalidInputError: The SIN refused the event.
            ServiceUnavailableError: The SIN went away again halfway.
    '''
    emitter = emitter_for(dynamodb_resource, owner)
    record = active_contingency(dynamodb_resource, owner, emitter)
    if record is None:
        return RecoveryOut(recovered = True)

    record['last_check_at'] = siat_stamp(get_current_time_gmt())
    if not packages.verify_communication():
        write_item(dynamodb_resource, SETTINGS_TABLE, record)
        message = f'{owner} stays offline: the SIN does not answer.'
        logger.info(message)
        return RecoveryOut(recovered = False)

    codes = current_codes(dynamodb_resource, owner, force_cufd = True)
    if record.get('event_reception_code') is None:
        event = packages.EventRegistration(
            cuis = codes.cuis, cufd = codes.cufd, cufd_event = record['cufd'],
            event_code = int(record['event']),
            description = _event_description(dynamodb_resource, owner, record['event']),
            started_at = record['started_at'], ended_at = siat_stamp(get_current_time_gmt())
        )
        record['event_reception_code'] = packages.register_event(emitter, event)
        write_item(dynamodb_resource, SETTINGS_TABLE, record)

    uncertain_cancelled = _settle_uncertain(emitter, codes, record)
    sales = _offline_sales(dynamodb_resource, owner, record)
    receipts = [
        _send_batch(dynamodb_resource, owner, (emitter, codes, record),
                    sales[start:start + packages.MAX_PACKAGE_INVOICES])
        for start in range(0, len(sales), packages.MAX_PACKAGE_INVOICES)
    ]

    dynamodb_resource.Table(SETTINGS_TABLE).delete_item(
        Key = {OWNER_KEY: owner, SETTING_SORT_KEY: record[SETTING_SORT_KEY]}
    )
    message = (f'{owner} left contingency: event {record["event_reception_code"]}, '
               f'{len(sales)} invoice(s) in {len(receipts)} package(s).')
    logger.info(message)
    return RecoveryOut(recovered = True, event_reception_code = record['event_reception_code'],
                       packages = receipts, invoices_sent = len(sales),
                       invoices_observed = sum(len(receipt.observed) for receipt in receipts),
                       uncertain_cancelled = uncertain_cancelled)


def run_scheduled(dynamodb_resource: ServiceResource) -> list[str]:
    '''
        What the scheduled run does: every contingency due for a check is
        tried, and every package the SIN had not settled is asked about again.

        One shop failing does not stop the others: its error goes to the log
        and the next run tries it again.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.

        Returns:
            list[str]: One line per shop touched, for the invocation's result.
    '''
    rows = _scan_prefix(dynamodb_resource, 'siat#')
    due = siat_stamp(get_current_time_gmt() - timedelta(minutes = RETRY_MINUTES))
    done: list[str] = []
    for row in rows:
        key = row[SETTING_SORT_KEY]
        try:
            if key.startswith(CONTINGENCY_PREFIX) and row.get('last_check_at', '') <= due:
                outcome = recover(dynamodb_resource, row[OWNER_KEY])
                done.append(f'{row[OWNER_KEY]} {key}: recovered={outcome.recovered}')
            elif key.startswith(PACKAGE_PREFIX):
                settle_package(dynamodb_resource, row)
                done.append(f'{row[OWNER_KEY]} {key}: validated')
        except (HTTPException, BotoCoreError, ClientError) as error:
            # One shop's failure must not leave the others offline: it is
            # logged with its cause and tried again on the next run.
            error_msg = f'Scheduled contingency run failed for {row[OWNER_KEY]} {key}: {error}'
            logger.error(error_msg)
    return done


def settle_package(
    dynamodb_resource: ServiceResource,
    row: dict[str, Any]
) -> PackageReceipt:
    '''
        Asks the SIN again about a package it had not settled.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            row (dict[str, Any]): The stored package.

        Returns:
            PackageReceipt: What the SIN answers now.
    '''
    owner = row[OWNER_KEY]
    emitter = emitter_for(dynamodb_resource, owner)
    codes = current_codes(dynamodb_resource, owner)
    receipt = packages.validate_package(emitter, (codes.cuis, codes.cufd),
                                        row['reception_code'])
    if receipt.state != STATE_PENDING:
        _mark_batch(dynamodb_resource, owner, row['sale_ids'], receipt)
        dynamodb_resource.Table(SETTINGS_TABLE).delete_item(
            Key = {OWNER_KEY: owner, SETTING_SORT_KEY: row[SETTING_SORT_KEY]}
        )
    return receipt


def _send_batch(
    dynamodb_resource: ServiceResource,
    owner: str,
    context: tuple[Emitter, SiatCodesOut, dict[str, Any]],
    batch: list[dict[str, Any]]
) -> PackageReceipt:
    '''
        Sends one package and settles it, or leaves it for the next run.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            context (tuple[Emitter, SiatCodesOut, dict[str, Any]]): Who issues,
                the codes in force and the contingency.
            batch (list[dict[str, Any]]): The sales of this package, in order.

        Returns:
            PackageReceipt: What the SIN answered last.
    '''
    emitter, codes, record = context
    received = packages.send_package(emitter, packages.PackageSubmission(
        cuis = codes.cuis, cufd = codes.cufd,
        event_reception_code = int(record['event_reception_code']),
        invoices = [(f'{sale["invoice"]["number"]}.xml', sale['invoice_xml']) for sale in batch],
        sent_at = siat_stamp(get_current_time_gmt())
    ))
    if not received.reception_code:
        error_msg = f'SIAT refused a package of {owner}: {received.messages or "no messages"}'
        logger.error(error_msg)
        return received

    sale_ids = [sale[SALE_SORT_KEY] for sale in batch]
    receipt = packages.validate_package(emitter, (codes.cuis, codes.cufd), received.reception_code)
    if receipt.state == STATE_PENDING:
        write_item(dynamodb_resource, SETTINGS_TABLE, {
            OWNER_KEY: owner, SETTING_SORT_KEY: f'{PACKAGE_PREFIX}{received.reception_code}',
            'reception_code': received.reception_code, 'sale_ids': sale_ids
        })
    else:
        _mark_batch(dynamodb_resource, owner, sale_ids, receipt)
    return receipt


def _mark_batch(
    dynamodb_resource: ServiceResource,
    owner: str,
    sale_ids: list[str],
    receipt: PackageReceipt
) -> None:
    '''
        Stores on each sale of a settled package what the SIN said of it.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            sale_ids (list[str]): The sales, in the order they went in the package.
            receipt (PackageReceipt): The SIN's validation.
    '''
    table = dynamodb_resource.Table(SALES_TABLE)
    for position, sale_id in enumerate(sale_ids):
        sale = from_dynamo(table.get_item(Key = {OWNER_KEY: owner,
                                                 SALE_SORT_KEY: sale_id}).get('Item'))
        if not sale:
            continue
        observations = receipt.observed.get(position, [])
        # A validated package (908) can still carry warnings — an offline NIT
        # the SIN could not find, for one: the invoice is valid and the
        # warning is kept. Only an observed package (904) leaves invoices out.
        rejected = receipt.state == STATE_OBSERVED and observations
        sale['invoice'].update(
            state = (InvoiceState.OBSERVED if rejected else InvoiceState.ACCEPTED).value,
            package_reception_code = receipt.reception_code,
            siat_state = receipt.state, observations = observations
        )
        write_item(dynamodb_resource, SALES_TABLE, sale)


def _settle_uncertain(
    emitter: Emitter,
    codes: SiatCodesOut,
    record: dict[str, Any]
) -> int:
    '''
        Cancels the online sendings the SIN did register although no answer
        came back: their offline twins are the invoices the buyers hold.

        Args:
            emitter (Emitter): Who issued them.
            codes (SiatCodesOut): The codes in force.
            record (dict[str, Any]): The contingency.

        Returns:
            int: How many had to be cancelled.
    '''
    cancelled = 0
    for cuf in record.get('uncertain_cufs', []):
        if packages.invoice_state(emitter, (codes.cuis, codes.cufd), cuf) == STATE_VALID:
            siat_client.cancel_invoice(emitter, InvoiceCancellation(
                cuis = codes.cuis, cufd = codes.cufd, cuf = cuf, reason_code = DUPLICATE_REASON
            ))
            cancelled += 1
    return cancelled


def _offline_sales(
    dynamodb_resource: ServiceResource,
    owner: str,
    record: dict[str, Any]
) -> list[dict[str, Any]]:
    '''
        The sales issued offline in this contingency, by invoice number.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            record (dict[str, Any]): The contingency.

        Returns:
            list[dict[str, Any]]: The sale items.
    '''
    since = record['started_at'][:10]
    rows = read_partition(dynamodb_resource, SALES_TABLE, owner, bounds = SortBounds(
        sort_key = SALE_SORT_KEY, between = date_window(since, None)
    ))
    offline = [row for row in rows if (row.get('invoice') or {}).get('state') ==
               InvoiceState.OFFLINE.value and row['invoice'].get('cufd') == record['cufd']]
    # By invoice number, not by sale identifier: two sales of the same instant
    # sort by the random half of their identifier, and a package goes in the
    # order the invoices were numbered.
    return sorted(offline, key = lambda row: int(row['invoice']['number']))


def _event_description(
    dynamodb_resource: ServiceResource,
    owner: str,
    event: int
) -> str:
    '''
        The event's description, as the SIN's own catalogue writes it.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            event (int): The event code.

        Returns:
            str: The description.

        Raises:
            RegisterNotFoundError: The catalogue lacks the event.
    '''
    for entry in get_catalog(dynamodb_resource, owner, SiatCatalog.SIGNIFICANT_EVENTS).entries:
        if entry.code == str(event):
            return entry.description
    raise RegisterNotFoundError(detail = BillingError.CATALOG_NOT_SYNCED.value)


def _scan_prefix(
    dynamodb_resource: ServiceResource,
    prefix: str
) -> list[dict[str, Any]]:
    '''
        Every settings row of every shop whose key starts with a prefix.

        A scan, on purpose: it runs from the scheduler and not per request,
        the settings table holds a handful of rows per shop, and the rows it
        looks for exist only while a shop is offline.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            prefix (str): Start of the setting key.

        Returns:
            list[dict[str, Any]]: The rows.
    '''
    table = dynamodb_resource.Table(SETTINGS_TABLE)
    request: dict[str, Any] = {'FilterExpression': Attr(SETTING_SORT_KEY).begins_with(prefix)}
    rows: list[dict[str, Any]] = []
    while True:
        page = table.scan(**request)
        rows.extend(from_dynamo(page.get('Items', [])))
        if 'LastEvaluatedKey' not in page:
            return rows
        request['ExclusiveStartKey'] = page['LastEvaluatedKey']
