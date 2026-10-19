'''
    services/events/tests/test_events.py

    Pure tests: they import only schemas and modules that need no
    configuration, because the CI of GitHub Actions runs them with no .env.
'''
import pytest
from pydantic import ValidationError

from schemas.audit import READ_ROLES, AuditRecordCreateSchema, AuditRecordQuerySchema
from schemas.usage_log import UsageLogQuerySchema
from services.payload_limits import (
    TRUNCATION_MARKER,
    cap_log_bodies,
    cap_many,
    truncate_body
)


def test_truncate_body_keeps_what_fits() -> None:
    '''A body under the cap comes back as the same object, structure intact.'''
    body = {'sku': 'A1', 'quantity': 3}
    assert truncate_body(body, max_chars = 100) is body
    assert truncate_body(None, max_chars = 100) is None


def test_truncate_body_cuts_and_marks() -> None:
    '''A body over the cap is cut at the cap and carries the visible marker.'''
    capped = truncate_body('x' * 50, max_chars = 10)
    assert capped == 'x' * 10 + TRUNCATION_MARKER


def test_truncate_body_measures_the_serialized_size() -> None:
    '''A structure is measured as the text that would be stored.'''
    capped = truncate_body({'rows': list(range(100))}, max_chars = 20)
    assert isinstance(capped, str)
    assert capped.endswith(TRUNCATION_MARKER)
    assert len(capped) == 20 + len(TRUNCATION_MARKER)


def test_cap_log_bodies_touches_only_the_bodies() -> None:
    '''Request, response and audit states are capped; the rest is untouched.'''
    record = {'endpoint': '/v1/finance/report' + 'z' * 50, 'request_body': 'r' * 50,
              'response_body': 'ok', 'old_values': 'o' * 50, 'new_values': 'n' * 50}
    cap_log_bodies(record, max_chars = 10)
    assert record['endpoint'].endswith('z' * 50)
    assert record['response_body'] == 'ok'
    for field in ('request_body', 'old_values', 'new_values'):
        assert record[field].endswith(TRUNCATION_MARKER)


def test_cap_many_caps_every_record() -> None:
    '''A whole page is capped, so it cannot pass the Lambda response limit.'''
    page = cap_many([{'request_body': 'a' * 30}, {'request_body': 'b'}], max_chars = 5)
    assert page[0]['request_body'] == 'aaaaa' + TRUNCATION_MARKER
    assert page[1]['request_body'] == 'b'


def test_audit_record_ignores_unknown_fields() -> None:
    '''A service that sends more than the schema knows is not rejected.'''
    record = AuditRecordCreateSchema(microservice = 'FINANCE', entity_name = 'Entry',
                                     entity_id = 7, action = 'UPDATE', user_id = 'acme',
                                     new_values = {'amount': 10}, unexpected = True)
    assert not hasattr(record, 'unexpected')
    assert record.old_values is None


@pytest.mark.parametrize('schema', [AuditRecordQuerySchema, UsageLogQuerySchema])
def test_query_page_size_is_bounded(schema: type) -> None:
    '''A page holds between 1 and 100 records.'''
    assert schema().limit == 100
    for limit in (0, 101):
        with pytest.raises(ValidationError):
            schema(limit = limit)


def test_only_admin_reads_the_logs() -> None:
    '''The logs hold every user's e-mail, IP and request bodies.'''
    assert READ_ROLES == ('ADMIN',)
