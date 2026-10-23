'''
    ANALYTICS: the policies the analyses are judged with — the commercial one
    (objectives, exchange-rate effect) and the credit one (receivables).
'''
from boto3.resources.base import ServiceResource
from fastapi import Request

from schemas.objectives import CommercialPolicyResponse, CommercialPolicySchema
from schemas.receivables import CreditPolicyRequest, CreditPolicyResponse
from services.analytics_utils import (
    get_commercial_policy,
    get_credit_policy,
    save_commercial_policy,
    save_credit_policy
)
from services.objectives import resolve_policy as resolve_commercial_policy
from services.receivables import resolve_policy
from services.utils import audit_event, handle_service_errors


@handle_service_errors('COMMERCIAL')
async def get_commercial_policy_controller(
    dynamodb_resource: ServiceResource,
    request: Request, # pylint: disable=unused-argument
    current_user: str
) -> CommercialPolicyResponse:
    '''
        Returns the yardstick the caller's attainment is judged with: their
        own where they set it, the service default everywhere else.
    '''
    stored = get_commercial_policy(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user
    )
    return CommercialPolicyResponse(
        owner_email = current_user,
        # Whether the account set its own: every view that judges with it
        # warns while it runs on the service defaults.
        source_code = 'CLIENT' if stored else 'DEFAULT',
        **resolve_commercial_policy(stored).model_dump()
    )


@handle_service_errors('COMMERCIAL')
@audit_event('COMMERCIAL', 'CommercialPolicy', 'UPSERT')
async def save_commercial_policy_controller(
    dynamodb_resource: ServiceResource,
    policy: CommercialPolicySchema,
    request: Request, # pylint: disable=unused-argument
    current_user: str
) -> CommercialPolicyResponse:
    '''
        Stores the caller's commercial policy and answers with how it resolves.

        Answering with the resolved policy and not with what was sent is
        deliberate: the caller has to see which defaults filled the gaps
        before a semaphore is drawn with them.
    '''
    save_commercial_policy(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user,
        policy = policy.model_dump(exclude_none = True)
    )
    return await get_commercial_policy_controller(
        dynamodb_resource = dynamodb_resource,
        request = request,
        current_user = current_user
    )


@handle_service_errors('COMMERCIAL')
async def get_credit_policy_controller(
    dynamodb_resource: ServiceResource,
    request: Request, # pylint: disable=unused-argument
    current_user: str
) -> CreditPolicyResponse:
    '''
        Returns the credit policy that will be applied to the caller's book:
        their own where they set it, the service default everywhere else.
    '''
    resolved = resolve_policy(get_credit_policy(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user
    ))
    return CreditPolicyResponse(
        owner_email = current_user,
        **resolved.as_dto().model_dump()
    )


@handle_service_errors('COMMERCIAL')
@audit_event('COMMERCIAL', 'CreditPolicy', 'UPSERT')
async def save_credit_policy_controller(
    dynamodb_resource: ServiceResource,
    policy: CreditPolicyRequest,
    request: Request, # pylint: disable=unused-argument
    current_user: str
) -> CreditPolicyResponse:
    '''
        Stores the caller's credit policy and answers with how it resolves.

        Answering with the resolved policy and not with what was sent is
        deliberate: the caller has to be able to see which defaults filled the
        gaps before a provision is computed with them.
    '''
    save_credit_policy(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user,
        policy = policy.model_dump(exclude_none = True)
    )
    return await get_credit_policy_controller(
        dynamodb_resource = dynamodb_resource,
        request = request,
        current_user = current_user
    )
