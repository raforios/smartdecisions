'''
    Participant Model for DynamoDB.
'''
from typing import Optional, TypedDict


class Participant(TypedDict, total = False):
    '''
        Python model representing a participant (person) document in DynamoDB.

        The person master data is intentionally decoupled from the event
        registration/seat, which lives in the `mining_summit_registration`
        table and is joined by `ci`. A person may exist without a registration.

        Table: mining_summit_participants
        Partition Key: ci (String)
    '''
    ci: str
    first_name: str
    last_name: str
    email: Optional[str]
    phone: Optional[str]
    department: Optional[str]
    institution_id: Optional[str]
    role: Optional[str]
    created_at: str
