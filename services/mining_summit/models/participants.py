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
    registered_date: str
    registered_at: str
