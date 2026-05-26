'''
    Smoke tests for the CMS admin endpoints.

    Auth is exercised once (401 without token, 200 with override) and then
    every CRUD path is covered for each of the four entities using the
    moto-mocked DynamoDB resource. The JWT dependency is overridden with
    a fake user to keep the tests independent of `SECRET_KEY` / `ALGORITHM`.
'''
from typing import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


FAKE_ADMIN = 'tester@admin.local'


@pytest.fixture()
def admin_client(dynamodb_resource) -> Generator[TestClient, None, None]:
    '''
        FastAPI TestClient mounting the admin router with the auth
        dependency stubbed to a fixed user.
    '''
    from routes.admin_cms import router as admin_cms_router
    from services.db_connection import get_db_dependency
    from services.security import get_current_user

    app = FastAPI()
    app.include_router(admin_cms_router)
    app.dependency_overrides[get_db_dependency] = lambda: dynamodb_resource
    app.dependency_overrides[get_current_user] = lambda: FAKE_ADMIN
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def unauth_client(dynamodb_resource) -> Generator[TestClient, None, None]:
    '''
        Same router, but WITHOUT the auth override so the real
        get_current_user runs and 401s on missing header.
    '''
    from routes.admin_cms import router as admin_cms_router
    from services.db_connection import get_db_dependency

    app = FastAPI()
    app.include_router(admin_cms_router)
    app.dependency_overrides[get_db_dependency] = lambda: dynamodb_resource
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---------- Auth boundary ----------

def test_admin_requires_authorization(unauth_client):
    '''Without a Bearer token the admin endpoints must 401.'''
    response = unauth_client.get('/v1/cms/admin/news')
    assert response.status_code == 401


# ---------- News CRUD ----------

def test_news_crud_happy_path(admin_client):
    '''Create → list → fetch → partial update → delete.'''
    payload = {
        'lang': 'es',
        'type': 'press',
        'title': 'Prensa Inicial',
        'summary': 'Resumen corto',
        'image_s3_bucket': 'cms-bucket',
        'image_s3_key': 'news/abc.jpg',
        'sort_order': 1,
    }
    created = admin_client.post('/v1/cms/admin/news', json = payload)
    assert created.status_code == 201, created.text
    created_body = created.json()
    news_id = created_body['id']
    assert created_body['is_published'] is True
    assert created_body['image_url'] == 'https://cms-bucket.s3.amazonaws.com/news/abc.jpg'

    listing = admin_client.get('/v1/cms/admin/news')
    assert listing.status_code == 200
    assert any(item['id'] == news_id for item in listing.json()['items'])

    detail = admin_client.get(f'/v1/cms/admin/news/{news_id}')
    assert detail.status_code == 200
    assert detail.json()['title'] == 'Prensa Inicial'

    updated = admin_client.put(
        f'/v1/cms/admin/news/{news_id}',
        json = {'title': 'Prensa Actualizada', 'is_published': False},
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body['title'] == 'Prensa Actualizada'
    assert body['is_published'] is False
    # Untouched fields must survive the partial update.
    assert body['summary'] == 'Resumen corto'

    deleted = admin_client.delete(f'/v1/cms/admin/news/{news_id}')
    assert deleted.status_code == 200
    assert deleted.json()['id'] == news_id

    missing = admin_client.get(f'/v1/cms/admin/news/{news_id}')
    assert missing.status_code == 404


# ---------- Documents CRUD ----------

def test_document_crud_happy_path(admin_client):
    '''Create with external URL, update to switch to S3 ref, delete.'''
    created = admin_client.post('/v1/cms/admin/documents', json = {
        'lang': 'es',
        'title': 'Ley fomento',
        'doc_type': 'LEY',
        'doc_date': '2026-02-20',
        'file_external_url': 'https://gaceta.gob.bo/ley.pdf',
        'sort_order': 5,
    })
    assert created.status_code == 201, created.text
    body = created.json()
    document_id = body['id']
    assert body['file_url'] == 'https://gaceta.gob.bo/ley.pdf'

    updated = admin_client.put(f'/v1/cms/admin/documents/{document_id}', json = {
        'file_s3_bucket': 'cms-bucket',
        'file_s3_key': 'docs/ley.pdf',
        'file_external_url': None,
    })
    assert updated.status_code == 200
    # The S3 reference now wins over the (cleared) external URL.
    assert updated.json()['file_url'] == 'https://cms-bucket.s3.amazonaws.com/docs/ley.pdf'

    assert admin_client.delete(
        f'/v1/cms/admin/documents/{document_id}').status_code == 200


# ---------- Slides CRUD ----------

def test_slide_crud_happy_path(admin_client):
    '''Create, toggle is_active, delete.'''
    created = admin_client.post('/v1/cms/admin/slides', json = {
        'lang': 'es',
        'title': 'Litio',
        'description': 'Transición energética',
        'image_s3_bucket': 'cms-bucket',
        'image_s3_key': 'slides/litio.jpg',
        'sort_order': 1,
    })
    assert created.status_code == 201
    slide_id = created.json()['id']

    listing = admin_client.get('/v1/cms/admin/slides')
    assert any(item['id'] == slide_id for item in listing.json()['items'])

    toggled = admin_client.put(f'/v1/cms/admin/slides/{slide_id}', json = {
        'is_active': False,
    })
    assert toggled.status_code == 200
    assert toggled.json()['is_active'] is False

    assert admin_client.delete(
        f'/v1/cms/admin/slides/{slide_id}').status_code == 200


# ---------- Entities CRUD ----------

def test_entity_crud_happy_path(admin_client):
    '''Create an entity with a logo reference, partial-update its URL, delete.'''
    created = admin_client.post('/v1/cms/admin/entities', json = {
        'name': 'VINTO',
        'url': 'https://vinto.gob.bo',
        'logo_s3_bucket': 'cms-bucket',
        'logo_s3_key': 'entities/vinto.png',
        'sort_order': 1,
    })
    assert created.status_code == 201
    entity_id = created.json()['id']
    assert created.json()['logo_url'] == (
        'https://cms-bucket.s3.amazonaws.com/entities/vinto.png')

    updated = admin_client.put(f'/v1/cms/admin/entities/{entity_id}', json = {
        'url': 'https://www.vinto.gob.bo',
    })
    assert updated.status_code == 200
    assert updated.json()['url'] == 'https://www.vinto.gob.bo'
    # Other fields preserved.
    assert updated.json()['name'] == 'VINTO'

    assert admin_client.delete(
        f'/v1/cms/admin/entities/{entity_id}').status_code == 200


# ---------- Validation ----------

def test_news_create_rejects_invalid_type(admin_client):
    '''type fuera del Literal (press|communique|photo|article) → 422.'''
    response = admin_client.post('/v1/cms/admin/news', json = {
        'type': 'banner',
        'title': 'No debería pasar',
    })
    assert response.status_code == 422
    assert response.json()['detail'][0]['loc'][-1] == 'type'


# ---------- Missing-id 404s ----------

@pytest.mark.parametrize('endpoint', [
    '/v1/cms/admin/news/missing',
    '/v1/cms/admin/documents/missing',
    '/v1/cms/admin/slides/missing',
    '/v1/cms/admin/entities/missing',
])
def test_get_missing_returns_404(admin_client, endpoint):
    '''Fetching by unknown id must return 404, not 500.'''
    assert admin_client.get(endpoint).status_code == 404
