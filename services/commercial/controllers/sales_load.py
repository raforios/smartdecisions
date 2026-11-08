'''
    The sales of a dataset, loaded line by line: the ERP's push, SmartBilling's
    live sales and what a cancellation or a return leaves of a sale.

    Every door lands on the same merge and the same store: the stored lines are
    put through the contract, the new ones land on top keyed by invoice and
    product, and the file they replace is retired.
'''
from dataclasses import replace
from typing import Any

import pandas as pd
from boto3.resources.base import ServiceResource

from controllers.common import (
    store_new_or_known,
    API_ORIGIN,
    MAX_ISSUES_ON_RESPONSE,
    native_numbers,
    retire_replaced_file,
    rows_frame,
    store_frame,
    to_ingest_response,
    with_known_masters
)
from schemas.channels import LoadMode, SaleRowSchema, SalesPushSchema, SalesRowsSchema
from schemas.clients import ClientSource
from schemas.commercial import IngestResponse
from services.commercial import prepare_rows as prepare_sales_rows
from services.commercial import validate_rows_partial
from services.commercial_utils import (
    attach_to_dataset,
    get_owned_dataset,
    read_stored_frame
)
from services.logger_config import custom_logger as logger
from services.modules import sales_profile

# A sales line IS its invoice and its product: one line per product per
# invoice. That is what lets an ERP push the same day twice —a retry, or a
# correction to one line— without the invoice ending up counted twice.
SALES_MERGE_KEYS: tuple[str, ...] = ('order_id', 'product_id')


def merge_sales(
    dataset: dict[str, Any],
    accepted: Any,
    auth_token: str,
    cleared_orders: frozenset[str] = frozenset()
) -> Any:
    '''
        Lands pushed sales lines on top of the ones the dataset already holds.

        The stored rows are put through the same contract before comparing,
        because they come back from CSV as text and a date that is a Timestamp
        on one side and a string on the other never matches.

        Args:
            dataset (dict[str, Any]): The dataset item.
            accepted (pd.DataFrame): The lines just accepted.
            auth_token (str): The caller's Authorization header, forwarded to FILES.
            cleared_orders (frozenset[str]): Orders whose stored lines all go
                before the new ones land: what a cancellation or a return
                leaves of a sale replaces the whole sale.

        Returns:
            pd.DataFrame: Stored lines and new lines, deduplicated.
    '''
    stored_key = dataset.get('file_s3_key')
    if not stored_key:
        return accepted
    previous = read_stored_frame(str(stored_key), auth_token)
    if previous.empty:
        return accepted
    aligned = validate_rows_partial(previous, API_ORIGIN).accepted
    if cleared_orders and 'order_id' in aligned.columns:
        aligned = aligned[~aligned['order_id'].astype(str).isin(cleared_orders)]
    merged = pd.concat([aligned, accepted], ignore_index = True)
    keys = [key for key in SALES_MERGE_KEYS if key in merged.columns]
    if keys:
        merged = merged.drop_duplicates(subset = keys, keep = 'last')
    message = (f'Sales merge: {len(aligned)} stored + {len(accepted)} pushed = '
               f'{len(merged)} line(s).')
    logger.info(message)
    return merged.reset_index(drop = True)


def _store_sales(
    dynamodb_resource: ServiceResource,
    dataset: dict[str, Any],
    whole: Any,
    issues: list,
    auth_token: str
) -> dict[str, Any]:
    '''
        Stores a dataset's sales as they now stand and retires the file they
        replace.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            dataset (dict[str, Any]): The dataset item, as it was read.
            whole (Any): The validation of every line the dataset now holds.
            issues (list): The issues of the lines just received.
            auth_token (str): The caller's Authorization header, forwarded to FILES.

        Returns:
            dict[str, Any]: The dataset as stored.
    '''
    dataset_id = str(dataset['dataset_id'])
    replaced_key = dataset.get('file_s3_key')
    file_key = store_frame(whole.accepted, 'normalized', auth_token)
    stored = attach_to_dataset(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        payload = {
            'file_s3_key': file_key,
            'status': 'validated' if len(whole.accepted) else 'failed',
            'sales_profile': sales_profile(whole.accepted).model_dump(),
            **whole.summary.model_dump(),
            'issues': [
                issue.model_dump(mode = 'json')
                for issue in issues[:MAX_ISSUES_ON_RESPONSE]
            ]
        }
    )
    retire_replaced_file(replaced_key, auth_token)
    return stored


async def push_sales(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    push: SalesPushSchema,
    current_user: str,
    auth_token: str
) -> IngestResponse:
    '''
        Sales lines into an owned dataset, shared by the push door and the live
        door so each is reported and audited once, by its own controller.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            dataset_id (str): Dataset the lines belong to.
            push (SalesPushSchema): Mode and rows.
            current_user (str): Authenticated caller and owner of the dataset.
            auth_token (str): The caller's Authorization header, forwarded to FILES.

        Returns:
            IngestResponse: The dataset as it now stands.
    '''
    dataset = get_owned_dataset(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        owner_email = current_user
    )
    result = validate_rows_partial(prepare_sales_rows(rows_frame(push.rows)), API_ORIGIN)
    result = with_known_masters(dynamodb_resource, current_user, result, ClientSource.API)

    whole = result
    if push.mode is LoadMode.APPEND:
        merged = merge_sales(dataset, result.accepted, auth_token)
        if len(merged) != len(result.accepted):
            whole = replace(validate_rows_partial(merged, API_ORIGIN),
                            issues = result.issues)

    stored = _store_sales(dynamodb_resource, dataset, whole, result.issues, auth_token)
    message = (f'Dataset {dataset_id} received {len(push.rows)} pushed line(s) '
               f'({push.mode.value}); {whole.summary.valid_rows} stored.')
    logger.info(message)
    return to_ingest_response(native_numbers(stored))


async def create_sales_dataset(
    dynamodb_resource: ServiceResource,
    rows: SalesRowsSchema,
    current_user: str,
    auth_token: str
) -> IngestResponse:
    '''
        A new dataset from posted lines, shared by the create door and the live
        door so each is reported and audited once, by its own controller.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            rows (SalesRowsSchema): The lines.
            current_user (str): Authenticated caller, owner of the dataset.
            auth_token (str): The caller's Authorization header, forwarded to FILES.

        Returns:
            IngestResponse: The new dataset, or the one that already held
                these lines.
    '''
    response, _ = store_new_or_known(
        dynamodb_resource, (current_user, auth_token), prepare_sales_rows(rows_frame(rows.rows)),
        lambda frame: validate_rows_partial(frame, API_ORIGIN), ClientSource.API
    )
    return response


def replace_order_lines(
    dynamodb_resource: ServiceResource,
    dataset: dict[str, Any],
    order_id: str,
    rows: list[SaleRowSchema],
    auth_token: str
) -> dict[str, Any]:
    '''
        Leaves a sale in the dataset as it stands after a cancellation or a
        return: its stored lines go and `rows` —what the buyer kept, nothing
        when it was cancelled— take their place, through the same contract
        and the same client master as any pushed line.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            dataset (dict[str, Any]): The owned dataset that holds the sale.
            order_id (str): The sale.
            rows (list[SaleRowSchema]): Its lines now; empty when cancelled.
            auth_token (str): The caller's Authorization header, forwarded to FILES.

        Returns:
            dict[str, Any]: The dataset as stored.
    '''
    owner = str(dataset['owner_email'])
    kept = validate_rows_partial(prepare_sales_rows(rows_frame(rows)), API_ORIGIN)
    if rows:
        kept = with_known_masters(dynamodb_resource, owner, kept, ClientSource.API)
    merged = merge_sales(dataset, kept.accepted, auth_token, frozenset({order_id}))
    whole = replace(validate_rows_partial(merged, API_ORIGIN), issues = kept.issues)
    stored = _store_sales(dynamodb_resource, dataset, whole, kept.issues, auth_token)
    message = (f'Sale {order_id} of dataset {dataset["dataset_id"]} now holds '
               f'{len(kept.accepted)} line(s); {whole.summary.valid_rows} stored.')
    logger.info(message)
    return stored
