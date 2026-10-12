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

from schemas.ai import (
    ExplainRequest,
    ExplainResponse,
    RoleActiveRequest,
    RoleDefinition,
    RoleListResponse,
    RoleSummary,
    ViewName
)
from controllers import ai as controllers


def test_explain_controller_returns_its_model():
    '''The explain endpoint answers a fully built ExplainResponse.'''
    async def _explain(
        view, # pylint: disable=unused-argument
        data # pylint: disable=unused-argument
    ):
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


def test_get_role_controller_returns_its_model():
    '''One version of a role answers a fully built RoleDefinition.'''
    async def _role(
        view,
        version
    ):
        return {'view': view, 'version': version, 'role': 'Asesor.',
                'instructions': 'Explica.', 'rules': ['No inventes.'], 'max_tokens': 400,
                'model_id': 'us.anthropic.claude-haiku-4-5-20251001-v1:0', 'active': False}

    with patch.object(controllers, 'get_role_service', _role):
        response = asyncio.run(controllers.get_role_controller(
            view = ViewName.SALE_SCENARIO, version = 2, current_user = 'tester', request = None
        ))

    assert isinstance(response, RoleDefinition)
    assert response.rules == ['No inventes.']


def test_set_role_active_controller_returns_its_model():
    '''Switching a version answers a fully built RoleSummary.'''
    async def _switch(
        view,
        version,
        active
    ):
        return {'view': view, 'version': version, 'role': 'Asesor.',
                'model_id': 'us.anthropic.claude-haiku-4-5-20251001-v1:0', 'active': active}

    with patch.object(controllers, 'set_role_active_service', _switch):
        response = asyncio.run(controllers.set_role_active_controller(
            view = ViewName.SALE_SCENARIO, version = 2,
            change = RoleActiveRequest(active = False), current_user = 'tester', request = None
        ))

    assert isinstance(response, RoleSummary)
    assert response.active is False


def test_save_role_controller_returns_its_model():
    '''Storing a version answers a fully built RoleSummary.'''
    async def _save(definition):
        return {key: definition[key] for key in ('view', 'version', 'role', 'model_id', 'active')}

    definition = RoleDefinition(view = ViewName.SALE_SCENARIO, version = 3, role = 'Asesor.',
                                instructions = 'Explica.', max_tokens = 400,
                                model_id = 'us.anthropic.claude-haiku-4-5-20251001-v1:0')
    with patch.object(controllers, 'save_role_service', _save):
        response = asyncio.run(controllers.save_role_controller(
            definition = definition, current_user = 'tester', request = None
        ))

    assert isinstance(response, RoleSummary)
    assert response.version == 3
