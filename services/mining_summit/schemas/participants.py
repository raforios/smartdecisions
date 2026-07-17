'''
    Participant Schemas (Request / Response / Query) for the Mining Summit service.
'''
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field

from schemas.common import OptionalContactSchema
from schemas.enums import (
    AssignmentType,
    ParticipantRole,
    ParticipantStatus,
    ThematicAxis
)


class ParticipantCreateSchema(OptionalContactSchema):
    '''
        Pydantic schema for registering a new summit participant.
        First name, last name and CI are mandatory; remaining fields are optional.
        When 'axis' is provided the participant is seated in that axis.
    '''
    first_name: str = Field(..., min_length = 1, max_length = 80)
    last_name: str = Field(..., min_length = 1, max_length = 80)
    ci: str = Field(..., min_length = 4, max_length = 20,
                    description = 'Carnet de Identidad. Unique identifier per participant.')
    institution_id: Optional[str] = Field(
        None, max_length = 120,
        description = 'Reference institution slug; drives role and institution data.'
    )
    axis: Optional[ThematicAxis] = Field(
        None, description = 'Thematic axis chosen by the participant; drives seat assignment.'
    )
    observation: Optional[str] = Field(None, max_length = 300)


class ParticipantUpdateSchema(OptionalContactSchema):
    '''
        Pydantic schema for editing an existing participant so it can be fully
        accredited. Every field is optional; only the provided ones change.
        Setting 'institution_id' re-derives the role and is validated against the
        institution cupo. Setting 'axis' assigns (or reassigns) a stable eje/mesa
        seat, validated against the axis aula availability.
    '''
    first_name: Optional[str] = Field(None, min_length = 1, max_length = 80)
    last_name: Optional[str] = Field(None, min_length = 1, max_length = 80)
    institution_id: Optional[str] = Field(
        None, max_length = 120,
        description = 'Reference institution slug; drives role and cupo check.'
    )
    axis: Optional[ThematicAxis] = Field(
        None, description = 'Thematic axis to seat the participant in.'
    )
    observation: Optional[str] = Field(None, max_length = 300)


class ParticipantDeactivateSchema(BaseModel):
    '''
        Pydantic schema for deactivating (soft-deleting) an accredited
        participant. The observation records the authorization / reason.
    '''
    observation: Optional[str] = Field(
        None, max_length = 300,
        description = 'Reason or institutional authorization for the removal.'
    )


class ParticipantReplaceSchema(OptionalContactSchema):
    '''
        Pydantic schema for replacing an accredited participant with a
        substitute authorized by the same institution. The substitute inherits
        the outgoing participant's seat (axis/mesa/institution).
    '''
    ci: str = Field(..., min_length = 4, max_length = 20,
                    description = 'CI of the substitute participant.')
    first_name: str = Field(..., min_length = 1, max_length = 80)
    last_name: str = Field(..., min_length = 1, max_length = 80)
    observation: Optional[str] = Field(
        None, max_length = 300,
        description = 'Institutional authorization note for the replacement.'
    )


class ParticipantResponseSchema(BaseModel):
    '''
        Joined participant view: the person master data plus, when the person is
        registered, the event registration/seat (axis, mesa, lifecycle status).
        Registration fields are null for a person that exists but is not yet
        registered. institution_name is resolved from the institutions catalog.
    '''
    # Person (mining_summit_participants).
    ci: str
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    institution_id: Optional[str] = None
    institution_name: Optional[str] = None
    role: Optional[ParticipantRole] = None
    created_at: Optional[str] = None
    # Registration (mining_summit_registration); null when not registered.
    assignment_type: Optional[AssignmentType] = None
    axis: Optional[ThematicAxis] = None
    axis_label: Optional[str] = None
    mesa_code: Optional[str] = None
    status: Optional[ParticipantStatus] = None
    observation: Optional[str] = None
    replaces_ci: Optional[str] = None
    replaced_by_ci: Optional[str] = None
    registered_at: Optional[str] = None
    registered_by: Optional[str] = None
    status_changed_by: Optional[str] = Field(
        None, description = 'Operator who cancelled/replaced this registration.'
    )
    status_changed_at: Optional[str] = None
    registered: bool = Field(
        False, description = 'True when the person has an active event registration.'
    )

    model_config = ConfigDict(extra = 'ignore')


class ParticipantQuerySchema(BaseModel):
    '''
        Pydantic schema for filtering and paginating the participants list.
    '''
    department: Optional[str] = Field(None, max_length = 60)
    institution_id: Optional[str] = Field(None, max_length = 120)
    axis: Optional[ThematicAxis] = Field(None, description = 'Filter by thematic axis.')
    status: Optional[ParticipantStatus] = Field(
        None, description = 'Filter by registration status. Defaults to ACTIVE only.'
    )
    include_inactive: bool = Field(
        False, description = 'If True, include REPLACED/CANCELLED registrations.'
    )
    registered_from: Optional[str] = Field(
        None, description = 'Inclusive lower bound (YYYY-MM-DD) for the registration date.'
    )
    registered_to: Optional[str] = Field(
        None, description = 'Inclusive upper bound (YYYY-MM-DD) for the registration date.'
    )
    limit: int = Field(50, ge = 1, le = 100)
    last_evaluated_key: Optional[str] = Field(
        None, description = 'Pagination token returned by the previous page.'
    )


class ParticipantsListResponseSchema(BaseModel):
    '''
        Paginated response wrapper for participants.
    '''
    items: List[ParticipantResponseSchema]
    last_evaluated_key: Optional[str] = None
