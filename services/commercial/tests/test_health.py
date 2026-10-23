'''
    Health of the service's tables: the answer for each state DynamoDB gives.
'''
from botocore.exceptions import ClientError
from schemas.health import TableState
from main import tables_health


class _Client:  # pylint: disable=too-few-public-methods
    '''A DynamoDB client that answers from a dict instead of AWS.'''

    def __init__(
        self,
        answers: dict
    ):
        self.answers = answers

    def describe_table( # pylint: disable=invalid-name
        self,
        TableName: str
    ) -> dict:
        '''The described table, or the error the dict holds for it.'''
        answer = self.answers[TableName]
        if isinstance(answer, str):
            raise ClientError({'Error': {'Code': answer, 'Message': answer}}, 'DescribeTable')
        return {'Table': answer}


def test_all_active_tables_are_healthy():
    '''Every table ACTIVE: healthy, with DynamoDB's counts.'''
    client = _Client({'a': {'TableStatus': 'ACTIVE', 'ItemCount': 3, 'TableSizeBytes': 90}})
    result = tables_health(client, 'svc', ['a'])
    assert result.healthy
    assert (result.tables[0].item_count, result.tables[0].size_bytes) == (3, 90)


def test_a_missing_or_unreadable_table_makes_it_unhealthy():
    '''A table that does not exist is MISSING; any other refusal, UNREACHABLE.'''
    client = _Client({
        'a': {'TableStatus': 'ACTIVE'},
        'b': 'ResourceNotFoundException',
        'c': 'AccessDeniedException'
    })
    result = tables_health(client, 'svc', ['a', 'b', 'c'])
    assert not result.healthy
    assert [table.status for table in result.tables] == [
        TableState.ACTIVE, TableState.MISSING, TableState.UNREACHABLE]
