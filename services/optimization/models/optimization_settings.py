'''
    Route parameters item for DynamoDB.
'''
from typing import Any, Dict, Optional, TypedDict


class RouteSettingsItem(TypedDict, total = False):
    '''
        The route parameters of one company.

        Table: optimization_settings
        Partition Key: owner_email (String)

        `base_point` is {name, latitude, longitude}: where routes may start or
        end when a plan asks for it.
    '''
    owner_email: str
    base_point: Optional[Dict[str, Any]]
    updated_at: str
