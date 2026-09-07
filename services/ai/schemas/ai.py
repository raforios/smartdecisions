'''
    Pydantic V2 DTOs for the AI interpretation service.

    Every other service in SmartDecisions returns data and stable codes. This is
    the one place where those codes become a sentence.

    The input is **the response of those services, as they returned it**: the
    JSON a Pydantic model produced on the other side travels here whole. Nothing
    is re-declared, nothing is trimmed. Re-typing a subset here would mean two
    declarations of the same contract drifting apart, and would silently drop
    fields the explanation could have used — the expert has to see everything the
    backend saw.
'''
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, Field


class AIError(str, Enum):
    '''
        Why an explanation could not be produced.

        Travels as the error `detail`, same contract as the rest of the API.
    '''
    UNKNOWN_VIEW = 'UNKNOWN_VIEW'
    EMPTY_PAYLOAD = 'EMPTY_PAYLOAD'
    PAYLOAD_TOO_LARGE = 'PAYLOAD_TOO_LARGE'
    ROLE_NOT_CONFIGURED = 'ROLE_NOT_CONFIGURED'
    MODEL_UNAVAILABLE = 'MODEL_UNAVAILABLE'
    MODEL_REFUSED = 'MODEL_REFUSED'


class ViewName(str, Enum):
    '''
        The views this service knows how to read.

        A closed list on purpose: an unknown view is answered with
        UNKNOWN_VIEW rather than passed to the model as unstructured text.
        Adding a module tomorrow means adding a member here and a role in the
        prompts table — not touching the engine.
    '''
    MINERALS_FORECAST = 'minerals_forecast'
    RATE_FORECAST = 'rate_forecast'
    SALE_SCENARIO = 'sale_scenario'


class ExplainRequest(BaseModel):
    '''
        What the caller sends: which view, and the response it is showing.

        `data` is the JSON the producing service returned, untouched. It is not
        re-validated field by field here on purpose: it already passed through a
        Pydantic model on the other side, and declaring its shape a second time
        would create two contracts for one thing.
    '''
    view: ViewName
    data: Dict[str, Any] = Field(
        ...,
        description = 'The response of the service that produced the view, as it '
                      'returned it.'
    )


class ExplainResponse(BaseModel):
    '''
        The interpretation, plus what produced it.

        `cached` travels because a demo clicks the same button repeatedly and
        the difference between a fresh answer and a stored one is the difference
        between paying for it and not.
    '''
    view: ViewName
    text: str
    role: str = Field(..., description = 'Expert role the answer was written from.')
    model: str
    prompt_version: int
    cached: bool = False
    generated_at: datetime


class RoleDefinition(BaseModel):
    '''
        The expert a view is explained by.

        Lives in DynamoDB and not in the code because the wording is what gets
        tuned most, and tuning it must not need a release. It is also what makes
        the answers specific: a mining quotations analyst and a commercial
        analyst read the same kind of numbers with different eyes.
    '''
    view: ViewName
    version: int = Field(..., ge = 1)
    role: str = Field(..., description = 'Who the model is, in one line.')
    instructions: str = Field(..., description = 'How to read this view.')
    rules: List[str] = Field(
        default_factory = list,
        description = 'What it must never do. Kept as a list so a new rule is '
                      'one row and not a rewrite of the prompt.'
    )
    max_tokens: int = Field(..., ge = 1)
    model_id: str = Field(..., description = 'Bedrock inference profile to use.')
    active: bool = True


class RoleSummary(BaseModel):
    '''One row of the configured roles, without the full prompt text.'''
    view: ViewName
    version: int
    role: str
    model_id: str
    active: bool


class RoleListResponse(BaseModel):
    '''The roles currently configured, so they can be reviewed without a deploy.'''
    count: int = Field(..., ge = 0)
    roles: List[RoleSummary] = Field(default_factory = list)
