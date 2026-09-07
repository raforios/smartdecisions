'''
    AI controllers.
'''
from fastapi import Request

from schemas.ai import (
    ExplainRequest,
    ExplainResponse,
    RoleDefinition,
    RoleListResponse,
    RoleSummary
)
from services.ai import explain_service, list_roles_service, save_role_service
from services.utils import handle_service_errors


@handle_service_errors('AI')
async def explain_controller(
    payload: ExplainRequest,
    current_user: str, # pylint: disable=unused-argument
    request: Request # pylint: disable=unused-argument
) -> ExplainResponse:
    '''
        Explains what a view is showing.

        Args:
            payload (ExplainRequest): View and the data it displays.
            current_user (str): Authenticated caller.
            request (Request): Incoming request, used by the audit decorator.

        Returns:
            ExplainResponse: The interpretation and what produced it.
    '''
    result = await explain_service(view = payload.view, data = payload.data)
    return ExplainResponse(**result)


@handle_service_errors('AI')
async def list_roles_controller(
    current_user: str, # pylint: disable=unused-argument
    request: Request # pylint: disable=unused-argument
) -> RoleListResponse:
    '''
        Returns the expert roles currently configured.

        Args:
            current_user (str): Authenticated caller.
            request (Request): Incoming request, used by the audit decorator.

        Returns:
            RoleListResponse: The configured roles.
    '''
    result = await list_roles_service()
    return RoleListResponse(**result)


@handle_service_errors('AI')
async def save_role_controller(
    definition: RoleDefinition,
    current_user: str, # pylint: disable=unused-argument
    request: Request # pylint: disable=unused-argument
) -> RoleSummary:
    '''
        Stores a version of the role a view is explained from.

        Args:
            definition (RoleDefinition): The expert, its instructions and rules.
            current_user (str): Authenticated caller.
            request (Request): Incoming request, used by the audit decorator.

        Returns:
            RoleSummary: The stored role.
    '''
    result = await save_role_service(definition = definition.model_dump(mode = 'json'))
    return RoleSummary(**result)
