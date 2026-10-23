'''
    AI controllers.
'''
from fastapi import Request

from schemas.ai import (
    ExplainRequest,
    ExplainResponse,
    PromptCaller,
    RoleDefinition,
    RoleListResponse,
    RoleSummary,
    RoleSwitch
)
from services.ai import (
    delete_role_service,
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
    current_user: str,
    request: Request, # pylint: disable=unused-argument
    auth_token: str | None
) -> ExplainResponse:
    '''
        Explains what a view is showing.

        Args:
            payload (ExplainRequest): View and the data it displays.
            current_user (str): The caller's company: its own role wins.
            request (Request): Incoming request, used by the audit decorator.
            auth_token (str | None): The caller's Authorization header, to read
                the explanation settings from PARAMETERS.

        Returns:
            ExplainResponse: The interpretation and what produced it.
    '''
    result = await explain_service(view = payload.view, data = payload.data,
                                   auth_token = auth_token, owner = current_user)
    return ExplainResponse(**result)


@handle_service_errors('AI')
async def list_roles_controller(
    current_user: str, # pylint: disable=unused-argument
    caller: PromptCaller,
    request: Request # pylint: disable=unused-argument
) -> RoleListResponse:
    '''
        Returns the expert roles the caller may see.

        Args:
            current_user (str): Authenticated caller, as the audit reads it.
            caller (PromptCaller): The caller's company and role.
            request (Request): Incoming request, used by the audit decorator.

        Returns:
            RoleListResponse: The configured roles.
    '''
    result = await list_roles_service(caller = caller)
    return RoleListResponse(**result)


@handle_service_errors('AI')
@audit_event('AI', 'Role', 'UPSERT')
async def save_role_controller(
    definition: RoleDefinition,
    current_user: str, # pylint: disable=unused-argument
    caller: PromptCaller,
    request: Request # pylint: disable=unused-argument
) -> RoleSummary:
    '''
        Stores a version of the role a view is explained from.

        Args:
            definition (RoleDefinition): The expert, its instructions and rules.
            current_user (str): Authenticated caller, as the audit reads it.
            caller (PromptCaller): The caller's company and role.
            request (Request): Incoming request, used by the audit decorator.

        Returns:
            RoleSummary: The stored role.
    '''
    result = await save_role_service(definition = definition.model_dump(mode = 'json'),
                                     caller = caller)
    return RoleSummary(**result)


@handle_service_errors('AI')
async def get_role_controller(
    view: str,
    version: int,
    current_user: str, # pylint: disable=unused-argument
    caller: PromptCaller,
    request: Request # pylint: disable=unused-argument
) -> RoleDefinition:
    '''
        Returns one version of a role in full, to edit it.

        Args:
            view (str): View the role explains.
            version (int): Version to read.
            current_user (str): Authenticated caller, as the audit reads it.
            caller (PromptCaller): The caller's company and role.
            request (Request): Incoming request.

        Returns:
            RoleDefinition: The role with its instructions and rules.
    '''
    result = await get_role_service(view = view, version = version, caller = caller)
    return RoleDefinition(**result)


@handle_service_errors('AI')
@audit_event('AI', 'Role', 'UPDATE')
async def set_role_active_controller(
    change: RoleSwitch,
    current_user: str, # pylint: disable=unused-argument
    caller: PromptCaller,
    request: Request # pylint: disable=unused-argument
) -> RoleSummary:
    '''
        Turns one version of a role on or off.

        Args:
            change (RoleSwitch): View, version and whether it is in force.
            current_user (str): Authenticated caller, as the audit reads it.
            caller (PromptCaller): The caller's company and role.
            request (Request): Incoming request, used by the audit decorator.

        Returns:
            RoleSummary: The changed role.
    '''
    result = await set_role_active_service(view = change.view, version = change.version,
                                           active = change.active, caller = caller)
    return RoleSummary(**result)


@handle_service_errors('AI')
@audit_event('AI', 'Role', 'DELETE')
async def delete_role_controller(
    view: str,
    version: int,
    current_user: str, # pylint: disable=unused-argument
    caller: PromptCaller,
    request: Request # pylint: disable=unused-argument
) -> RoleSummary:
    '''
        Deletes one version of a role, of any company (ADMIN only).

        Args:
            view (str): View the role explains.
            version (int): Version to delete.
            current_user (str): Authenticated caller, as the audit reads it.
            caller (PromptCaller): The caller's company and role.
            request (Request): Incoming request, used by the audit decorator.

        Returns:
            RoleSummary: The deleted role.
    '''
    result = await delete_role_service(view = view, version = version, caller = caller)
    return RoleSummary(**result)
