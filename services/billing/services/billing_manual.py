'''
    Manual contingency invoices: the CAFCs a shop holds, the contingencies it
    issued on paper, the transcription of each paper invoice and the sending
    to the SIN.

    A transcribed invoice is a sale like any other — it takes its units out
    of the shelf and the buyer goes into the customer master — except that it
    takes no till, since its cash was counted when the till closed (a
    difference is explained in the closing note, Rafael, 30-oct-2026), and
    that it charges what the paper says. Its invoice carries the paper's
    number and moment, the CAFC, and the CUFD in force when the contingency
    began.

    Sending follows the SIN's order for paper invoices (its page on manual
    contingency invoices, `docs/siat/SIAT.md`): a new CUFD, the event — one
    per CAFC —, then the packages with the CAFC, all within 72 hours. The
    packages go through the same path as an automatic contingency's.

    Stored in `billing_settings`:

    | setting_key              | What                                       |
    |--------------------------|--------------------------------------------|
    | siat#cafc#<cafc>         | A CAFC, its range and the numbers used     |
    | siat#manual#<id>         | A manual contingency and its transcriptions|
'''
from datetime import datetime
from typing import Any

from boto3.dynamodb.conditions import Key
from boto3.resources.base import ServiceResource

from models.billing import OWNER_KEY, SALES_TABLE, SALE_SORT_KEY, SETTINGS_TABLE, SETTING_SORT_KEY
from schemas.billing import SaleLineIn, SaleNoteIn, SaleNoteOut
from schemas.billing_manual import (
    CafcIn,
    CafcOut,
    CafcsResponse,
    ManualContingenciesResponse,
    ManualContingencyIn,
    ManualContingencyOut,
    ManualContingencyStatus,
    ManualError,
    ManualInvoiceIn
)
from schemas.billing_siat import RecoveryOut, SiatCodesOut
from services import billing_siat_packages as packages
from services.billing import document_id, from_dynamo, get_settings, now_iso, write_item
from services.billing_contingency import register_event_once, send_batch
from services.billing_invoicing import CONTINGENCY_CODES, ManualIssue
from services.billing_sales import PaperSale, issue_sale
from services.billing_siat import siat_stamp
from services.billing_siat_codes import codes_at, emitter_for
from services.exceptions import (
    InvalidInputError,
    RegisterAlreadyExistsError,
    RegisterNotFoundError
)
from services.logger_config import custom_logger as logger
from services.utils import get_current_time_gmt

CAFC_PREFIX = 'siat#cafc#'
MANUAL_PREFIX = 'siat#manual#'


def register_cafc(
    dynamodb_resource: ServiceResource,
    owner: str,
    cafc: CafcIn
) -> CafcOut:
    '''
        Keeps a CAFC the SIN authorized, with its range of numbers.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            cafc (CafcIn): The code and its range.

        Returns:
            CafcOut: The CAFC, with no number used yet.

        Raises:
            RegisterAlreadyExistsError: The CAFC is already registered.
    '''
    if _cafc_record(dynamodb_resource, owner, cafc.cafc):
        raise RegisterAlreadyExistsError(detail = ManualError.CAFC_ALREADY_REGISTERED.value)
    record = {OWNER_KEY: owner, SETTING_SORT_KEY: f'{CAFC_PREFIX}{cafc.cafc}',
              **cafc.model_dump(), 'used_numbers': [], 'registered_at': now_iso()}
    write_item(dynamodb_resource, SETTINGS_TABLE, record)
    return CafcOut(**record)


def list_cafcs(
    dynamodb_resource: ServiceResource,
    owner: str
) -> CafcsResponse:
    '''
        The shop's CAFCs.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.

        Returns:
            CafcsResponse: Every CAFC, with the numbers used.
    '''
    return CafcsResponse(items = [CafcOut(**row) for row in
                                  _settings_with_prefix(dynamodb_resource, owner, CAFC_PREFIX)])


def open_manual_contingency(
    dynamodb_resource: ServiceResource,
    owner: str,
    contingency: ManualContingencyIn,
    created_by: str
) -> ManualContingencyOut:
    '''
        Opens a contingency during which the shop issued paper invoices, with
        the codes in force when it began.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            contingency (ManualContingencyIn): Its CAFC, event and window.
            created_by (str): Who opens it.

        Returns:
            ManualContingencyOut: The contingency, ready for transcriptions.

        Raises:
            RegisterNotFoundError: The CAFC is not registered.
            InvalidInputError: CUFD_NOT_KEPT, no CUFD kept covers its start.
    '''
    if not _cafc_record(dynamodb_resource, owner, contingency.cafc):
        raise RegisterNotFoundError(detail = ManualError.CAFC_NOT_FOUND.value)
    started = _local(contingency.started_at)
    codes = codes_at(dynamodb_resource, owner, started.isoformat())
    if codes is None:
        raise InvalidInputError(detail = ManualError.CUFD_NOT_KEPT.value)
    record = {
        OWNER_KEY: owner, SETTING_SORT_KEY: f'{MANUAL_PREFIX}{document_id()}',
        'cafc': contingency.cafc, 'event': int(contingency.event),
        'started_at': siat_stamp(started), 'ended_at': siat_stamp(_local(contingency.ended_at)),
        'status': ManualContingencyStatus.OPEN.value, 'sale_ids': [],
        'created_by': created_by, 'created_at': now_iso(),
        **codes.model_dump(include = set(CONTINGENCY_CODES))
    }
    write_item(dynamodb_resource, SETTINGS_TABLE, record)
    message = f'{owner}: {created_by} opened a manual contingency with CAFC {contingency.cafc}.'
    logger.info(message)
    return _contingency_out(record)


def list_manual_contingencies(
    dynamodb_resource: ServiceResource,
    owner: str
) -> ManualContingenciesResponse:
    '''
        The shop's manual contingencies, newest first.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.

        Returns:
            ManualContingenciesResponse: Every one, open or sent.
    '''
    rows = _settings_with_prefix(dynamodb_resource, owner, MANUAL_PREFIX)
    return ManualContingenciesResponse(items = [_contingency_out(row) for row in reversed(rows)])


def transcribe_invoice(
    dynamodb_resource: ServiceResource,
    owner: str,
    contingency_id: str,
    paper: ManualInvoiceIn,
    created_by: str
) -> SaleNoteOut:
    '''
        Transcribes one paper invoice into its contingency: a sale whose
        invoice waits offline for the sending.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            contingency_id (str): The manual contingency.
            paper (ManualInvoiceIn): What the paper invoice says.
            created_by (str): Who transcribes it.

        Returns:
            SaleNoteOut: The sale, with its invoice offline.

        Raises:
            RegisterNotFoundError: No such contingency or CAFC.
            InvalidInputError: The contingency was sent, the shop does not
                invoice, the number is outside the CAFC or already
                transcribed, the moment falls outside the event, or any
                refusal of a sale.
    '''
    record = _open_contingency(dynamodb_resource, owner, contingency_id)
    if not get_settings(dynamodb_resource, owner).invoicing_enabled:
        raise InvalidInputError(detail = ManualError.INVOICING_DISABLED.value)
    cafc = _cafc_record(dynamodb_resource, owner, record['cafc'])
    if cafc is None:
        raise RegisterNotFoundError(detail = ManualError.CAFC_NOT_FOUND.value)
    if not cafc['first_number'] <= paper.number <= cafc['last_number']:
        raise InvalidInputError(detail = ManualError.NUMBER_OUTSIDE_CAFC.value)
    if paper.number in cafc['used_numbers']:
        raise InvalidInputError(detail = ManualError.NUMBER_ALREADY_TRANSCRIBED.value)
    issued = _local(paper.issued_at)
    if not _stamped(record['started_at']) <= issued <= _stamped(record['ended_at']):
        raise InvalidInputError(detail = ManualError.ISSUED_OUTSIDE_EVENT.value)

    note = SaleNoteIn(buyer = paper.buyer, payment_method = paper.payment_method,
                      payments = paper.payments, card_number = paper.card_number,
                      lines = [SaleLineIn(sku = line.sku, quantity = line.quantity)
                               for line in paper.lines])
    sale = issue_sale(dynamodb_resource, owner, note, created_by, PaperSale(
        issue = ManualIssue(number = paper.number, issued_at = issued, cafc = record['cafc']),
        codes = _contingency_codes(dynamodb_resource, owner, record),
        prices = {line.sku: line.unit_price for line in paper.lines}
    ))
    cafc['used_numbers'] = sorted([*cafc['used_numbers'], paper.number])
    write_item(dynamodb_resource, SETTINGS_TABLE, cafc)
    record['sale_ids'].append(sale.sale_id)
    write_item(dynamodb_resource, SETTINGS_TABLE, record)
    return sale


def send_manual_contingency(
    dynamodb_resource: ServiceResource,
    owner: str,
    contingency_id: str
) -> RecoveryOut:
    '''
        Sends the transcribed invoices of a manual contingency to the SIN:
        a new CUFD, the event with the CUFD of the contingency, and the
        packages with the CAFC.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            contingency_id (str): The manual contingency.

        Returns:
            RecoveryOut: What was sent; `recovered` False while the SIN is away.

        Raises:
            RegisterNotFoundError: No such contingency.
            InvalidInputError: It was sent already, it has nothing to send, or
                the SIN refused the event.
            ServiceUnavailableError: The SIN went away halfway.
    '''
    record = _open_contingency(dynamodb_resource, owner, contingency_id)
    if not record['sale_ids']:
        raise InvalidInputError(detail = ManualError.NOTHING_TO_SEND.value)
    if not packages.verify_communication():
        return RecoveryOut(recovered = False)

    emitter = emitter_for(dynamodb_resource, owner)
    codes = register_event_once(dynamodb_resource, owner, record, record['ended_at'])

    sales = _sales_by_number(dynamodb_resource, owner, record['sale_ids'])
    receipts = [send_batch(dynamodb_resource, owner, (emitter, codes, record),
                           sales[start:start + packages.MAX_PACKAGE_INVOICES])
                for start in range(0, len(sales), packages.MAX_PACKAGE_INVOICES)]
    record['status'] = ManualContingencyStatus.SENT.value
    write_item(dynamodb_resource, SETTINGS_TABLE, record)

    message = (f'{owner} sent manual contingency {contingency_id}: event '
               f'{record["event_reception_code"]}, {len(sales)} invoice(s).')
    logger.info(message)
    return RecoveryOut(recovered = True, event_reception_code = record['event_reception_code'],
                       packages = receipts, invoices_sent = len(sales),
                       invoices_observed = sum(len(receipt.observed) for receipt in receipts))


def _open_contingency(
    dynamodb_resource: ServiceResource,
    owner: str,
    contingency_id: str
) -> dict[str, Any]:
    '''
        A manual contingency still taking transcriptions.

        Raises:
            RegisterNotFoundError: No such contingency in this shop.
            InvalidInputError: It was sent already.
    '''
    record = from_dynamo(dynamodb_resource.Table(SETTINGS_TABLE).get_item(
        Key = {OWNER_KEY: owner, SETTING_SORT_KEY: f'{MANUAL_PREFIX}{contingency_id}'}
    ).get('Item'))
    if not record:
        raise RegisterNotFoundError(detail = ManualError.MANUAL_CONTINGENCY_NOT_FOUND.value)
    if record['status'] != ManualContingencyStatus.OPEN.value:
        raise InvalidInputError(detail = ManualError.MANUAL_CONTINGENCY_SENT.value)
    return record


def _contingency_codes(
    dynamodb_resource: ServiceResource,
    owner: str,
    record: dict[str, Any]
) -> SiatCodesOut:
    '''
        The codes a manual contingency kept, for the shop's point of sale.
    '''
    emitter = emitter_for(dynamodb_resource, owner)
    return SiatCodesOut(branch = emitter.branch, point_of_sale = emitter.point_of_sale or 0,
                        **{field: record[field] for field in CONTINGENCY_CODES})


def _cafc_record(
    dynamodb_resource: ServiceResource,
    owner: str,
    cafc: str
) -> dict[str, Any] | None:
    '''
        A stored CAFC, or None.
    '''
    return from_dynamo(dynamodb_resource.Table(SETTINGS_TABLE).get_item(
        Key = {OWNER_KEY: owner, SETTING_SORT_KEY: f'{CAFC_PREFIX}{cafc}'}
    ).get('Item'))


def _settings_with_prefix(
    dynamodb_resource: ServiceResource,
    owner: str,
    prefix: str
) -> list[dict[str, Any]]:
    '''
        The shop's settings rows under one prefix, in key order.
    '''
    table = dynamodb_resource.Table(SETTINGS_TABLE)
    condition = Key(OWNER_KEY).eq(owner) & Key(SETTING_SORT_KEY).begins_with(prefix)
    request: dict[str, Any] = {'KeyConditionExpression': condition}
    rows: list[dict[str, Any]] = []
    while True:
        page = table.query(**request)
        rows.extend(from_dynamo(page.get('Items', [])))
        if 'LastEvaluatedKey' not in page:
            return rows
        request['ExclusiveStartKey'] = page['LastEvaluatedKey']


def _sales_by_number(
    dynamodb_resource: ServiceResource,
    owner: str,
    sale_ids: list[str]
) -> list[dict[str, Any]]:
    '''
        The transcribed sales, by invoice number: a package goes in the order
        the paper invoices were numbered.
    '''
    table = dynamodb_resource.Table(SALES_TABLE)
    sales = [from_dynamo(table.get_item(Key = {OWNER_KEY: owner, SALE_SORT_KEY: sale_id}
                                        ).get('Item')) for sale_id in sale_ids]
    return sorted((sale for sale in sales if sale),
                  key = lambda sale: int(sale['invoice']['number']))


def _contingency_out(record: dict[str, Any]) -> ManualContingencyOut:
    '''
        A stored manual contingency as the DTO.
    '''
    return ManualContingencyOut(contingency_id = record[SETTING_SORT_KEY][len(MANUAL_PREFIX):],
                                **{field: record.get(field) for field in (
                                    'cafc', 'event', 'started_at', 'ended_at', 'cufd', 'status',
                                    'sale_ids', 'event_reception_code', 'created_by',
                                    'created_at')})


def _local(moment: datetime) -> datetime:
    '''
        A moment in the service's zone, the one every SIAT stamp is written in.
    '''
    zone = get_current_time_gmt().tzinfo
    return (moment.replace(tzinfo = zone) if moment.tzinfo is None
            else moment.astimezone(zone))


def _stamped(stamp: str) -> datetime:
    '''
        A SIAT stamp, which carries no zone, as a moment in the service's zone.
    '''
    return _local(datetime.fromisoformat(stamp))
