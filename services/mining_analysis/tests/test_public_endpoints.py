'''
    Smoke tests for the public mineral-report endpoints — reachable without a
    JWT, answering 200 with the expected payload shape.

    They run against DynamoDB (moto), which is what the deployment serves:
    the route resolves the resource through GET_DB_DEPENDENCY and hands it
    down, exactly as in production.
'''
from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from moto import mock_aws

from models.mining_analysis import MiningPriceItem
from routes.public_reports import router as public_reports_router
from services import prices_dyb
from services.db_connection import GET_DB_DEPENDENCY
from services.mining_analysis import normalize_name
from tests.dynamo_helpers import build_quotation_tables, seed_official_catalog

# Two days of tin, the pair the assertions below read: 21.0 then 22.0.
TIN_PRICES = ((date(2026, 4, 10), 21.0), (date(2026, 4, 11), 22.0))


@pytest.fixture(name = 'public_client')
def _public_client():
    '''
        A client for the public router backed by a mocked DynamoDB holding the
        official catalogue and two tin quotations.

        Returns:
            TestClient: Ready to hit the public endpoints anonymously.
    '''
    with mock_aws():
        resource = build_quotation_tables()
        catalogue_ids = seed_official_catalog(resource)
        tin_id = catalogue_ids[normalize_name('Estaño')]
        prices_dyb.put_prices_batch(resource, [
            MiningPriceItem(mineral_id = tin_id, date = day, price_low = price, price_high = price)
            for day, price in TIN_PRICES
        ])

        app = FastAPI()
        app.include_router(public_reports_router)
        app.dependency_overrides[GET_DB_DEPENDENCY] = lambda: resource
        try:
            yield TestClient(app)
        finally:
            app.dependency_overrides.clear()


def test_public_daily_returns_200_without_auth(public_client):
    '''Public daily endpoint must respond without an Authorization header.'''
    response = public_client.get('/v1/mining-analysis/public/reports/daily',
                                 params = {'date': '2026-04-11'})
    assert response.status_code == 200
    body = response.json()
    assert body['ref_date'] == '2026-04-11'
    estano = next(r for r in body['rows'] if r['mineral'] == 'Estaño')
    assert estano['price_low'] == 22.0
    assert estano['previous_price_low'] == 21.0
    # Two decimals, like every published percentage: the exact value is
    # 4.7619…, and what travels is what a reader would be shown.
    assert estano['change_pct'] == pytest.approx(4.76, abs = 1e-9)


def test_public_biweekly_returns_200_without_auth(public_client):
    '''Public biweekly endpoint must respond without an Authorization header.'''
    response = public_client.get('/v1/mining-analysis/public/reports/biweekly',
                                 params = {'year': 2026, 'month': 4, 'half': 1})
    assert response.status_code == 200
    body = response.json()
    assert body['year'] == 2026 and body['month'] == 4 and body['half'] == 1
    estano = next(r for r in body['rows'] if r['mineral'] == 'Estaño')
    assert estano['avg_price_low'] == pytest.approx(21.5)
    assert estano['sample_size'] == 2


def test_public_biweekly_history_returns_200_without_auth(public_client):
    '''The history endpoint must return at least the populated period.'''
    response = public_client.get(
        '/v1/mining-analysis/public/reports/biweekly/history')
    assert response.status_code == 200
    body = response.json()
    keys = [(p['year'], p['month'], p['half']) for p in body['periods']]
    assert (2026, 4, 1) in keys


def test_responses_carry_codes_and_no_prose(public_client):
    '''
        Every report answers with a stable code, never with a sentence.

        The backend returns data and codes; the wording belongs to the frontend
        and to the interpretation layer. A regression here is invisible until
        someone builds a screen on top of an English phrase.
    '''
    cases = (
        ('/v1/mining-analysis/public/reports/daily',
         {'date': '2026-04-11'}, 'DAILY_REPORT_GENERATED'),
        ('/v1/mining-analysis/public/reports/biweekly',
         {'year': 2026, 'month': 4, 'half': 1}, 'BIWEEKLY_REPORT_GENERATED'),
        ('/v1/mining-analysis/public/reports/biweekly/history',
         {'date_from': '2026-04-01', 'date_to': '2026-04-30'},
         'BIWEEKLY_HISTORY_GENERATED'),
    )

    for path, params, expected in cases:
        body = public_client.get(path, params = params).json()
        assert body['result'] == expected
        assert body['status'] == 'success'
        assert 'message' not in body
