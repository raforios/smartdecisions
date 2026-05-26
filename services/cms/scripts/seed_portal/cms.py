'''
    CMS admin client used by the seeder.

    Targets the /v1/cms/admin/* endpoints with a Bearer token. Exposes
    only the methods the seeder needs (list/create/delete per entity).
'''
from typing import Any, Dict, List, Optional
import requests


class CmsAdminClient:
    '''
        Minimal wrapper around the CMS admin endpoints.
    '''

    def __init__(self, base_url: str, token: str, timeout: int = 20):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.timeout = timeout

    # ---------- News ----------
    def list_news(self) -> List[Dict[str, Any]]:
        return self._get('/news').get('items', [])

    def create_news(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._post('/news', payload)

    def delete_news(self, news_id: str) -> None:
        self._delete(f'/news/{news_id}')

    # ---------- Documents ----------
    def list_documents(self) -> List[Dict[str, Any]]:
        return self._get('/documents').get('items', [])

    def create_document(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._post('/documents', payload)

    def delete_document(self, document_id: str) -> None:
        self._delete(f'/documents/{document_id}')

    # ---------- Entities ----------
    def list_entities(self) -> List[Dict[str, Any]]:
        return self._get('/entities').get('items', [])

    def create_entity(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._post('/entities', payload)

    def delete_entity(self, entity_id: str) -> None:
        self._delete(f'/entities/{entity_id}')

    # ---------- Low-level ----------
    def _headers(self, content_json: bool = False) -> Dict[str, str]:
        headers = {
            'Authorization': f'Bearer {self.token}',
            'Accept': 'application/json',
        }
        if content_json:
            headers['Content-Type'] = 'application/json'
        return headers

    def _get(self, path: str) -> Dict[str, Any]:
        url = f'{self.base_url}/admin{path}'
        response = requests.get(url, headers = self._headers(),
                                timeout = self.timeout)
        return _unwrap(response)

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f'{self.base_url}/admin{path}'
        response = requests.post(url, headers = self._headers(content_json = True),
                                 json = payload, timeout = self.timeout)
        return _unwrap(response)

    def _delete(self, path: str) -> Optional[Dict[str, Any]]:
        url = f'{self.base_url}/admin{path}'
        response = requests.delete(url, headers = self._headers(),
                                   timeout = self.timeout)
        return _unwrap(response)


def _unwrap(response) -> Dict[str, Any]:
    '''
        Returns the JSON body on success; raises with the server's detail
        on failure so callers see a meaningful error.
    '''
    if response.ok:
        if response.status_code == 204 or not response.text:
            return {}
        return response.json()
    detail = _format_detail(response)
    raise RuntimeError(f'CMS admin {response.request.method} '
                       f'{response.url} → {detail}')


def _format_detail(response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f'HTTP {response.status_code}'
    detail = payload.get('detail')
    if isinstance(detail, list):
        return '; '.join(
            f'{".".join(str(x) for x in d.get("loc", []))}: {d.get("msg")}'
            for d in detail
        )
    if isinstance(detail, str):
        return detail
    return f'HTTP {response.status_code}: {payload}'
