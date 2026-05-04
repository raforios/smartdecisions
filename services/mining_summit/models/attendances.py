'''
    Attendance Model for DynamoDB.
'''
from typing import TypedDict


class Attendance(TypedDict):
    '''
        Python model representing an attendance document in DynamoDB.

        Table: mining_summit_attendances
        Partition Key: ci (String)
        Sort Key: attendance_date (String, YYYY-MM-DD)

        The composite (ci, attendance_date) key naturally enforces a single
        attendance per participant per day.
    '''
    ci: str
    attendance_date: str
    attendance_at: str
    marked_by: str
