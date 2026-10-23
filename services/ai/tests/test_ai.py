'''
    Tests for the AI interpretation domain.

    The model itself is never called here: what these cover is everything around
    it, which is where the failures that matter live. A role nobody configured, a
    cache that serves an answer written under a different set of rules, a backend
    response that arrives trimmed — none of those show up as an error from the
    provider. They show up as a confident explanation of the wrong thing.
'''
import asyncio
from dataclasses import replace
from unittest.mock import patch

import pytest

from fastapi import HTTPException

from models.ai import PromptItem
from schemas.ai import AIError, PromptCaller
from services import ai, ai_utils
from services.ai_utils import build_cache_key

# The ADMIN writes the general roles; a manager, those of their company.
ADMIN = PromptCaller(owner = 'admin@bearsoft.com.bo', role = 'ADMIN')
MANAGER = PromptCaller(owner = 'acme', role = 'MANAGER')


def _run(coroutine):
    '''
        Runs a coroutine, the way the sibling services' tests do.

        Args:
            coroutine: The coroutine to execute.

        Returns:
            Any: Whatever the coroutine returns.
    '''
    return asyncio.run(coroutine)


def _prompt(version: int = 1) -> PromptItem:
    '''
        A configured role.

        Args:
            version (int): Version to build.

        Returns:
            PromptItem: The role.
    '''
    return PromptItem(
        view = 'rate_forecast',
        version = version,
        role = 'Analista cambiario.',
        instructions = 'Explica la serie.',
        rules = ['No inventes cifras.'],
        max_tokens = 500,
        model_id = 'us.anthropic.claude-haiku-4-5-20251001-v1:0',
        active = True,
        created_at = '2026-09-06T10:00:00+00:00'
    )


# What PARAMETERS answers for the `ai` scope (docs/parametros.md).
SETTINGS = ai.ExplainSettings(cache_hours = 24, max_payload_characters = 40000,
                              sample_size = 25, question = '¿Qué significa esto?',
                              temperature = 0.2)

# The real reader, kept before the fixture below replaces it in every test.
real_explain_settings = ai.explain_settings


@pytest.fixture(autouse = True)
def _settings():
    '''
        Every explanation reads its settings as if PARAMETERS answered.

        Yields:
            None: The patch stays active for the test.
    '''
    with patch.object(ai, 'explain_settings', lambda auth_token: SETTINGS):
        yield


RATE_VIEW = {
    'currency': 'USD',
    'days_ahead': 30,
    'confidence': 'MEDIUM',
    'last_rate': 12.58,
    'last_date': '2026-09-05',
    'valid_from': '2026-09-05',
    'valid_to': '2026-09-07',
    'final_rate': 12.79,
}


@pytest.fixture(name = 'model')
def _model():
    '''
        Replaces Bedrock with a recorder.

        Yields:
            list: The calls the domain made, so a test can read the prompt it
                would have sent without paying for a token.
    '''
    calls = []

    def _invoke(**kwargs):
        calls.append(kwargs)
        return {'text': 'Una explicación.', 'input_tokens': 100, 'output_tokens': 20}

    with patch.object(ai, 'invoke', _invoke):
        yield calls


@pytest.fixture(name = 'cache')
def _cache():
    '''
        Replaces the cache table with a dictionary.

        Yields:
            dict: What was stored, keyed by cache key.
    '''
    stored = {}

    with patch.object(ai, 'get_cached', stored.get), \
         patch.object(ai, 'put_cached',
                      lambda item: stored.__setitem__(item.cache_key, item)):
        yield stored


def test_an_unconfigured_view_is_refused_before_reaching_the_model(model):
    '''
        Without a role there is nothing to write from, and answering anyway
        would mean the model inventing its own voice.
    '''
    with patch.object(ai, 'get_active_prompt', lambda view, owner: None):
        with pytest.raises(HTTPException) as failure:
            _run(ai.explain_service('rate_forecast', RATE_VIEW, None, 'acme'))

    assert AIError.ROLE_NOT_CONFIGURED.value in str(failure.value.detail)
    assert not model


def test_an_empty_payload_is_refused(model):
    '''
        Nothing to explain is not an explanation. The view must send what the
        backend answered, and an empty object means the caller has nothing.
    '''
    with patch.object(ai, 'get_active_prompt', lambda view, owner: _prompt()):
        with pytest.raises(HTTPException) as failure:
            _run(ai.explain_service('rate_forecast', {}, None, 'acme'))

    assert AIError.EMPTY_PAYLOAD.value in str(failure.value.detail)
    assert not model


def test_the_backend_response_travels_whole(
    model, # pylint: disable=unused-argument
    cache # pylint: disable=unused-argument
):
    '''
        The input is the response of the producing service, untouched.

        Re-declaring its shape here would be a second contract for one thing,
        and would drop fields the expert could have used — including ones added
        by a service after this one was written.
    '''
    answered = dict(RATE_VIEW, campo_nuevo = 'agregado por otro servicio')

    with patch.object(ai, 'get_active_prompt', lambda view, owner: _prompt()):
        _run(ai.explain_service('rate_forecast', answered, None, 'acme'))

    sent = model[0]['user_prompt']
    assert 'campo_nuevo' in sent
    assert 'agregado por otro servicio' in sent
    assert '12.58' in sent



def test_a_second_identical_request_is_served_from_cache(
    model,
    cache
):
    '''
        A demo clicks the same button repeatedly. The difference between a
        fresh answer and a stored one is the difference between paying for it
        and not.
    '''
    with patch.object(ai, 'get_active_prompt', lambda view, owner: _prompt()):
        first = _run(ai.explain_service('rate_forecast', RATE_VIEW, None, 'acme'))
        second = _run(ai.explain_service('rate_forecast', RATE_VIEW, None, 'acme'))

    assert first['cached'] is False
    assert second['cached'] is True
    assert second['text'] == first['text']
    # The model was asked once, not twice.
    assert len(model) == 1
    assert len(cache) == 1


def test_retuning_the_role_stops_serving_what_the_old_one_produced(
    model, # pylint: disable=unused-argument
    cache # pylint: disable=unused-argument
):
    '''
        The prompt version is part of the cache key, so a retuned role does not
        keep answering with text written under the previous rules — and nothing
        has to be deleted for that to hold.
    '''
    with patch.object(ai, 'get_active_prompt', lambda view, owner: _prompt(version = 1)):
        _run(ai.explain_service('rate_forecast', RATE_VIEW, None, 'acme'))

    with patch.object(ai, 'get_active_prompt', lambda view, owner: _prompt(version = 2)):
        after = _run(ai.explain_service('rate_forecast', RATE_VIEW, None, 'acme'))

    assert after['cached'] is False
    assert after['prompt_version'] == 2
    assert len(model) == 2


def test_a_model_that_says_nothing_is_not_published_as_an_answer(
    cache # pylint: disable=unused-argument
):
    '''
        A refusal carries no text block. Returning an empty explanation would
        put a blank box on the screen as if it were a finding.
    '''
    def _silent(
        **kwargs # pylint: disable=unused-argument
    ):
        return {'text': '', 'input_tokens': 100, 'output_tokens': 0}

    with patch.object(ai, 'get_active_prompt', lambda view, owner: _prompt()), \
         patch.object(ai, 'invoke', _silent):
        with pytest.raises(HTTPException) as failure:
            _run(ai.explain_service('rate_forecast', RATE_VIEW, None, 'acme'))

    assert AIError.MODEL_REFUSED.value in str(failure.value.detail)


def test_the_prompt_carries_the_role_and_every_rule(
    model, # pylint: disable=unused-argument
    cache # pylint: disable=unused-argument
):
    '''
        The rules are what keep the answers honest — not inventing figures, not
        recommending. If they stopped reaching the model nothing would break
        visibly; the answers would just start drifting.
    '''
    prompt = _prompt()
    with patch.object(ai, 'get_active_prompt', lambda view, owner: prompt):
        _run(ai.explain_service('rate_forecast', RATE_VIEW, None, 'acme'))

    system = model[0]['system_prompt']
    assert prompt.role in system
    assert prompt.instructions in system
    for rule in prompt.rules:
        assert rule in system



def test_the_cache_key_changes_with_every_input_that_changes_the_answer():
    '''
        View, payload and prompt version each change the answer, so each must
        change the key. A key that ignored one of them would serve an answer
        written for something else.
    '''
    base = build_cache_key('rate_forecast', RATE_VIEW, 1)

    assert base == build_cache_key('rate_forecast', dict(RATE_VIEW), 1)
    assert base != build_cache_key('minerals_forecast', RATE_VIEW, 1)
    assert base != build_cache_key('rate_forecast', dict(RATE_VIEW, last_rate = 12.59), 1)
    assert base != build_cache_key('rate_forecast', RATE_VIEW, 2)


def test_the_cache_key_does_not_depend_on_key_order():
    '''
        Two identical screens must produce the same key regardless of the order
        the browser happened to serialise them in, or the cache would never hit.
    '''
    forwards = {'a': 1, 'b': 2, 'c': 3}
    backwards = {'c': 3, 'b': 2, 'a': 1}

    assert build_cache_key('v', forwards, 1) == build_cache_key('v', backwards, 1)


def test_storing_a_role_retires_the_previous_version():
    '''
        Only one version of a view is in force.

        The older ones stay — that is the point of versioning — but marked
        inactive, so a rollback is flipping a flag and nothing is ever restored.
    '''
    stored, retired = {}, []

    def _put(prompt):
        stored[(prompt.view, prompt.version)] = prompt
        if not prompt.active:
            retired.append(prompt.version)

    old = _prompt(version = 1)
    with patch.object(ai, 'put_prompt', _put), \
         patch.object(ai, 'next_version', lambda view: 2), \
         patch.object(ai, 'list_prompts', lambda: [old]):
        result = _run(ai.save_role_service({
            'view': 'rate_forecast',
            'version': 2,
            'role': 'Analista cambiario, versión afinada.',
            'instructions': 'Explica la serie.',
            'rules': ['No inventes cifras.', 'No infieras el día de la semana.'],
            'max_tokens': 500,
            'model_id': 'us.anthropic.claude-haiku-4-5-20251001-v1:0',
            'active': True,
        }, ADMIN))

    assert result['version'] == 2
    assert result['active'] is True
    assert retired == [1]
    # The old version is still there, not deleted.
    assert ('rate_forecast', 1) in stored


def test_a_long_response_is_sampled_instead_of_refused(
    model, # pylint: disable=unused-argument
    cache # pylint: disable=unused-argument
):
    """
        Some responses are long by nature — the opportunities run answers with
        545 rows and 246 KB. Refusing it leaves the button broken on the screen
        where it is most useful, and sending it whole costs a fortune for a
        worse explanation: nobody reads 545 rows.
    """
    huge = dict(RATE_VIEW, history = [
        {'date': '2026-09-05', 'rate': 12.5, 'relleno': 'x' * 60} for _ in range(3000)
    ])

    with patch.object(ai, 'get_active_prompt', lambda view, owner: _prompt()):
        result = _run(ai.explain_service('rate_forecast', huge, None, 'acme'))

    assert result['text']
    sent = model[0]['user_prompt']
    assert len(sent) <= SETTINGS.max_payload_characters + 500
    # The model must be told it is looking at a sample, or it would describe it
    # as if it were the whole.
    # The model must be told it is looking at a sample, or it would describe it
    # as if it were the whole.
    assert 'no mostrados' in sent


def test_a_response_that_fits_is_not_touched(
    model, # pylint: disable=unused-argument
    cache # pylint: disable=unused-argument
):
    """Trimming is a last resort, not something that happens on every call."""
    with patch.object(ai, 'get_active_prompt', lambda view, owner: _prompt()):
        _run(ai.explain_service('rate_forecast', RATE_VIEW, None, 'acme'))

    sent = model[0]['user_prompt']
    assert 'muestra' not in sent
    assert '12.58' in sent


def test_an_empty_payload_is_still_refused(model):
    """Nothing to explain is not an explanation."""
    with patch.object(ai, 'get_active_prompt', lambda view, owner: _prompt()):
        with pytest.raises(HTTPException) as failure:
            _run(ai.explain_service('rate_forecast', {}, None, 'acme'))

    assert AIError.EMPTY_PAYLOAD.value in str(failure.value.detail)
    assert not model


def test_a_long_list_is_trimmed_at_any_depth(
    model, # pylint: disable=unused-argument
    cache # pylint: disable=unused-argument
):
    """
        A route plan is days[].stops[]: trimming only the top level cut a list
        of five and left eighty thousand stops underneath, which reached the
        model as 218 000 tokens against a limit of 200 000 and failed outright.
    """
    nested = {
        'route_id': 1,
        'days': [
            {'day': day, 'stops': [{'client': f'Cliente {i}', 'amount': 100.0,
                                    'relleno': 'x' * 80} for i in range(500)]}
            for day in range(1, 6)
        ]
    }

    with patch.object(ai, 'get_active_prompt', lambda view, owner: _prompt()):
        _run(ai.explain_service('rate_forecast', nested, None, 'acme'))

    sent = model[0]['user_prompt']
    assert len(sent) <= SETTINGS.max_payload_characters + 500
    assert 'no mostrados' in sent
    # The structure survives: it is still days with stops, only shorter.
    assert 'stops' in sent and 'Cliente 0' in sent


def test_a_role_is_read_whole_to_be_edited():
    '''The editor needs the instructions and every rule, not the summary.'''
    with patch.object(ai, 'get_prompt', lambda view, version: _prompt(version)):
        role = _run(ai.get_role_service('rate_forecast', 3, ADMIN))

    assert role['version'] == 3
    assert role['instructions'] == 'Explica la serie.'
    assert role['rules'] == ['No inventes cifras.']


def test_a_version_that_does_not_exist_answers_not_found():
    '''Reading or switching a missing version is a 404 with its code.'''
    with patch.object(ai, 'get_prompt', lambda view, version: None):
        with pytest.raises(HTTPException) as raised:
            _run(ai.get_role_service('rate_forecast', 9, ADMIN))

    assert raised.value.status_code == 404
    assert raised.value.detail == AIError.ROLE_NOT_FOUND.value


def test_turning_a_version_on_retires_the_one_in_force():
    '''Rolling back is turning the old version on: the newer one goes off.'''
    stored = {}
    old, new = replace(_prompt(1), active = False), _prompt(2)
    with patch.object(ai, 'get_prompt', lambda view, version: {1: old, 2: new}[version]), \
         patch.object(ai, 'put_prompt',
                      lambda prompt: stored.__setitem__(prompt.version, prompt.active)), \
         patch.object(ai, 'list_prompts', lambda: [old, new]):
        result = _run(ai.set_role_active_service('rate_forecast', 1, True, ADMIN))

    assert result['active'] is True
    assert stored == {1: True, 2: False}


def test_turning_a_version_off_touches_nothing_else():
    '''Deactivating leaves the view without a role; nothing else changes.'''
    stored = {}
    with patch.object(ai, 'get_prompt', lambda view, version: _prompt(version)), \
         patch.object(ai, 'put_prompt',
                      lambda prompt: stored.__setitem__(prompt.version, prompt.active)), \
         patch.object(ai, 'list_prompts', lambda: [_prompt(1)]):
        _run(ai.set_role_active_service('rate_forecast', 2, False, ADMIN))

    assert stored == {2: False}


def test_settings_are_read_from_parameters():
    '''The five values come from the `ai` scope, typed as the code uses them.'''
    answered = {'EXPLANATION_CACHE_HOURS': 24.0, 'MAX_PAYLOAD_CHARACTERS': 40000.0,
                'LIST_SAMPLE_SIZE': 25.0, 'EXPLANATION_QUESTION': '¿Qué significa esto?',
                'BEDROCK_TEMPERATURE': 0.2}
    asked = []

    def _read(
        scope,
        auth_token
    ):
        asked.append((scope, auth_token))
        return answered

    with patch.object(ai, 'read_parameters', _read):
        settings = real_explain_settings('Bearer token')
    assert asked == [('ai', 'Bearer token')]
    assert settings == SETTINGS
    assert isinstance(settings.sample_size, int)


def test_a_missing_setting_stops_the_explanation():
    '''No value is invented: a missing one answers PARAMETER_MISSING.'''
    with patch.object(ai, 'read_parameters', lambda scope, auth_token: {}):
        with pytest.raises(HTTPException) as raised:
            real_explain_settings('Bearer token')
    assert raised.value.detail == 'PARAMETER_MISSING'


def test_the_configured_temperature_reaches_the_model(
    model,
    cache # pylint: disable=unused-argument
):
    '''The temperature is the one in PARAMETERS, not a number in the code.'''
    with patch.object(ai, 'get_active_prompt', lambda view, owner: _prompt()):
        _run(ai.explain_service('rate_forecast', RATE_VIEW, None, 'acme'))
    assert model[0]['temperature'] == SETTINGS.temperature


# ---------- Roles per company (Rafael, 21-oct) ----------

ROLE_BODY = {'view': 'rate_forecast', 'version': 1, 'role': 'Analista de acme.',
             'instructions': 'Explica la serie.', 'rules': [], 'max_tokens': 500,
             'model_id': 'us.anthropic.claude-haiku-4-5-20251001-v1:0', 'active': True}


def test_a_company_role_wins_and_the_general_one_is_the_default():
    '''acme gets its own role in force; any other company, the general one.'''
    general = _prompt(1)
    own = replace(_prompt(2), client = 'acme')
    retired = replace(_prompt(3), client = 'acme', active = False)
    with patch.object(ai_utils, '_versions', lambda view: [retired, own, general]):
        assert ai_utils.get_active_prompt('rate_forecast', 'acme') == own
        assert ai_utils.get_active_prompt('rate_forecast', 'other') == general


def test_the_next_version_counts_every_company():
    '''Numbers are per view across companies, so no one writes over another.'''
    stored = [_prompt(1), replace(_prompt(4), client = 'other')]
    with patch.object(ai_utils, '_versions', lambda view: stored):
        assert ai_utils.next_version('rate_forecast') == 5


def test_a_manager_stores_for_their_company_and_retires_only_theirs():
    '''The company comes from the token; the general role stays in force.'''
    general = _prompt(1)
    older = replace(_prompt(2), client = 'acme')
    written = []
    with patch.object(ai, 'put_prompt', written.append), \
         patch.object(ai, 'next_version', lambda view: 3), \
         patch.object(ai, 'list_prompts', lambda: [general, older]):
        result = _run(ai.save_role_service({**ROLE_BODY, 'client': 'intruso'}, MANAGER))
    assert (result['version'], result['client']) == (3, 'acme')
    assert [(prompt.version, prompt.active) for prompt in written] == [(3, True), (2, False)]


def test_only_the_admin_and_managers_write_roles():
    '''A query user is refused before anything is stored.'''
    reader = PromptCaller(owner = 'acme', role = 'REQUESTER')
    with patch.object(ai, 'put_prompt', pytest.fail):
        with pytest.raises(HTTPException) as refused:
            _run(ai.save_role_service(ROLE_BODY, reader))
    assert refused.value.status_code == 403


def test_a_manager_sees_the_general_roles_and_theirs_only():
    '''Another company's role is left out of the list.'''
    stored = [_prompt(1), replace(_prompt(2), client = 'acme'),
              replace(_prompt(3), client = 'other')]
    with patch.object(ai, 'list_prompts', lambda: stored):
        listed = _run(ai.list_roles_service(MANAGER))
        everything = _run(ai.list_roles_service(ADMIN))
    assert [role['version'] for role in listed['roles']] == [1, 2]
    assert everything['count'] == 3


def test_another_company_role_answers_like_one_that_does_not_exist():
    '''Same 404 as a missing version: nothing says it exists.'''
    with patch.object(ai, 'get_prompt', lambda view, version: replace(_prompt(5),
                                                                       client = 'other')):
        with pytest.raises(HTTPException) as hidden:
            _run(ai.get_role_service('rate_forecast', 5, MANAGER))
    assert hidden.value.detail == AIError.ROLE_NOT_FOUND.value


def test_a_manager_cannot_switch_the_general_role():
    '''They may read it to start theirs from it, never turn it off.'''
    with patch.object(ai, 'get_prompt', lambda view, version: _prompt(1)), \
         patch.object(ai, 'put_prompt', pytest.fail):
        with pytest.raises(HTTPException) as refused:
            _run(ai.set_role_active_service('rate_forecast', 1, False, MANAGER))
    assert refused.value.status_code == 403


def test_the_admin_deletes_a_company_role():
    '''The deleted version is reported with its company.'''
    deleted = []
    with patch.object(ai, 'get_prompt', lambda view, version: replace(_prompt(7),
                                                                       client = 'acme')), \
         patch.object(ai, 'delete_prompt', lambda view, version: deleted.append(version)):
        result = _run(ai.delete_role_service('rate_forecast', 7, ADMIN))
    assert (deleted, result['client']) == ([7], 'acme')
