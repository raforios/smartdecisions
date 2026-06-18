'''
    Ingest controllers.
'''
from pathlib import Path
from typing import Any, Dict, Optional
from boto3.resources.base import ServiceResource

from schemas.ingest import (
    IngestColumnError,
    IngestResponse,
    IngestStatusResponse,
    IngestSummary,
    TemplateInfo
)
from services.datasets import get_dataset_by_id, persist_dataset
from services.excel_parser import parse_and_validate
from services.excel_validator import OPTIONAL_COLUMNS, REQUIRED_COLUMNS, TEMPLATE_VERSION
from services.file_storage import upload_excel
from services.utils import handle_service_errors


TEMPLATE_RELATIVE_PATH = 'assets/template_ventas_v1.xlsx'


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


@handle_service_errors
def ingest_excel_controller(
    dynamodb_resource: ServiceResource,
    file_bytes: bytes,
    filename: str,
    bearer_token: str,
    current_user: str
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
    _, errors, summary = parse_and_validate(file_bytes, filename)
    is_valid = not errors

    file_s3_key: Optional[str] = None
    if is_valid:
        file_s3_key = upload_excel(
            file_bytes = file_bytes,
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


@handle_service_errors
def get_dataset_status_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str
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
        created_at = item['created_at']
    )


def get_template_info_controller(base_path: Path) -> TemplateInfo:
    '''
        Controller returning the metadata of the canonical Excel template.

        Args:
            base_path (Path): Service root, used to resolve the static template file.

        Returns:
            TemplateInfo: Version + required/optional columns + relative URL.
    '''
    template_path = (base_path / TEMPLATE_RELATIVE_PATH).resolve()
    download_url = f'/v1/ingest/template/file' if template_path.exists() else ''
    return TemplateInfo(
        template_version = TEMPLATE_VERSION,
        download_url = download_url,
        required_columns = list(REQUIRED_COLUMNS),
        optional_columns = list(OPTIONAL_COLUMNS)
    )
