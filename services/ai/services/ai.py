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
from dataclasses import dataclass, replace
from datetime import timedelta
from typing import Any

from models.ai import ExplanationItem, PromptItem
from schemas.ai import AIError, PromptCaller
from services.ai_utils import (
    build_cache_key,
    delete_prompt,
    get_active_prompt,
    get_cached,
    get_prompt,
    list_prompts,
    next_version,
    put_cached,
    put_prompt
)
from services.bedrock_client import invoke
from services.exceptions import (
    ForbiddenError,
    InvalidInputError,
    RegisterNotFoundError,
    ServiceUnavailableError
)
from services.logger_config import custom_logger as logger
from services.utils import (
    get_current_time_gmt,
    handle_service_errors,
    read_parameters,
    required_parameters
)


# The business values of an explanation live in PARAMETERS (scope `ai`), not
# in the .env (Rafael, 17-oct-2026): changing one must not need a release.
AI_SCOPE = 'ai'
SETTINGS_CODES = ('EXPLANATION_CACHE_HOURS', 'MAX_PAYLOAD_CHARACTERS', 'LIST_SAMPLE_SIZE',
                  'EXPLANATION_QUESTION', 'BEDROCK_TEMPERATURE')


@dataclass(frozen = True)
class ExplainSettings:
    '''
        What shapes an explanation, as read from PARAMETERS.

        - cache_hours: how long an answer stays valid.
        - max_payload_characters: ceiling on what a view may send; a screen
          that grew unexpectedly must not turn into an unexpectedly large bill.
        - sample_size: elements of a long list that survive the trim.
        - question: what every explanation answers. Never accepted from the
          caller: this endpoint explains a screen, it does not take orders.
        - temperature: low, so the same screen explained twice reads the same.
    '''
    cache_hours: int
    max_payload_characters: int
    sample_size: int
    question: str
    temperature: float


def explain_settings(auth_token: str | None) -> ExplainSettings:
    '''
        Reads the explanation settings from PARAMETERS, all of them or none.

        Args:
            auth_token (str | None): The caller's Authorization header.

        Returns:
            ExplainSettings: The values in force.

        Raises:
            ServiceUnavailableError: PARAMETERS unreachable, or a value missing.
    '''
    values = required_parameters(read_parameters(AI_SCOPE, auth_token), SETTINGS_CODES)
    return ExplainSettings(
        cache_hours = int(values['EXPLANATION_CACHE_HOURS']),
        max_payload_characters = int(values['MAX_PAYLOAD_CHARACTERS']),
        sample_size = int(values['LIST_SAMPLE_SIZE']),
        question = str(values['EXPLANATION_QUESTION']),
        temperature = float(values['BEDROCK_TEMPERATURE'])
    )


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


def _trim(
    value: Any,
    budget_hit: list[bool],
    sample_size: int
) -> Any:
    '''
        Walks a structure and cuts every long list, at any depth.

        Depth matters: a route plan is `days[].stops[]`, so trimming only the
        top level cut a list of five and left the eighty thousand stops
        underneath. That payload reached the model as 218 000 tokens against a
        limit of 200 000, and the call failed outright.

        Args:
            value (Any): Node of the response being walked.
            budget_hit (list[bool]): Single-element flag set when something was
                actually cut, so the caller can log it once.
            sample_size (int): Elements a long list keeps.

        Returns:
            Any: The same node, with long lists reduced to a sample.
    '''
    if isinstance(value, dict):
        return {key: _trim(item, budget_hit, sample_size) for key, item in value.items()}

    if isinstance(value, list):
        if len(value) > sample_size:
            budget_hit[0] = True
            kept = [_trim(item, budget_hit, sample_size) for item in value[:sample_size]]
            kept.append(
                f'… {len(value) - sample_size} elemento(s) más, no mostrados: '
                f'se envía una muestra de los primeros {sample_size}.'
            )
            return kept
        return [_trim(item, budget_hit, sample_size) for item in value]

    return value


def _fit_to_budget(
    payload: dict[str, Any],
    settings: ExplainSettings
) -> dict[str, Any]:
    '''
        Shrinks a response that does not fit the token budget, without
        re-declaring its shape.

        Some responses are long by nature: the opportunities run answers with
        545 rows and 246 KB, and a route plan carries every stop of every day.
        Sending that costs a fortune and produces a worse explanation, because
        no reader — model or person — takes in hundreds of rows; and refusing it
        leaves the button broken on the screen where it is most useful.

        So every long list is cut to a sample, at whatever depth it sits.
        Nothing is re-typed and no key is invented: the marker goes inside the
        list itself, which the model needs or it would describe a sample as if
        it were the whole.

        Args:
            payload (dict[str, Any]): The response as the service returned it.
            settings (ExplainSettings): The ceiling and the sample size.

        Returns:
            dict[str, Any]: The same response, trimmed only if it had to be.
    '''
    if len(json.dumps(payload, default = str)) <= settings.max_payload_characters:
        return payload

    budget_hit = [False]
    trimmed = _trim(payload, budget_hit, settings.sample_size)

    message = (
        f'Payload trimmed to fit the budget: '
        f'{len(json.dumps(payload, default = str)):,} -> '
        f'{len(json.dumps(trimmed, default = str)):,} characters.'
    )
    logger.info(message)
    return trimmed


@handle_service_errors('AI')
async def explain_service(
    view: str,
    data: dict[str, Any],
    auth_token: str | None,
    owner: str
) -> dict[str, Any]:
    '''
    Explains what a view is showing, from the point of view of its expert.

    Args:
        view (str): View being explained; it exists if it has an active role.
        data (dict[str, Any]): The payload the view is displaying.
        auth_token (str | None): The caller's Authorization header, forwarded
            to PARAMETERS.
        owner (str): The caller's company: its own role wins over the general.

    Returns:
        dict[str, Any]: Payload matching ExplainResponse shape.

    Raises:
        InvalidInputError: If the payload is empty.
        RegisterNotFoundError: If no role is configured for the view.
        ServiceUnavailableError: If the model cannot be reached or says nothing.
    '''
    if not data:
        raise InvalidInputError(detail = AIError.EMPTY_PAYLOAD.value)

    # The payload travels as the producing service returned it. It already
    # passed a Pydantic model on the other side; re-declaring its shape here
    # would be a second contract for one thing, and would drop fields the
    # expert could have used. The only thing done to it is fitting it to the
    # budget when a list is longer than anyone can read.
    settings = explain_settings(auth_token)
    payload = _fit_to_budget(data, settings)

    prompt = get_active_prompt(view, owner)
    if prompt is None:
        error_msg = f'No active role is configured for {view}.'
        logger.warning(error_msg)
        raise RegisterNotFoundError(detail = AIError.ROLE_NOT_CONFIGURED.value)

    cache_key = build_cache_key(view, payload, prompt.version)
    cached = get_cached(cache_key)
    if cached is not None:
        message = f'Explanation of {view} served from cache.'
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
        user_prompt = (f'Vista {view}, respuesta del backend:\n'
                       f'{json.dumps(payload, ensure_ascii = False, default = str)}'
                       f'\n\n{settings.question}'),
        max_tokens = prompt.max_tokens,
        temperature = settings.temperature
    )
    if not answer['text']:
        error_msg = f'The model returned no text for {view}.'
        logger.error(error_msg)
        raise ServiceUnavailableError(detail = AIError.MODEL_REFUSED.value)

    now = get_current_time_gmt()
    message = (
        f'Explained {view} with {prompt.model_id}: '
        f'{answer["input_tokens"]} in, {answer["output_tokens"]} out.'
    )
    logger.info(message)

    put_cached(ExplanationItem(
        cache_key = cache_key,
        view = view,
        text = answer['text'],
        role = prompt.role,
        model_id = prompt.model_id,
        prompt_version = prompt.version,
        generated_at = now.isoformat(),
        expires_at = int((now + timedelta(hours = settings.cache_hours)).timestamp())
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


# Who may write roles: the ADMIN the general ones, a manager their company's.
WRITERS = ('ADMIN', 'MANAGER')


def _scope(caller: PromptCaller) -> str | None:
    '''
        The company a caller writes for: none (general) for the ADMIN.

        Args:
            caller (PromptCaller): Who is administering.

        Returns:
            str | None: The company, or None for the general roles.
    '''
    return None if caller.admin else caller.owner


def _visible(
    prompt: PromptItem,
    caller: PromptCaller
) -> bool:
    '''
        Whether a caller may see a role: the ADMIN every one; anyone else the
        general ones and their company's.

        Args:
            prompt (PromptItem): Stored role.
            caller (PromptCaller): Who asks.

        Returns:
            bool: True when it may be shown.
    '''
    return caller.admin or prompt.client in (None, caller.owner)


def _summary(prompt: PromptItem) -> dict[str, Any]:
    '''
        One role as RoleSummary shape.

        Args:
            prompt (PromptItem): Stored role.

        Returns:
            dict[str, Any]: View, version, role, model, whether it is in force
            and its company.
    '''
    return {
        'view': prompt.view,
        'version': prompt.version,
        'role': prompt.role,
        'model_id': prompt.model_id,
        'active': prompt.active,
        'client': prompt.client,
    }


def _retire_others(prompt: PromptItem) -> int:
    '''
        Turns off the other active versions of the same view and company: a
        company's view is explained by one role, and so is the general one.

        Args:
            prompt (PromptItem): The version just turned on.

        Returns:
            int: How many were retired.
    '''
    retired = 0
    for stored in list_prompts():
        if (stored.view == prompt.view and stored.client == prompt.client
                and stored.version != prompt.version and stored.active):
            put_prompt(replace(stored, active = False))
            retired += 1
    return retired


@handle_service_errors('AI')
async def list_roles_service(caller: PromptCaller) -> dict[str, Any]:
    '''
    Returns the roles the caller may see: every one for the ADMIN, the general
    ones and their company's for anyone else.

    Exists so the wording in force can be reviewed without opening the console:
    the whole point of keeping it in a table is that it changes often, and what
    changes often has to be inspectable.

    Args:
        caller (PromptCaller): Who asks.

    Returns:
        dict[str, Any]: Payload matching RoleListResponse shape.
    '''
    prompts = [prompt for prompt in list_prompts() if _visible(prompt, caller)]
    return {'count': len(prompts), 'roles': [_summary(prompt) for prompt in prompts]}


@handle_service_errors('AI')
async def save_role_service(
    definition: dict[str, Any],
    caller: PromptCaller
) -> dict[str, Any]:
    '''
    Stores a version of the role a view is explained from.

    This is how the wording is administered — through the API, like everything
    else. Writing a version does not overwrite the previous one: it is stored
    alongside and the older versions of that view and company are marked
    inactive, so a rollback is flipping a flag and nothing is ever lost. The
    version also takes part in the cache key, so retuning stops serving what
    the previous wording produced without deleting a single row.

    The company comes from the token, never from the body: the ADMIN writes
    general roles, a manager their company's. The number is the next one of
    the view across every company, whatever the body says, so two companies
    never write over each other.

    Args:
        definition (dict[str, Any]): Payload matching RoleDefinition shape.
        caller (PromptCaller): Who is writing.

    Returns:
        dict[str, Any]: The stored role, as RoleSummary shape.

    Raises:
        ForbiddenError: If the caller's role may not write roles.
    '''
    if caller.role not in WRITERS:
        error_msg = f'{caller.owner} with role {caller.role} tried to store a role.'
        logger.warning(error_msg)
        raise ForbiddenError(detail = 'ROLE_NOT_ALLOWED')
    prompt = PromptItem(
        view = definition['view'],
        version = next_version(definition['view']),
        role = definition['role'],
        instructions = definition['instructions'],
        rules = list(definition.get('rules', [])),
        max_tokens = definition['max_tokens'],
        model_id = definition['model_id'],
        active = bool(definition.get('active', True)),
        created_at = get_current_time_gmt().isoformat(),
        client = _scope(caller)
    )
    put_prompt(prompt)
    retired = _retire_others(prompt) if prompt.active else 0
    message = (f'Role of {prompt.view} stored as version {prompt.version} for '
               f'{prompt.client or "every company"}; {retired} earlier version(s) retired.')
    logger.info(message)
    return _summary(prompt)


def _stored(
    view: str,
    version: int,
    caller: PromptCaller
) -> PromptItem:
    '''
        One stored version of a role the caller may see, or the not-found
        answer: another company's role answers like one that does not exist.

        Args:
            view (str): View the role explains.
            version (int): Version to read.
            caller (PromptCaller): Who asks.

        Returns:
            PromptItem: The role.

        Raises:
            RegisterNotFoundError: If that version does not exist for the caller.
    '''
    prompt = get_prompt(view, version)
    if prompt is None or not _visible(prompt, caller):
        error_msg = f'Role {view} v{version} does not exist for {caller.owner}.'
        logger.warning(error_msg)
        raise RegisterNotFoundError(detail = AIError.ROLE_NOT_FOUND.value)
    return prompt


@handle_service_errors('AI')
async def get_role_service(
    view: str,
    version: int,
    caller: PromptCaller
) -> dict[str, Any]:
    '''
        Returns one version of a role in full, so it can be edited: an edit is
        stored as the next version, never over this one. A manager may open a
        general role to start their company's from it.

        Args:
            view (str): View the role explains.
            version (int): Version to read.
            caller (PromptCaller): Who asks.

        Returns:
            dict[str, Any]: Payload matching RoleDefinition shape.
    '''
    prompt = _stored(view, version, caller)
    return {
        'view': prompt.view,
        'version': prompt.version,
        'role': prompt.role,
        'instructions': prompt.instructions,
        'rules': list(prompt.rules),
        'max_tokens': prompt.max_tokens,
        'model_id': prompt.model_id,
        'active': prompt.active,
        'client': prompt.client,
    }


@handle_service_errors('AI')
async def set_role_active_service(
    view: str,
    version: int,
    active: bool,
    caller: PromptCaller
) -> dict[str, Any]:
    '''
        Turns one version of a role on or off.

        Only the caller's own: the ADMIN the general ones, a manager their
        company's. Turning a version on retires the others of the same view
        and company; turning it off leaves that company on the general role.

        Args:
            view (str): View the role explains.
            version (int): Version to change.
            active (bool): Whether it is in force.
            caller (PromptCaller): Who is changing it.

        Returns:
            dict[str, Any]: The changed role, as RoleSummary shape.

        Raises:
            ForbiddenError: If the role is not the caller's to change.
    '''
    stored = _stored(view, version, caller)
    if caller.role not in WRITERS or stored.client != _scope(caller):
        error_msg = f'{caller.owner} tried to switch role {view} v{version} of another owner.'
        logger.warning(error_msg)
        raise ForbiddenError(detail = 'ROLE_NOT_ALLOWED')
    prompt = replace(stored, active = active)
    put_prompt(prompt)
    if active:
        _retire_others(prompt)
    message = f'Role {view} v{version} set to active={active}.'
    logger.info(message)
    return _summary(prompt)


@handle_service_errors('AI')
async def delete_role_service(
    view: str,
    version: int,
    caller: PromptCaller
) -> dict[str, Any]:
    '''
        Deletes one version of a role, of any company (the ADMIN only, by the
        route: Rafael, 21-oct). The company falls back on the general role.

        Args:
            view (str): View the role explains.
            version (int): Version to delete.
            caller (PromptCaller): Who is deleting.

        Returns:
            dict[str, Any]: The deleted role, as RoleSummary shape.
    '''
    prompt = _stored(view, version, caller)
    delete_prompt(view, version)
    message = f'Role {view} v{version} of {prompt.client or "every company"} deleted.'
    logger.info(message)
    return _summary(prompt)
