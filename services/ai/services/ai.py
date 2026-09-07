'''
    AI interpretation domain — main module.

    Every other service in SmartDecisions answers with data and stable codes:
    `INSUFFICIENT`, `DAMPED_TREND`, `is_fallback`. The frontend turns the short
    ones into labels. What it cannot do is *explain* — why one mineral's
    projection is trusted and another's is not, or what it means that the next
    official quotation is still partial. That is what this service is for.

    Three rules shape it:

      1. **It explains what it is given, and nothing else.** No database access,
         no tools, no fetching. If a figure is not on the screen it is not in the
         answer.
      2. **It reads what the backend answered, untouched.** The input is the
         JSON the producing service returned — the same object its own Pydantic
         model built. Re-declaring that shape here would create two contracts
         for one thing and would hide fields the expert could have used.
      3. **The role lives in the database.** The wording is what gets tuned
         most, and tuning it must not need a release.
'''
import json
from dataclasses import replace
from datetime import timedelta
from typing import Any, Dict

from models.ai import ExplanationItem, PromptItem
from schemas.ai import AIError, ViewName
from services.ai_utils import (
    build_cache_key,
    get_active_prompt,
    get_cached,
    list_prompts,
    put_cached,
    put_prompt
)
from services.bedrock_client import invoke
from services.environment import load_and_validate_env_vars
from services.exceptions import (
    InvalidInputError,
    RegisterNotFoundError,
    ServiceUnavailableError
)
from services.logger_config import custom_logger as logger
from services.utils import get_current_time_gmt, handle_service_errors


ENV_VARS = load_and_validate_env_vars({
    'EXPLANATION_CACHE_HOURS': int,
    'MAX_PAYLOAD_CHARACTERS': int,
})

# How long an answer stays valid. A day, because the figures underneath move by
# fortnight for minerals and by day for the exchange rate.
CACHE_HOURS = ENV_VARS['EXPLANATION_CACHE_HOURS']

# Ceiling on what a view may send. A screen that grew unexpectedly must not
# turn into an unexpectedly large bill, and it is also the crudest defence
# against somebody pushing a large payload through the endpoint.
MAX_PAYLOAD_CHARACTERS = ENV_VARS['MAX_PAYLOAD_CHARACTERS']

# The question every explanation answers. Fixed here rather than accepted from
# the caller: this endpoint explains a screen, it does not take instructions.
_QUESTION = '¿Qué significa esto?'


def _system_prompt(prompt: PromptItem) -> str:
    '''
        Assembles the role the answer is written from.

        The rules are numbered rather than run together: they are read by a
        person tuning them as much as by the model, and a numbered list is what
        makes adding one a single row instead of a rewrite.

        Args:
            prompt (PromptItem): The role in force.

        Returns:
            str: The system prompt.
    '''
    rules = '\n'.join(f'{index}. {rule}'
                      for index, rule in enumerate(prompt.rules, start = 1))
    return f'{prompt.role}\n\n{prompt.instructions}\n\nReglas:\n{rules}'


@handle_service_errors('AI')
async def explain_service(view: ViewName, data: Dict[str, Any]) -> Dict[str, Any]:
    '''
    Explains what a view is showing, from the point of view of its expert.

    Args:
        view (ViewName): View being explained.
        data (Dict[str, Any]): The payload the view is displaying.

    Returns:
        Dict[str, Any]: Payload matching ExplainResponse shape.

    Raises:
        InvalidInputError: If the payload is empty or too large.
        RegisterNotFoundError: If no role is configured for the view.
        ServiceUnavailableError: If the model cannot be reached or says nothing.
    '''
    if not data:
        raise InvalidInputError(detail = AIError.EMPTY_PAYLOAD.value)
    if len(json.dumps(data, default = str)) > MAX_PAYLOAD_CHARACTERS:
        raise InvalidInputError(detail = AIError.PAYLOAD_TOO_LARGE.value)

    # The payload travels as the producing service returned it. It already
    # passed a Pydantic model on the other side; re-declaring its shape here
    # would be a second contract for one thing, and would drop fields the
    # expert could have used.
    payload = data

    prompt = get_active_prompt(view.value)
    if prompt is None:
        error_msg = f'No active role is configured for {view.value}.'
        logger.warning(error_msg)
        raise RegisterNotFoundError(detail = AIError.ROLE_NOT_CONFIGURED.value)

    cache_key = build_cache_key(view.value, payload, prompt.version)
    cached = get_cached(cache_key)
    if cached is not None:
        message = f'Explanation of {view.value} served from cache.'
        logger.info(message)
        return {
            'view': view,
            'text': cached.text,
            'role': cached.role,
            'model': cached.model_id,
            'prompt_version': cached.prompt_version,
            'cached': True,
            'generated_at': cached.generated_at,
        }

    answer = invoke(
        model_id = prompt.model_id,
        system_prompt = _system_prompt(prompt),
        user_prompt = (f'Vista {view.value}, respuesta del backend:\n'
                       f'{json.dumps(payload, ensure_ascii = False, default = str)}'
                       f'\n\n{_QUESTION}'),
        max_tokens = prompt.max_tokens
    )
    if not answer['text']:
        error_msg = f'The model returned no text for {view.value}.'
        logger.error(error_msg)
        raise ServiceUnavailableError(detail = AIError.MODEL_REFUSED.value)

    now = get_current_time_gmt()
    message = (
        f'Explained {view.value} with {prompt.model_id}: '
        f'{answer["input_tokens"]} in, {answer["output_tokens"]} out.'
    )
    logger.info(message)

    put_cached(ExplanationItem(
        cache_key = cache_key,
        view = view.value,
        text = answer['text'],
        role = prompt.role,
        model_id = prompt.model_id,
        prompt_version = prompt.version,
        generated_at = now.isoformat(),
        expires_at = int((now + timedelta(hours = CACHE_HOURS)).timestamp())
    ))

    return {
        'view': view,
        'text': answer['text'],
        'role': prompt.role,
        'model': prompt.model_id,
        'prompt_version': prompt.version,
        'cached': False,
        'generated_at': now.isoformat(),
    }


@handle_service_errors('AI')
async def list_roles_service() -> Dict[str, Any]:
    '''
    Returns the roles currently configured.

    Exists so the wording in force can be reviewed without opening the console:
    the whole point of keeping it in a table is that it changes often, and what
    changes often has to be inspectable.

    Returns:
        Dict[str, Any]: Payload matching RoleListResponse shape.
    '''
    prompts = list_prompts()
    return {
        'count': len(prompts),
        'roles': [
            {
                'view': prompt.view,
                'version': prompt.version,
                'role': prompt.role,
                'model_id': prompt.model_id,
                'active': prompt.active,
            }
            for prompt in prompts
        ],
    }


@handle_service_errors('AI')
async def save_role_service(definition: Dict[str, Any]) -> Dict[str, Any]:
    '''
    Stores a version of the role a view is explained from.

    This is how the wording is administered — through the API, like everything
    else. Writing a version does not overwrite the previous one: it is stored
    alongside and the older versions of that view are marked inactive, so a
    rollback is flipping a flag and nothing is ever lost. The version also takes
    part in the cache key, so retuning stops serving what the previous wording
    produced without deleting a single row.

    Args:
        definition (Dict[str, Any]): Payload matching RoleDefinition shape.

    Returns:
        Dict[str, Any]: The stored role, as RoleSummary shape.
    '''
    prompt = PromptItem(
        view = definition['view'],
        version = definition['version'],
        role = definition['role'],
        instructions = definition['instructions'],
        rules = list(definition.get('rules', [])),
        max_tokens = definition['max_tokens'],
        model_id = definition['model_id'],
        active = bool(definition.get('active', True)),
        created_at = get_current_time_gmt().isoformat()
    )
    put_prompt(prompt)

    retired = 0
    if prompt.active:
        for stored in list_prompts():
            if (stored.view == prompt.view and stored.version != prompt.version
                    and stored.active):
                put_prompt(replace(stored, active = False))
                retired += 1

    message = (f'Role of {prompt.view} stored as version {prompt.version}; '
               f'{retired} earlier version(s) retired.')
    logger.info(message)

    return {
        'view': prompt.view,
        'version': prompt.version,
        'role': prompt.role,
        'model_id': prompt.model_id,
        'active': prompt.active,
    }


__all__ = [
    'CACHE_HOURS',
    'MAX_PAYLOAD_CHARACTERS',
    'explain_service',
    'save_role_service',
    'list_roles_service',
]
