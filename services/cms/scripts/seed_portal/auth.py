'''
    AUTH microservice client used by the seeder.

    Exchanges email + password for the JWT that grants access to the CMS
    admin and FILES upload endpoints. Token lives in memory only.
'''
import requests


class AuthClient:
    '''
        Thin wrapper around POST /v1/auth/login.
    '''

    def __init__(self, base_url: str, timeout: int = 15):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout

    def login(self, email: str, password: str) -> str:
        '''
            Returns the access token. Raises RuntimeError on failure.
        '''
        response = requests.post(
            f'{self.base_url}/login',
            json = {'email': email, 'password': password},
            timeout = self.timeout,
        )
        if not response.ok:
            detail = _detail_or_status(response)
            raise RuntimeError(f'AUTH login failed: {detail}')
        token = response.json().get('access_token')
        if not token:
            raise RuntimeError('AUTH responded without access_token.')
        return token


def _detail_or_status(response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f'HTTP {response.status_code}'
    detail = payload.get('detail')
    if isinstance(detail, str):
        return detail
    return f'HTTP {response.status_code}: {payload}'
