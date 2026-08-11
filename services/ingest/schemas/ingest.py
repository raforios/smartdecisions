'''
    Pydantic V2 DTOs for the Ingest service.

    Defines the request/response contracts for uploading and validating sales
    Excel files. The DataFrame-level contract (column dtypes, nullability,
    business rules) lives in services/excel_validator.py — these DTOs only
    describe the HTTP envelope.
'''
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class IngestColumnError(BaseModel):
    '''
        Detailed error for a single (row, column) in the uploaded Excel.
    '''
    row: int = Field(..., description = 'Excel row number (1-based, header is row 1).')
    column: str = Field(..., description = 'Column name where the error occurred.')
    value: Optional[str] = Field(None, description = 'Raw value that failed validation.')
    rule: str = Field(..., description = 'Pandera check name or business rule violated.')
    message: str = Field(..., description = 'Human-readable error in Spanish for the end user.')


class IngestSummary(BaseModel):
    '''
        High-level outcome of an ingest attempt.
    '''
    total_rows: int = Field(..., ge = 0)
    valid_rows: int = Field(..., ge = 0)
    error_rows: int = Field(..., ge = 0)
    unique_points_of_sale: int = Field(..., ge = 0)
    unique_products: int = Field(..., ge = 0)
    date_range_start: Optional[str] = Field(None,
                    description = 'ISO date of the earliest valid sale.')
    date_range_end: Optional[str] = Field(None,
                    description = 'ISO date of the latest valid sale.')


class IngestResponse(BaseModel):
    '''
        Response payload returned after a successful ingest.

        `status = 'validated'` means the file passed the structural contract and
        is ready for downstream analysis (paso 3 of the POC). `status = 'failed'`
        means the file was uploaded but rejected: `errors` lists per-row issues.
    '''
    model_config = ConfigDict(json_schema_extra = {
        'example': {
            'dataset_id': '7c1a4f31-7c9f-4d63-8b9a-2c0f3a5b7e21',
            'status': 'validated',
            'file_s3_key': 'ingest/2026/06/12/7c1a4f31.xlsx',
            'summary': {
                'total_rows': 1843,
                'valid_rows': 1843,
                'error_rows': 0,
                'unique_points_of_sale': 42,
                'unique_products': 187,
                'date_range_start': '2026-01-01',
                'date_range_end': '2026-05-31'
            },
            'errors': [],
            'created_at': '2026-06-12T15:42:01Z'
        }
    })

    dataset_id: str
    status: str = Field(..., description = "'validated' or 'failed'.")
    file_s3_key: str = Field(..., description = 'Object key in the S3 bucket managed by FILES.')
    summary: IngestSummary
    errors: list[IngestColumnError] = Field(default_factory = list)
    created_at: datetime


class IngestStatusResponse(BaseModel):
    '''
        Compact metadata for `GET /ingest/{dataset_id}`. `status` is
        'validated' or 'failed'.
    '''
    dataset_id: str
    status: str
    owner_email: str
    file_s3_key: str
    summary: IngestSummary
    errors: list[IngestColumnError] = Field(default_factory = list)
    created_at: datetime


class IngestFromS3Request(BaseModel):
    '''
        Request for ingesting a file already uploaded to S3 via a pre-signed URL.

        Large files (real sales exports easily exceed the 10 MB API Gateway limit)
        are uploaded directly to S3 by the browser; the service then reads them
        from S3 by key, so no big binary ever transits API Gateway / Lambda.
    '''
    file_key: str = Field(..., min_length = 1,
                description = 'S3 object key of the raw uploaded file.')
    file_name: str = Field(..., min_length = 1,
                description = 'Original filename (drives format detection: .xlsx/.csv).')


class TemplateInfo(BaseModel):
    '''
        Metadata describing the canonical Excel template version.
    '''
    template_version: str = Field(...,
                description = "Semantic version of the contract, e.g. 'v1'.")
    download_url: str = Field(...,
                description = 'Pre-signed URL or static URL to download the template.')
    required_columns: list[str]
    optional_columns: list[str]
