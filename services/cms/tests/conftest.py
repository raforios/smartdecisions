'''
    Shared CMS test fixtures.

    Spins up a moto-mocked DynamoDB resource per test, creates the four CMS
    tables on it, and exposes both the resource and a populated `TestClient`
    that injects the resource via FastAPI's dependency_overrides.
'''
import os
from typing import Generator

import boto3
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from moto import mock_aws

# AWS SDK credential resolution is strict even when targeting moto.
# Set throwaway values *before* boto3 spins up its session cache.
os.environ.setdefault('AWS_ACCESS_KEY_ID', 'testing')
os.environ.setdefault('AWS_SECRET_ACCESS_KEY', 'testing')
os.environ.setdefault('AWS_SESSION_TOKEN', 'testing')
os.environ.setdefault('AWS_DEFAULT_REGION', 'us-east-1')


CMS_TABLE_NAMES = (
    't_cms_news',
    't_cms_documents',
    't_cms_slides',
    't_cms_entities',
)


def _provision_tables(dynamodb_resource) -> None:
    '''
        Creates the four CMS tables on the supplied resource. Each table
        is keyed solely by `id` (string uuid) to mirror dynamodb.sh.
    '''
    for table_name in CMS_TABLE_NAMES:
        dynamodb_resource.create_table(
            TableName = table_name,
            AttributeDefinitions = [{'AttributeName': 'id', 'AttributeType': 'S'}],
            KeySchema = [{'AttributeName': 'id', 'KeyType': 'HASH'}],
            BillingMode = 'PAY_PER_REQUEST',
        )


@pytest.fixture()
def dynamodb_resource() -> Generator:
    '''
        Yields a moto-mocked DynamoDB resource with the four CMS tables
        already created.
    '''
    with mock_aws():
        resource = boto3.resource('dynamodb', region_name = 'us-east-1')
        _provision_tables(resource)
        yield resource


@pytest.fixture()
def public_client(dynamodb_resource):
    '''
        FastAPI TestClient mounting only the public CMS router and
        injecting the moto resource through the standard DB dependency.
    '''
    from routes.public_cms import router as public_cms_router
    from services.db_connection import get_db_dependency

    app = FastAPI()
    app.include_router(public_cms_router)
    app.dependency_overrides[get_db_dependency] = lambda: dynamodb_resource
    yield TestClient(app)
    app.dependency_overrides.clear()
