'''
    Registration Model for DynamoDB.
'''
from typing import Optional, TypedDict


class Registration(TypedDict, total = False):
    '''
        Python model representing a participant's event registration/seat in
        DynamoDB. Joined to the person master data (mining_summit_participants)
        by `ci`. A person only has a registration once they are seated in a
        thematic axis; the replacement chain and lifecycle status live here.

        Table: mining_summit_registration
        Partition Key: ci (String)
    '''
    ci: str
    assignment_type: Optional[str]
    axis: Optional[str]
    axis_label: Optional[str]
    mesa_code: Optional[str]
    observation: Optional[str]
    replaces_ci: Optional[str]
    replaced_by_ci: Optional[str]
    # Lifecycle: ACTIVE by default; REPLACED/CANCELLED for soft-deleted seats.
    status: str
    registered_at: str
    # Audit: operator (email) who created this registration and who last changed
    # its lifecycle (cancellation / replacement), so the action is never anonymous.
    registered_by: Optional[str]
    status_changed_by: Optional[str]
    status_changed_at: Optional[str]
