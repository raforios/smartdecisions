'''
    Analytics Run Model for DynamoDB.
'''
from typing import Any, Dict, List, TypedDict


class AnalyticsRun(TypedDict, total = False):
    '''
        Python model representing an analytics run document in DynamoDB.

        Table: t_analytics_runs
        Partition Key: dataset_id (String)
        Sort Key:      run_id     (String, UUIDv4)

        Sort key allows multiple runs on the same dataset (e.g., re-tuned
        Apriori thresholds) without overwriting prior history.
    '''
    dataset_id: str
    run_id: str
    status: str
    owner_email: str
    summary: Dict[str, Any]
    opportunities: List[Dict[str, Any]]
    parameters: Dict[str, Any]
    created_at: str
