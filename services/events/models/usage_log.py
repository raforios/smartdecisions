'''
   Usage Log Model for DynamoDB
'''
from typing import TypedDict

class UsageLog(TypedDict):
    '''
      Python model to represent a usage log document in DynamoDB.
      
      This TypedDict defines the expected structure of items in the
      't_usage_logs' table, which is schemaless in DynamoDB.
      
      DynamoDB Partition Key: 'id' (String, e.g., UUID)
    '''
    id: str  # Unique identifier for the item (e.g., UUID)
    user_app: str
    microservice: str
    endpoint: str
    method: str
    status_code: int
    ip_address: str
    request_body: dict
    response_body: dict
    response_time_ms: int
    timestamp: str  # ISO 8601 format
