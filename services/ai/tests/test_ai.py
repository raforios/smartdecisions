'''
    Tests for the AI interpretation domain.

    The model itself is never called here: what these cover is everything around
    it, which is where the failures that matter live. A role nobody configured, a
    cache that serves an answer written under a different set of rules, a backend
    response that arrives trimmed — none of those show up as an error from the
    provider. They show up as a confident explanation of the wrong thing.
'''
import asyncio
from unittest.mock import patch

import pytest

from fastapi import HTTPException

from models.ai import PromptItem
from schemas.ai import AIError, ViewName
from services import ai
from services.ai_utils import build_cache_key


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
        view = ViewName.RATE_FORECAST.value,
        version = version,
        role = 'Analista cambiario.',
        instructions = 'Explica la serie.',
        rules = ['No inventes cifras.'],
        max_tokens = 500,
        model_id = 'us.anthropic.claude-haiku-4-5-20251001-v1:0',
        active = True,
        created_at = '2026-09-06T10:00:00+00:00'
    )


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
    with patch.object(ai, 'get_active_prompt', lambda view: None):
        with pytest.raises(HTTPException) as failure:
            _run(ai.explain_service(ViewName.RATE_FORECAST, RATE_VIEW))

    assert AIError.ROLE_NOT_CONFIGURED.value in str(failure.value.detail)
    assert not model


def test_an_empty_payload_is_refused(model):
    '''
        Nothing to explain is not an explanation. The view must send what the
        backend answered, and an empty object means the caller has nothing.
    '''
    with patch.object(ai, 'get_active_prompt', lambda view: _prompt()):
        with pytest.raises(HTTPException) as failure:
            _run(ai.explain_service(ViewName.RATE_FORECAST, {}))

    assert AIError.EMPTY_PAYLOAD.value in str(failure.value.detail)
    assert not model


def test_the_backend_response_travels_whole(model, cache): # pylint: disable=unused-argument
    '''
        The input is the response of the producing service, untouched.

        Re-declaring its shape here would be a second contract for one thing,
        and would drop fields the expert could have used — including ones added
        by a service after this one was written.
    '''
    answered = dict(RATE_VIEW, campo_nuevo = 'agregado por otro servicio')

    with patch.object(ai, 'get_active_prompt', lambda view: _prompt()):
        _run(ai.explain_service(ViewName.RATE_FORECAST, answered))

    sent = model[0]['user_prompt']
    assert 'campo_nuevo' in sent
    assert 'agregado por otro servicio' in sent
    assert '12.58' in sent


def test_an_oversized_payload_is_refused_before_anything_else(model):
    '''
        A screen that grew unexpectedly must not become a bill that grew
        unexpectedly, and the check happens before validation so a large
        malformed payload is not parsed either.
    '''
    huge = dict(RATE_VIEW, history = [{'date': '2026-09-05', 'rate': 12.5}] * 20000)

    with patch.object(ai, 'get_active_prompt', lambda view: _prompt()):
        with pytest.raises(HTTPException) as failure:
            _run(ai.explain_service(ViewName.RATE_FORECAST, huge))

    assert AIError.PAYLOAD_TOO_LARGE.value in str(failure.value.detail)
    assert not model


def test_a_second_identical_request_is_served_from_cache(model, cache):
    '''
        A demo clicks the same button repeatedly. The difference between a
        fresh answer and a stored one is the difference between paying for it
        and not.
    '''
    with patch.object(ai, 'get_active_prompt', lambda view: _prompt()):
        first = _run(ai.explain_service(ViewName.RATE_FORECAST, RATE_VIEW))
        second = _run(ai.explain_service(ViewName.RATE_FORECAST, RATE_VIEW))

    assert first['cached'] is False
    assert second['cached'] is True
    assert second['text'] == first['text']
    # The model was asked once, not twice.
    assert len(model) == 1
    assert len(cache) == 1


def test_retuning_the_role_stops_serving_what_the_old_one_produced(model, cache): # pylint: disable=unused-argument
    '''
        The prompt version is part of the cache key, so a retuned role does not
        keep answering with text written under the previous rules — and nothing
        has to be deleted for that to hold.
    '''
    with patch.object(ai, 'get_active_prompt', lambda view: _prompt(version = 1)):
        _run(ai.explain_service(ViewName.RATE_FORECAST, RATE_VIEW))

    with patch.object(ai, 'get_active_prompt', lambda view: _prompt(version = 2)):
        after = _run(ai.explain_service(ViewName.RATE_FORECAST, RATE_VIEW))

    assert after['cached'] is False
    assert after['prompt_version'] == 2
    assert len(model) == 2


def test_a_model_that_says_nothing_is_not_published_as_an_answer(cache): # pylint: disable=unused-argument
    '''
        A refusal carries no text block. Returning an empty explanation would
        put a blank box on the screen as if it were a finding.
    '''
    def _silent(**kwargs): # pylint: disable=unused-argument
        return {'text': '', 'input_tokens': 100, 'output_tokens': 0}

    with patch.object(ai, 'get_active_prompt', lambda view: _prompt()), \
         patch.object(ai, 'invoke', _silent):
        with pytest.raises(HTTPException) as failure:
            _run(ai.explain_service(ViewName.RATE_FORECAST, RATE_VIEW))

    assert AIError.MODEL_REFUSED.value in str(failure.value.detail)


def test_the_prompt_carries_the_role_and_every_rule(model, cache): # pylint: disable=unused-argument
    '''
        The rules are what keep the answers honest — not inventing figures, not
        recommending. If they stopped reaching the model nothing would break
        visibly; the answers would just start drifting.
    '''
    prompt = _prompt()
    with patch.object(ai, 'get_active_prompt', lambda view: prompt):
        _run(ai.explain_service(ViewName.RATE_FORECAST, RATE_VIEW))

    system = model[0]['system_prompt']
    assert prompt.role in system
    assert prompt.instructions in system
    for rule in prompt.rules:
        assert rule in system


def test_an_oversized_payload_is_measured_as_json(model):
    '''
        The ceiling is on what actually travels, so it is measured on the
        serialised payload and not on the Python object's repr.
    '''
    huge = dict(RATE_VIEW, history = [{'date': '2026-09-05', 'rate': 12.5}] * 5000)

    with patch.object(ai, 'get_active_prompt', lambda view: _prompt()):
        with pytest.raises(HTTPException) as failure:
            _run(ai.explain_service(ViewName.RATE_FORECAST, huge))

    assert AIError.PAYLOAD_TOO_LARGE.value in str(failure.value.detail)
    assert not model


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
         patch.object(ai, 'list_prompts', lambda: [old]):
        result = _run(ai.save_role_service({
            'view': ViewName.RATE_FORECAST.value,
            'version': 2,
            'role': 'Analista cambiario, versión afinada.',
            'instructions': 'Explica la serie.',
            'rules': ['No inventes cifras.', 'No infieras el día de la semana.'],
            'max_tokens': 500,
            'model_id': 'us.anthropic.claude-haiku-4-5-20251001-v1:0',
            'active': True,
        }))

    assert result['version'] == 2
    assert result['active'] is True
    assert retired == [1]
    # The old version is still there, not deleted.
    assert (ViewName.RATE_FORECAST.value, 1) in stored
