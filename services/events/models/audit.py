'''
   Audit Record Model for DynamoDB
'''
from typing import TypedDict

class AuditRecord(TypedDict):
    '''
    Python model to represent an audit record document in DynamoDB.
    
    This TypedDict defines the expected structure of items in the
    't_audit_records' table, which is schemaless in DynamoDB.
    
    DynamoDB Partition Key: 'id' (String, e.g., UUID)
    '''
    id: str  # Unique identifier for the item (e.g., UUID)
    microservice: str
    entity_name: str
    entity_id: str  # Stored as a String for flexibility
    action: str
    user_id: str
    timestamp: str  # ISO 8601 format
    old_values: dict
    new_values: dict
