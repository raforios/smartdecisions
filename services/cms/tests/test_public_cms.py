'''
    Smoke tests for the CMS public read endpoints against a moto-mocked
    DynamoDB. Each test seeds the relevant table(s) directly through the
    boto3 resource, then exercises the corresponding endpoint.
'''
import pytest


def _put_news(table, **overrides):
    item = {
        'id': overrides.pop('id', 'n1'),
        'lang': 'es',
        'type': 'press',
        'title': 'Default title',
        'is_published': True,
        'sort_order': 1,
    }
    item.update(overrides)
    table.put_item(Item = item)


def _put_document(table, **overrides):
    item = {
        'id': overrides.pop('id', 'd1'),
        'lang': 'es',
        'title': 'Default doc',
        'doc_type': 'PDF',
        'is_published': True,
        'sort_order': 1,
    }
    item.update(overrides)
    table.put_item(Item = item)


def _put_slide(table, **overrides):
    item = {
        'id': overrides.pop('id', 's1'),
        'lang': 'es',
        'title': 'Default slide',
        'is_active': True,
        'sort_order': 1,
    }
    item.update(overrides)
    table.put_item(Item = item)


def _put_entity(table, **overrides):
    item = {
        'id': overrides.pop('id', 'e1'),
        'name': 'DEFAULT',
        'url': 'https://example.org',
        'is_active': True,
        'sort_order': 1,
    }
    item.update(overrides)
    table.put_item(Item = item)


@pytest.fixture()
def seeded(dynamodb_resource):
    '''
        Seeds the four CMS tables with the same fixture dataset that
        previously lived inline in test_public_cms. Returns the resource
        so individual tests can re-query if needed.
    '''
    news = dynamodb_resource.Table('t_cms_news')
    _put_news(news, id = 'n1', title = 'Prensa ES 1', summary = 'Nota uno',
              published_at = '2026-05-10T00:00:00',
              image_s3_bucket = 'cms-bucket', image_s3_key = 'news/1.jpg')
    _put_news(news, id = 'n2', type = 'communique', title = 'Comunicado ES',
              summary = 'Aviso', sort_order = 2,
              published_at = '2026-05-11T00:00:00')
    _put_news(news, id = 'n3', lang = 'en', title = 'Press EN',
              summary = 'Note', published_at = '2026-05-12T00:00:00')
    _put_news(news, id = 'n4', title = 'Borrador',
              is_published = False, sort_order = 10)

    docs = dynamodb_resource.Table('t_cms_documents')
    _put_document(docs, id = 'd1', title = 'Reglamento 2026',
                  doc_date = '2026-03-10',
                  file_s3_bucket = 'cms-bucket',
                  file_s3_key = 'docs/reglamento.pdf')
    _put_document(docs, id = 'd2', title = 'Ley fomento', doc_type = 'LEY',
                  doc_date = '2026-02-20', sort_order = 2,
                  file_external_url = 'https://gaceta.gob.bo/ley.pdf')
    _put_document(docs, id = 'd3', title = 'Oculto', is_published = False,
                  sort_order = 99)

    slides = dynamodb_resource.Table('t_cms_slides')
    _put_slide(slides, id = 's1', title = 'Litio', description = 'Transición',
               image_s3_bucket = 'cms-bucket',
               image_s3_key = 'slides/litio.jpg')
    _put_slide(slides, id = 's2', title = 'Oro', sort_order = 2)
    _put_slide(slides, id = 's3', title = 'Inactivo', is_active = False,
               sort_order = 99)

    entities = dynamodb_resource.Table('t_cms_entities')
    _put_entity(entities, id = 'e1', name = 'VINTO', url = 'https://vinto.gob.bo')
    _put_entity(entities, id = 'e2', name = 'COMIBOL',
                url = 'https://comibol.gob.bo', sort_order = 2,
                logo_s3_bucket = 'cms-bucket',
                logo_s3_key = 'entities/comibol.png')
    _put_entity(entities, id = 'e3', name = 'INACTIVA',
                url = 'https://x.gob.bo', is_active = False, sort_order = 99)

    return dynamodb_resource


def test_public_news_lists_only_published_for_lang(public_client, seeded):
    '''Anonymous access yields only published Spanish news.'''
    response = public_client.get('/v1/cms/public/news', params = {'lang': 'es'})
    assert response.status_code == 200
    body = response.json()
    assert body['lang'] == 'es'
    titles = [item['title'] for item in body['items']]
    assert 'Borrador' not in titles
    assert 'Press EN' not in titles
    assert set(titles) == {'Prensa ES 1', 'Comunicado ES'}


def test_public_news_filters_by_type(public_client, seeded):
    '''The `type` alias filters down to the requested classification.'''
    response = public_client.get(
        '/v1/cms/public/news', params = {'lang': 'es', 'type': 'communique'})
    assert response.status_code == 200
    body = response.json()
    assert len(body['items']) == 1
    assert body['items'][0]['title'] == 'Comunicado ES'


def test_public_news_resolves_image_url(public_client, seeded):
    '''S3 bucket+key fields collapse into a public image URL.'''
    response = public_client.get('/v1/cms/public/news', params = {'lang': 'es'})
    item = next(i for i in response.json()['items'] if i['title'] == 'Prensa ES 1')
    assert item['image_url'] == 'https://cms-bucket.s3.amazonaws.com/news/1.jpg'


def test_public_documents_prefers_s3_then_external(public_client, seeded):
    '''S3 reference wins when present; external URL is used otherwise.'''
    response = public_client.get(
        '/v1/cms/public/documents', params = {'lang': 'es'})
    assert response.status_code == 200
    items = {item['title']: item for item in response.json()['items']}
    assert 'Oculto' not in items
    assert items['Reglamento 2026']['file_url'] == (
        'https://cms-bucket.s3.amazonaws.com/docs/reglamento.pdf')
    assert items['Ley fomento']['file_url'] == 'https://gaceta.gob.bo/ley.pdf'


def test_public_slides_excludes_inactive(public_client, seeded):
    '''Inactive slides must not surface in the public endpoint.'''
    response = public_client.get('/v1/cms/public/slides', params = {'lang': 'es'})
    assert response.status_code == 200
    titles = [item['title'] for item in response.json()['items']]
    assert 'Inactivo' not in titles
    assert set(titles) == {'Litio', 'Oro'}


def test_public_entities_excludes_inactive_and_resolves_logo(public_client, seeded):
    '''Entities listing skips inactive rows and resolves the logo URL.'''
    response = public_client.get('/v1/cms/public/entities')
    assert response.status_code == 200
    items = {item['name']: item for item in response.json()['items']}
    assert 'INACTIVA' not in items
    assert items['VINTO']['logo_url'] is None
    assert items['COMIBOL']['logo_url'] == (
        'https://cms-bucket.s3.amazonaws.com/entities/comibol.png')


# ---------- Detail endpoints (get-by-id) ----------

def test_public_news_detail_returns_published_item(public_client, seeded):
    '''The detail endpoint returns a single published item with resolved URLs.'''
    response = public_client.get('/v1/cms/public/news/n1')
    assert response.status_code == 200
    body = response.json()
    assert body['title'] == 'Prensa ES 1'
    assert body['image_url'] == 'https://cms-bucket.s3.amazonaws.com/news/1.jpg'


def test_public_news_detail_hides_drafts(public_client, seeded):
    '''Unpublished items must not be reachable via id-guessing.'''
    response = public_client.get('/v1/cms/public/news/n4')
    assert response.status_code == 404


def test_public_news_detail_404_when_missing(public_client, seeded):
    '''Unknown id → 404, not 500.'''
    response = public_client.get('/v1/cms/public/news/does-not-exist')
    assert response.status_code == 404


def test_public_document_detail_returns_resolved_url(public_client, seeded):
    '''Document detail resolves S3 first, external URL as fallback.'''
    response = public_client.get('/v1/cms/public/documents/d1')
    assert response.status_code == 200
    assert response.json()['file_url'] == (
        'https://cms-bucket.s3.amazonaws.com/docs/reglamento.pdf')


def test_public_document_detail_hides_drafts(public_client, seeded):
    '''Documents with is_published=False must 404.'''
    assert public_client.get('/v1/cms/public/documents/d3').status_code == 404


def test_public_slide_detail_hides_inactive(public_client, seeded):
    '''Inactive slides must 404 even if their id is known.'''
    assert public_client.get('/v1/cms/public/slides/s3').status_code == 404


def test_public_entity_detail_returns_item(public_client, seeded):
    '''Entity detail returns the resolved logo URL.'''
    response = public_client.get('/v1/cms/public/entities/e2')
    assert response.status_code == 200
    body = response.json()
    assert body['name'] == 'COMIBOL'
    assert body['logo_url'] == (
        'https://cms-bucket.s3.amazonaws.com/entities/comibol.png')


def test_public_entity_detail_hides_inactive(public_client, seeded):
    '''Inactive entities must 404.'''
    assert public_client.get('/v1/cms/public/entities/e3').status_code == 404
