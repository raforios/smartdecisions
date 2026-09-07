'''
    Controller-level tests: every AI endpoint must return its response model
    fully built.

    These exist because of a real production failure in the sibling services:
    the services were changed to return DTOs while the controllers still spread
    them with `**`, which raises TypeError only when the endpoint runs. The
    domain stayed green and the API returned 500.
'''
import asyncio
from unittest.mock import patch

from schemas.ai import ExplainRequest, ExplainResponse, RoleListResponse, ViewName
from controllers import ai as controllers


def test_explain_controller_returns_its_model():
    '''The explain endpoint answers a fully built ExplainResponse.'''
    async def _explain(view, data): # pylint: disable=unused-argument
        return {
            'view': ViewName.RATE_FORECAST,
            'text': 'Una explicación.',
            'role': 'Analista cambiario.',
            'model': 'us.anthropic.claude-haiku-4-5-20251001-v1:0',
            'prompt_version': 2,
            'cached': False,
            'generated_at': '2026-09-06T10:00:00+00:00',
        }

    with patch.object(controllers, 'explain_service', _explain):
        response = asyncio.run(controllers.explain_controller(
            payload = ExplainRequest(view = ViewName.RATE_FORECAST, data = {'currency': 'USD'}),
            current_user = 'tester',
            request = None
        ))

    assert isinstance(response, ExplainResponse)
    assert response.prompt_version == 2
    assert response.cached is False


def test_roles_controller_returns_its_model():
    '''The roles endpoint answers a fully built RoleListResponse.'''
    async def _roles():
        return {
            'count': 1,
            'roles': [{
                'view': ViewName.SALE_SCENARIO,
                'version': 2,
                'role': 'Asesor comercial.',
                'model_id': 'us.anthropic.claude-haiku-4-5-20251001-v1:0',
                'active': True,
            }],
        }

    with patch.object(controllers, 'list_roles_service', _roles):
        response = asyncio.run(controllers.list_roles_controller(
            current_user = 'tester', request = None
        ))

    assert isinstance(response, RoleListResponse)
    assert response.count == 1
    assert response.roles[0].view is ViewName.SALE_SCENARIO
