'''
    Smoke tests for the public mineral-report endpoints — verifies they are
    reachable without a JWT and return 200 with the expected payload shape.
'''
from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from models.mining_analysis import Mineral, MiningPrice
from routes.public_reports import router as public_reports_router
from services.db_connection import Base, GET_DB_DEPENDENCY
from services.mining_analysis import OFFICIAL_MINERALS, _normalize_name


@pytest.fixture(name = 'public_client')
def _public_client():
    '''
    Builds a FastAPI app mounting only the public router and a SQLite-backed
    DB dependency override, returning the TestClient ready to hit the public
    endpoints anonymously.
    '''
    engine = create_engine(
        'sqlite:///:memory:',
        future = True,
        connect_args = {'check_same_thread': False},
        poolclass = StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind = engine, autocommit = False, autoflush = False)
    session = session_factory()
    # Seed catalog + a few prices so the endpoints have something to return.
    for catalog in OFFICIAL_MINERALS:
        session.add(Mineral(
            name = catalog['name'],
            unit = catalog['unit'],
            chemical_symbol = catalog['chemical_symbol'],
            quoted_in = catalog['quoted_in'],
        ))
    session.commit()
    mineral_id = {
        _normalize_name(m.name): m.id for m in session.query(Mineral).all()
    }
    session.add(MiningPrice(
        mineral_id = mineral_id[_normalize_name('Estaño')],
        date = date(2026, 4, 10), price_low = 21.0, price_high = 21.0,
    ))
    session.add(MiningPrice(
        mineral_id = mineral_id[_normalize_name('Estaño')],
        date = date(2026, 4, 11), price_low = 22.0, price_high = 22.0,
    ))
    session.commit()

    app = FastAPI()
    app.include_router(public_reports_router)

    def _override_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[GET_DB_DEPENDENCY] = _override_db
    try:
        yield TestClient(app)
    finally:
        session.close()
        engine.dispose()


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
    assert estano['change_pct'] == pytest.approx((22.0 - 21.0) / 21.0 * 100, rel = 1e-4)


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
