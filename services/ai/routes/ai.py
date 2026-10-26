'''
    AI: routes handler
'''
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Request, status

from controllers.ai import (
    delete_role_controller,
    explain_controller,
    get_role_controller,
    list_roles_controller,
    save_role_controller,
    set_role_active_controller
)
from schemas.ai import (
    ExplainRequest,
    ExplainResponse,
    PromptCaller,
    RoleActiveRequest,
    RoleDefinition,
    RoleListResponse,
    RoleSummary,
    RoleSwitch,
    VIEW_PATTERN
)
from services.logger_config import custom_logger as logger
from services.security import (
    get_current_owner,
    get_current_payload,
    require_roles,
    resolve_owner
)


router = APIRouter(prefix = '/v1/ai', tags = ['AI'])


async def get_prompt_caller(payload: dict[str, Any] = Depends(get_current_payload)) -> PromptCaller:
    '''
        FastAPI dependency: the caller's company and role, which decide whose
        roles they see and write (Rafael, 21-oct).

        Args:
            payload (dict[str, Any]): Decoded token claims.

        Returns:
            PromptCaller: Company (or e-mail) and role.
    '''
    return PromptCaller(owner = resolve_owner(payload), role = payload.get('role'))


@router.post(
    '/explain',
    response_model = ExplainResponse,
    status_code = status.HTTP_200_OK,
    summary = 'Explain what a view is showing.',
    description = 'Reads the payload a screen is displaying and returns it in '
                  'words, written from the point of view of the expert '
                  'configured for that view. It explains what it is given: no '
                  'database access, no actions, and no figure that is not '
                  'already on the screen.'
)
async def explain_endpoint(
    request: Request,
    payload: ExplainRequest,
    current_user: str = Depends(get_current_owner)
) -> ExplainResponse:
    ''' Endpoint returning the interpretation of a view. '''
    message = f'User: {current_user}. Requested an explanation of {payload.view}.'
    logger.info(message)

    return await explain_controller(
        payload = payload,
        current_user = current_user,
        request = request
    )


@router.get(
    '/roles',
    response_model = RoleListResponse,
    status_code = status.HTTP_200_OK,
    summary = 'Expert roles currently configured.',
    description = 'The wording each view is explained from, and its version. '
                  'It lives in a table so it can be tuned without a release, '
                  'which is exactly why it has to be inspectable.'
)
async def list_roles_endpoint(
    request: Request,
    caller: PromptCaller = Depends(get_prompt_caller)
) -> RoleListResponse:
    ''' Endpoint listing the expert roles the caller may see. '''
    message = f'User: {caller.owner}. Requested the configured roles.'
    logger.info(message)

    return await list_roles_controller(
        current_user = caller.owner,
        caller = caller,
        request = request
    )


@router.post(
    '/roles',
    response_model = RoleSummary,
    status_code = status.HTTP_201_CREATED,
    summary = 'Store a version of a view\'s expert role.',
    description = 'The wording each view is explained from is administered here '
                  'and not in the repository, because it is what gets tuned most '
                  'and tuning it must not need a release. A new version does not '
                  'overwrite the previous one: it is stored alongside and the '
                  'older ones are marked inactive, so a rollback is flipping a '
                  'flag. The version also takes part in the cache key, so '
                  'retuning stops serving what the previous wording produced.'
)
async def save_role_endpoint(
    request: Request,
    definition: RoleDefinition,
    caller: PromptCaller = Depends(get_prompt_caller)
) -> RoleSummary:
    ''' Endpoint storing a version of an expert role. '''
    message = f'User: {caller.owner}. Storing a role of {definition.view}.'
    logger.info(message)

    return await save_role_controller(
        definition = definition,
        current_user = caller.owner,
        caller = caller,
        request = request
    )


@router.get(
    '/roles/{view}/{version}',
    response_model = RoleDefinition,
    status_code = status.HTTP_200_OK,
    summary = 'One version of a view\'s expert role, in full.',
    description = 'The role with its instructions and rules, to edit it. An edit '
                  'is stored as the next version through POST /roles, never over '
                  'this one.'
)
async def get_role_endpoint(
    request: Request,
    view: Annotated[str, Path(pattern = VIEW_PATTERN)],
    version: int,
    caller: PromptCaller = Depends(get_prompt_caller)
) -> RoleDefinition:
    ''' Endpoint returning one version of an expert role. '''
    message = f'User: {caller.owner}. Requested role {view} v{version}.'
    logger.info(message)

    return await get_role_controller(
        view = view,
        version = version,
        current_user = caller.owner,
        caller = caller,
        request = request
    )


@router.patch(
    '/roles/{view}/{version}/active',
    response_model = RoleSummary,
    status_code = status.HTTP_200_OK,
    summary = 'Turn one version of a view\'s expert role on or off.',
    description = 'Turning a version on retires the other versions of the same '
                  'view. Turning it off leaves the view without a role until '
                  'another is turned on. Nothing is deleted.'
)
async def set_role_active_endpoint(
    request: Request,
    view: Annotated[str, Path(pattern = VIEW_PATTERN)],
    version: int,
    change: RoleActiveRequest,
    caller: PromptCaller = Depends(get_prompt_caller)
) -> RoleSummary:
    ''' Endpoint turning a version of an expert role on or off. '''
    message = (f'User: {caller.owner}. Set role {view} v{version} '
               f'active={change.active}.')
    logger.info(message)

    return await set_role_active_controller(
        change = RoleSwitch(view = view, version = version, active = change.active),
        current_user = caller.owner,
        caller = caller,
        request = request
    )


@router.delete(
    '/roles/{view}/{version}',
    response_model = RoleSummary,
    status_code = status.HTTP_200_OK,
    summary = 'Delete one version of a view\'s expert role (ADMIN).',
    description = 'The ADMIN deletes a version of any company or a general one '
                  '(Rafael, 21-oct). A company without its own role in force '
                  'goes back to the general one.'
)
async def delete_role_endpoint(
    request: Request,
    view: Annotated[str, Path(pattern = VIEW_PATTERN)],
    version: int,
    current_user: str = Depends(require_roles('ADMIN'))
) -> RoleSummary:
    ''' Endpoint deleting a version of an expert role. '''
    message = f'User: {current_user}. Deleting role {view} v{version}.'
    logger.info(message)

    return await delete_role_controller(
        view = view,
        version = version,
        current_user = current_user,
        caller = PromptCaller(owner = current_user, role = 'ADMIN'),
        request = request
    )
