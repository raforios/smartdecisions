'''
    services/mining_summit/tests/test_attendances.py

    Unit tests for the once-per-day attendance rule. DynamoDB is mocked with moto.
'''
import pytest
from moto import mock_aws

from services.attendances import ATTENDANCES_TABLE, register_attendance
from services.exceptions import RegisterAlreadyExistsError
from services.participants import PARTICIPANTS_TABLE, create_participant
from tests.dynamo_helpers import build_resource


@pytest.fixture(name = 'dynamodb')
def dynamodb_fixture():
    '''Provides moto DynamoDB with the participants and attendances tables.'''
    with mock_aws():
        resource = build_resource([(PARTICIPANTS_TABLE, 'ci')])
        # Attendances uses a composite (ci, attendance_date) key.
        resource.create_table(
            TableName = ATTENDANCES_TABLE,
            KeySchema = [
                {'AttributeName': 'ci', 'KeyType': 'HASH'},
                {'AttributeName': 'attendance_date', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions = [
                {'AttributeName': 'ci', 'AttributeType': 'S'},
                {'AttributeName': 'attendance_date', 'AttributeType': 'S'}
            ],
            BillingMode = 'PAY_PER_REQUEST'
        )
        yield resource


def _seed_participant(dynamodb, ci):
    '''Creates an ACTIVE participant with no seat (no axis needed).'''
    create_participant(dynamodb, {'ci': ci, 'first_name': 'N', 'last_name': 'A'})


def test_second_attendance_same_day_is_blocked(dynamodb):
    '''
        The first check-in of the day succeeds; a second one the same day is
        rejected with RegisterAlreadyExistsError (HTTP 409).
    '''
    _seed_participant(dynamodb, '111')
    saved, _created = register_attendance(dynamodb, {'ci': '111'}, marked_by = 'op@x.com')
    assert saved['ci'] == '111'

    with pytest.raises(RegisterAlreadyExistsError):
        register_attendance(dynamodb, {'ci': '111'}, marked_by = 'op@x.com')


def test_attendance_on_a_new_day_is_allowed(dynamodb):
    '''
        A prior day's attendance must not block today's: the uniqueness is per
        (ci, day), so the same participant can check in again on a different day.
    '''
    _seed_participant(dynamodb, '222')
    # Simulate a check-in on a past day.
    dynamodb.Table(ATTENDANCES_TABLE).put_item(Item = {
        'ci': '222', 'attendance_date': '2000-01-01',
        'attendance_at': '2000-01-01T09:00:00', 'marked_by': 'op@x.com'
    })

    saved, _created = register_attendance(dynamodb, {'ci': '222'}, marked_by = 'op@x.com')
    assert saved['ci'] == '222'
    assert saved['attendance_date'] != '2000-01-01'
