'''
    Ingest controllers.
'''
from pathlib import Path
from typing import Any, Dict, Optional
from boto3.resources.base import ServiceResource
from fastapi import Request

from schemas.ingest import (
    IngestColumnError,
    IngestResponse,
    IngestStatusResponse,
    IngestSummary,
    TemplateInfo
)
from services.async_processor import dispatch_processing
from services.datasets import get_dataset_by_id, persist_dataset
from services.excel_parser import parse_and_validate, serialize_dataframe
from services.excel_validator import OPTIONAL_COLUMNS, REQUIRED_COLUMNS, TEMPLATE_VERSION
from services.exceptions import ResourceNotFoundError
from services.file_storage import upload_excel
from services.s3_storage import download_bytes
from services.template_builder import ensure_template
from services.utils import handle_service_errors


def _to_response(item: Dict[str, Any]) -> IngestResponse:
    '''
        Maps a persisted DynamoDB item into the public IngestResponse schema.
    '''
    return IngestResponse(
        dataset_id = item['dataset_id'],
        status = item['status'],
        file_s3_key = item.get('file_s3_key') or '',
        summary = IngestSummary(
            total_rows = item.get('total_rows', 0),
            valid_rows = item.get('valid_rows', 0),
            error_rows = item.get('error_rows', 0),
            unique_points_of_sale = item.get('unique_points_of_sale', 0),
            unique_products = item.get('unique_products', 0),
            date_range_start = item.get('date_range_start'),
            date_range_end = item.get('date_range_end')
        ),
        errors = [IngestColumnError(**err) for err in item.get('errors', [])],
        created_at = item['created_at']
    )


# pylint: disable=too-many-arguments, too-many-positional-arguments
@handle_service_errors('INGEST')
async def ingest_excel_controller(
    dynamodb_resource: ServiceResource,
    file_bytes: bytes,
    filename: str,
    bearer_token: str,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> IngestResponse:
    '''
        Controller orchestrating the full ingest flow:
            1. Parse + validate the uploaded file.
            2. If valid: upload to S3 via FILES; otherwise skip the upload.
            3. Persist the dataset metadata in DynamoDB.
            4. Return the public response.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            file_bytes (bytes): Raw content of the uploaded file.
            filename (str): Original filename.
            bearer_token (str): JWT used to call FILES on behalf of the user.
            current_user (str): Authenticated user email (owner of the dataset).

        Returns:
            IngestResponse: Public payload with summary + per-row errors.
    '''
    validated, errors, summary = parse_and_validate(file_bytes, filename)
    is_valid = not errors

    file_s3_key: Optional[str] = None
    if is_valid:
        # Store the NORMALIZED dataframe (canonical columns, ids filled) so every
        # downstream service reads a clean, uniform dataset without re-mapping.
        file_s3_key = upload_excel(
            file_bytes = serialize_dataframe(validated, filename),
            filename = filename,
            bearer_token = bearer_token
        )

    persisted = persist_dataset(
        dynamodb_resource = dynamodb_resource,
        payload = {
            'owner_email': current_user,
            'status': 'validated' if is_valid else 'failed',
            'file_s3_key': file_s3_key,
            'template_version': TEMPLATE_VERSION,
            **summary,
            'errors': errors
        }
    )
    return _to_response(persisted)


@handle_service_errors('INGEST')
async def ingest_excel_from_s3_controller(
    dynamodb_resource: ServiceResource,
    file_key: str,
    file_name: str,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> Dict[str, str]:
    '''
        Accepts a large file already uploaded to S3 for ASYNC processing:
            1. Record a 'processing' dataset immediately.
            2. Dispatch the heavy download/validate/normalize work in the
               background (self-invoked Lambda in AWS, inline in local dev).
            3. Return the dataset id so the client can poll
               `GET /v1/ingest/{dataset_id}` until it is validated/failed.

        This keeps the HTTP request well under the API Gateway 29 s timeout for
        files that take minutes to process.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            file_key (str): S3 key of the raw uploaded file.
            file_name (str): Original filename (drives format detection).
            current_user (str): Authenticated user email (dataset owner).

        Returns:
            Dict[str, str]: The new dataset_id and its 'processing' status.
    '''
    persisted = persist_dataset(
        dynamodb_resource = dynamodb_resource,
        payload = {
            'owner_email': current_user,
            'status': 'processing',
            'file_s3_key': None,
            'template_version': TEMPLATE_VERSION
        }
    )
    dispatch_processing({
        'dataset_id': persisted['dataset_id'],
        'file_key': file_key,
        'file_name': file_name,
        'owner_email': current_user
    })
    return {'dataset_id': persisted['dataset_id'], 'status': 'processing'}


@handle_service_errors('INGEST', with_log = False)
async def download_rejected_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> bytes:
    '''
        Returns the CSV of rows that could not be loaded (with a 'motivo'
        column), so the client can fix them and re-upload.

        Raises:
            ResourceNotFoundError: If the dataset has no rejected-rows file.
    '''
    item = get_dataset_by_id(dynamodb_resource = dynamodb_resource, dataset_id = dataset_id)
    rejected_key = item.get('rejected_s3_key')
    if not rejected_key:
        raise ResourceNotFoundError(
            detail = 'Este dataset no tiene filas rechazadas para descargar.'
        )
    return download_bytes(rejected_key)


@handle_service_errors('INGEST')
async def get_dataset_status_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> IngestStatusResponse:
    '''
        Controller to retrieve the status of a previously ingested dataset.
    '''
    item = get_dataset_by_id(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id
    )
    return IngestStatusResponse(
        dataset_id = item['dataset_id'],
        status = item['status'],
        owner_email = item['owner_email'],
        file_s3_key = item.get('file_s3_key') or '',
        summary = IngestSummary(
            total_rows = item.get('total_rows', 0),
            valid_rows = item.get('valid_rows', 0),
            error_rows = item.get('error_rows', 0),
            unique_points_of_sale = item.get('unique_points_of_sale', 0),
            unique_products = item.get('unique_products', 0),
            date_range_start = item.get('date_range_start'),
            date_range_end = item.get('date_range_end')
        ),
        errors = [IngestColumnError(**err) for err in item.get('errors', [])],
        created_at = item['created_at']
    )


@handle_service_errors('INGEST', with_log = False)
async def download_template_controller(
    base_path: Path, # pylint: disable=unused-argument
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> Path:
    '''
        Returns the path to the downloadable template so the route can stream
        it, generating it on demand in the writable temp dir (the Lambda package
        is read-only). Decorated with `with_log = False`: the event is still
        shipped to EVENTS, but the binary file body is not logged.
    '''
    return ensure_template()


@handle_service_errors('INGEST')
async def get_template_info_controller(
    base_path: Path, # pylint: disable=unused-argument
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> TemplateInfo:
    '''
        Controller returning the metadata of the canonical Excel template. The
        template is always downloadable (generated on demand), so the URL is
        unconditional.

        Returns:
            TemplateInfo: Version + required/optional columns + relative URL.
    '''
    return TemplateInfo(
        template_version = TEMPLATE_VERSION,
        download_url = '/v1/ingest/template/file',
        required_columns = list(REQUIRED_COLUMNS),
        optional_columns = list(OPTIONAL_COLUMNS)
    )
