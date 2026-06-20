'''
    Analytics Run Model for DynamoDB.
'''
from typing import Any, Dict, List, TypedDict


class AnalyticsRun(TypedDict, total = False):
    '''
        Python model representing an analytics run document in DynamoDB.

        Table: analytics_runs
        Partition Key: id (String, UUIDv4) — same value as `run_id`,
                       mirrored so any run is uniquely addressable.

        Multiple runs per dataset are still possible (the `dataset_id`
        attribute is regular, not part of the key). To list every run for
        a given dataset, scan with FilterExpression — implemented in
        services/analytics_runs.py:get_latest_run_for_dataset.
    '''
    id: str
    dataset_id: str
    run_id: str
    status: str
    owner_email: str
    summary: Dict[str, Any]
    opportunities: List[Dict[str, Any]]
    parameters: Dict[str, Any]
    created_at: str
