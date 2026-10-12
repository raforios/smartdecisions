'''
    AI controllers.
'''
from fastapi import Request

from schemas.ai import (
    ExplainRequest,
    ExplainResponse,
    RoleActiveRequest,
    RoleDefinition,
    RoleListResponse,
    RoleSummary,
    ViewName
)
from services.ai import (
    explain_service,
    get_role_service,
    list_roles_service,
    save_role_service,
    set_role_active_service
)
from services.utils import audit_event, handle_service_errors


@handle_service_errors('AI')
@audit_event('AI', 'Explanation', 'GENERATE')
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
@audit_event('AI', 'Role', 'UPSERT')
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


@handle_service_errors('AI')
async def get_role_controller(
    view: ViewName,
    version: int,
    current_user: str, # pylint: disable=unused-argument
    request: Request # pylint: disable=unused-argument
) -> RoleDefinition:
    '''
        Returns one version of a role in full, to edit it.

        Args:
            view (ViewName): View the role explains.
            version (int): Version to read.
            current_user (str): Authenticated caller.
            request (Request): Incoming request.

        Returns:
            RoleDefinition: The role with its instructions and rules.
    '''
    result = await get_role_service(view = view.value, version = version)
    return RoleDefinition(**result)


@handle_service_errors('AI')
@audit_event('AI', 'Role', 'UPDATE')
async def set_role_active_controller(
    view: ViewName,
    version: int,
    change: RoleActiveRequest,
    current_user: str, # pylint: disable=unused-argument
    request: Request # pylint: disable=unused-argument
) -> RoleSummary:
    '''
        Turns one version of a role on or off.

        Args:
            view (ViewName): View the role explains.
            version (int): Version to change.
            change (RoleActiveRequest): Whether it is in force.
            current_user (str): Authenticated caller.
            request (Request): Incoming request, used by the audit decorator.

        Returns:
            RoleSummary: The changed role.
    '''
    result = await set_role_active_service(view = view.value, version = version,
                                           active = change.active)
    return RoleSummary(**result)
