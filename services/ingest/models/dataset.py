'''
    Dataset Model for DynamoDB.
'''
from typing import Any, Dict, List, Optional, TypedDict


class IngestDataset(TypedDict, total = False):
    '''
        Python model representing an ingested dataset document in DynamoDB.

        Table: t_ingest_datasets
        Partition Key: dataset_id (String, UUIDv4)

        Status values:
            - 'validated': file passed the contract and is ready for analytics.
            - 'failed':    file was uploaded but rejected; see `errors`.
    '''
    dataset_id: str
    owner_email: str
    status: str
    file_s3_key: Optional[str]
    template_version: str
    total_rows: int
    valid_rows: int
    error_rows: int
    unique_points_of_sale: int
    unique_products: int
    date_range_start: Optional[str]
    date_range_end: Optional[str]
    errors: List[Dict[str, Any]]
    created_at: str
