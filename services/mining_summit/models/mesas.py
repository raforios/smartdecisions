'''
    Mesa reference model.

    Reference data (not a DynamoDB table): mesas are the fixed campus rooms
    (aulas ≡ mesas) seeded in services.summit_rules and allocated to thematic
    axes by a fixed, importance-based configuration.
'''
from typing import TypedDict


class Mesa(TypedDict, total = False):
    '''
        Shape of a working table (mesa) once allocated to a thematic axis.
    '''
    code: str
    block: str
    location: str
    capacity: int
    axis: str
    axis_number: int
    axis_label: str
