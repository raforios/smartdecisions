'''
    AI: routes handler
'''
from fastapi import APIRouter, Depends, Request, status

from controllers.ai import (
    explain_controller,
    list_roles_controller,
    save_role_controller
)
from schemas.ai import (
    ExplainRequest,
    ExplainResponse,
    RoleDefinition,
    RoleListResponse,
    RoleSummary
)
from services.logger_config import custom_logger as logger
from services.security import get_current_user


router = APIRouter(prefix = '/v1/ai', tags = ['AI'])


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
    current_user: str = Depends(get_current_user)
) -> ExplainResponse:
    ''' Endpoint returning the interpretation of a view. '''
    message = f'User: {current_user}. Requested an explanation of {payload.view.value}.'
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
    current_user: str = Depends(get_current_user)
) -> RoleListResponse:
    ''' Endpoint listing the configured expert roles. '''
    message = f'User: {current_user}. Requested the configured roles.'
    logger.info(message)

    return await list_roles_controller(
        current_user = current_user,
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
    current_user: str = Depends(get_current_user)
) -> RoleSummary:
    ''' Endpoint storing a version of an expert role. '''
    message = (f'User: {current_user}. Stored role {definition.view.value} '
               f'v{definition.version}.')
    logger.info(message)

    return await save_role_controller(
        definition = definition,
        current_user = current_user,
        request = request
    )
