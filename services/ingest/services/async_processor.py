'''
    Asynchronous processing for large-file ingestion.

    A large sales export (100k+ rows) takes minutes to read, validate and
    normalize — far beyond the API Gateway 29 s synchronous limit. So the HTTP
    endpoint only records a 'processing' dataset and dispatches the heavy work
    here; the client then polls `GET /v1/ingest/{dataset_id}` for the outcome.

    Dispatch mechanism: in AWS the Lambda self-invokes asynchronously
    (InvocationType='Event'); in local dev (uvicorn) there is no function to
    invoke, so the work runs inline. Errors are always captured onto the dataset
    record so a polling client never hangs.
'''
import json
import os
import uuid
from typing import Any, Dict

import boto3

from services.datasets import update_dataset_result
from services.db_connection import dynamodb_resource
from services.excel_parser import parse_and_validate_partial, serialize_dataframe
from services.exceptions import ServiceUnavailableError
from services.logger_config import custom_logger as logger
from services.s3_storage import download_bytes, upload_bytes

# Only a slice of the rejected rows is kept on the DynamoDB record (400 KB item
# limit); the full set lives in the rejected CSV in S3.
_MAX_ERRORS_ON_RECORD = 100

_CSV_CONTENT_TYPE = 'text/csv'
_lambda_client = boto3.client('lambda')


def dispatch_processing(job: Dict[str, Any]) -> None:
    '''
        Fires the background processing job. In Lambda it self-invokes
        asynchronously so the HTTP request returns immediately; locally it runs
        inline (there is no Lambda to invoke).

        Args:
            job (Dict[str, Any]): dataset_id, file_key, file_name, owner_email.
    '''
    function_name = os.getenv('AWS_LAMBDA_FUNCTION_NAME')
    if not function_name:
        process_dataset(job)
        return
    _lambda_client.invoke(
        FunctionName = function_name,
        InvocationType = 'Event',
        Payload = json.dumps({'ingest_async': job}).encode('utf-8')
    )
    message = f'Dispatched async ingest for dataset {job["dataset_id"]}.'
    logger.info(message)


def process_dataset(job: Dict[str, Any]) -> None:
    '''
        Downloads the raw file from S3, validates + normalizes it, stores the
        normalized dataset (CSV, fast to write/read) back in S3 and records the
        outcome on the dataset. Any failure is captured onto the record so the
        polling client always gets a terminal status.

        Args:
            job (Dict[str, Any]): dataset_id, file_key, file_name, owner_email.
    '''
    dataset_id = job['dataset_id']
    try:
        file_bytes = download_bytes(job['file_key'])
        valid_df, rejected_df, errors, summary = parse_and_validate_partial(
            file_bytes, job['file_name']
        )
        has_valid_rows = len(valid_df) > 0

        # Accepted rows → normalized CSV (feeds analytics/forecast/routes).
        normalized_key = None
        if has_valid_rows:
            normalized_key = upload_bytes(
                file_key = f'ingest/normalized/{uuid.uuid4().hex}.csv',
                data = serialize_dataframe(valid_df, 'normalized.csv'),
                content_type = _CSV_CONTENT_TYPE
            )
        # Rejected rows → separate CSV the client can fix and re-upload.
        rejected_key = None
        if len(rejected_df) > 0:
            rejected_key = upload_bytes(
                file_key = f'ingest/rejected/{uuid.uuid4().hex}.csv',
                data = serialize_dataframe(rejected_df, 'rejected.csv'),
                content_type = _CSV_CONTENT_TYPE
            )
        update_dataset_result(dynamodb_resource, dataset_id, {
            'status': 'validated' if has_valid_rows else 'failed',
            'file_s3_key': normalized_key,
            'rejected_s3_key': rejected_key,
            **summary,
            'errors': errors[:_MAX_ERRORS_ON_RECORD]
        })
    except ServiceUnavailableError as error:
        logger.error(f'Async ingest {dataset_id} storage failure: {error.detail}')
        _mark_failed(dataset_id, 'No se pudo leer o guardar el archivo en el almacenamiento.')
    except Exception as error: # pylint: disable=broad-exception-caught
        # Last-resort guard: an unhandled error must still land on the record,
        # otherwise the client polls forever.
        logger.error(f'Async ingest {dataset_id} unexpected error: {error}', exc_info = True)
        _mark_failed(dataset_id, 'Ocurrió un error inesperado al procesar el archivo.')


def _mark_failed(dataset_id: str, message: str) -> None:
    '''Records a processing failure so the polling client stops and shows it.'''
    update_dataset_result(dynamodb_resource, dataset_id, {
        'status': 'failed',
        'file_s3_key': None,
        'errors': [{
            'row': 0, 'column': '(archivo)', 'value': None,
            'rule': 'processing_error', 'message': message
        }]
    })
