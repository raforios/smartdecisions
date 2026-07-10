'''
    Institution model for DynamoDB.

    Table: mining_summit_institutions (Partition Key: id). Seeded from the
    official participation matrix by tools/mining_summit/import_institutions.py.
'''
from typing import Optional, TypedDict


class Institution(TypedDict, total = False):
    '''
        Shape of a single institution document in DynamoDB.

        Role and assignment_type are not stored; they are derived at runtime
        from the category via services.summit_rules.
    '''
    id: str
    number: int
    name: str
    abbreviation: Optional[str]
    category: str
    cupos: int
