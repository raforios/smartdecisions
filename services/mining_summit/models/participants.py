'''
    Participant Model for DynamoDB.
'''
from typing import Optional, TypedDict


class Participant(TypedDict, total = False):
    '''
        Python model representing a participant document in DynamoDB.

        Table: mining_summit_participants
        Partition Key: ci (String)
    '''
    ci: str
    first_name: str
    last_name: str
    email: Optional[str]
    phone: Optional[str]
    department: Optional[str]
    company: Optional[str]
    institution_id: Optional[str]
    institution_name: Optional[str]
    role: Optional[str]
    assignment_type: Optional[str]
    axis: Optional[str]
    axis_label: Optional[str]
    mesa_code: Optional[str]
    # Lifecycle: ACTIVE by default; REPLACED/CANCELLED for soft-deleted seats.
    status: str
    observation: Optional[str]
    replaces_ci: Optional[str]
    replaced_by_ci: Optional[str]
    registered_date: str
    registered_at: str
