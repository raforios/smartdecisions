'''
    Dataset Model for DynamoDB.
'''
from typing import Any, Dict, List, Optional, TypedDict


class IngestDataset(TypedDict, total = False):
    '''
        Python model representing an ingested dataset document in DynamoDB.

        Table: ingest_datasets
        Partition Key: id (String, UUIDv4) — same value as the logical
                       `dataset_id` attribute, kept as a mirror for backward
                       compatibility with downstream consumers.

        Status values:
            - 'validated': file passed the contract and is ready for analytics.
            - 'failed':    file was uploaded but rejected; see `errors`.

        Every companion file attached to the dataset (collections, stock,
        visits, objectives) writes the same three attributes, named after it:
        `<companion>_s3_key`, `<companion>_summary` and `<companion>_issues`.
    '''
    id: str
    dataset_id: str
    owner_email: str
    status: str
    file_s3_key: Optional[str]
    rejected_s3_key: Optional[str]
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
    collections_s3_key: Optional[str]
    collections_summary: Dict[str, Any]
    collections_issues: List[Dict[str, Any]]
    stock_s3_key: Optional[str]
    stock_summary: Dict[str, Any]
    stock_issues: List[Dict[str, Any]]
    visits_s3_key: Optional[str]
    visits_summary: Dict[str, Any]
    visits_issues: List[Dict[str, Any]]
    objectives_s3_key: Optional[str]
    objectives_summary: Dict[str, Any]
    objectives_issues: List[Dict[str, Any]]
