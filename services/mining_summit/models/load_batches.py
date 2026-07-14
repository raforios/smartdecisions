'''
    Load-batch model for DynamoDB.

    One record per institution file processed by the ETL. Keeps the responsible
    person and the accepted/rejected outcome as evidence (constancia) and as the
    source for the consolidated document later sent to the responsible.
'''
from typing import Any, List, TypedDict


class LoadBatch(TypedDict, total = False):
    '''
        Python model representing a load-batch document in DynamoDB.

        Table: mining_summit_load_batches
        Partition Key: batch_id (String, uuid4)
    '''
    batch_id: str
    institution_id: str
    institution_name: str
    responsible_name: str
    responsible_phone: str
    cupos: int
    already_accredited: int
    accepted_count: int
    rejected_count: int
    accepted_cis: List[str]
    rejected: List[Any]
    created_at: str
