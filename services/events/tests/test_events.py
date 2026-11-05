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


def test_both_logs_store_and_page_through_one_implementation(monkeypatch) -> None:
    '''
        A record gets its id and timestamp and its bodies capped; the listing
        answers the log's own page schema. Audit and usage go through the same
        code, each with its table.

        The environment is set before the import because CI runs without
        `.env` and `services/events.py` validates it on import.
    '''
    # pylint: disable=import-outside-toplevel
    import importlib

    import boto3
    from moto import mock_aws

    monkeypatch.setenv('DYNAMODB_TABLE_NAME_AUDIT', 'events-audit-test')
    monkeypatch.setenv('DYNAMODB_TABLE_NAME_USAGE', 'events-usage-test')
    monkeypatch.setenv('TARGET_TIMEZONE', 'America/La_Paz')
    monkeypatch.setenv('AWS_DEFAULT_REGION', 'us-east-1')
    events = importlib.import_module('services.events')
    usage_schemas = importlib.import_module('schemas.usage_log')

    with mock_aws():
        dynamodb = boto3.resource('dynamodb', region_name = 'us-east-1')
        # The names the module read: the .env's when it is already imported.
        for table in (events.AUDIT_LOG.table, events.USAGE_LOG.table):
            dynamodb.create_table(TableName = table, BillingMode = 'PAY_PER_REQUEST',
                                  KeySchema = [{'AttributeName': 'id', 'KeyType': 'HASH'}],
                                  AttributeDefinitions = [{'AttributeName': 'id',
                                                           'AttributeType': 'S'}])

        stored = events.record_event(dynamodb, events.AUDIT_LOG, AuditRecordCreateSchema(
            microservice = 'BILLING', entity_name = 'sale', entity_id = 7, action = 'CREATE',
            user_id = 'cajera@farmacia.bo', new_values = 'x' * 5000))
        events.record_event(dynamodb, events.USAGE_LOG, usage_schemas.UsageLogCreateSchema(
            user_app = 'portal', microservice = 'BILLING', endpoint = '/v1/billing/sales',
            method = 'POST', status_code = 201, ip_address = '10.0.0.1'))

        audit_page = events.list_events(dynamodb, events.AUDIT_LOG, AuditRecordQuerySchema())
        usage_page = events.list_events(dynamodb, events.USAGE_LOG, UsageLogQuerySchema())

    assert stored.id and stored.timestamp
    assert stored.new_values.endswith(TRUNCATION_MARKER)
    assert [record.id for record in audit_page.records] == [stored.id]
    assert isinstance(usage_page, usage_schemas.UsageLogsPage) and len(usage_page.records) == 1
    assert audit_page.last_evaluated_key is None
