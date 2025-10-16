'''
    Responses Schemas (Request/Response)
    This file defines Pydantic schemas related to form responses, including
    person/contact information, temporary answer storage, and final submission.
'''
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
from fastapi import Query, UploadFile
from pydantic import BaseModel, Field

# Enum for the status of a submitted form response
class FormResponseStatus(str, Enum):
    '''
        Enum for the possible statuses of a submitted form response.
        Used for tracking the review process of a completed form.
    '''
    COMPLETED = 'COMPLETED'
    REVIEWED = 'REVIEWED'
    APPROVED = 'APPROVED'
    REJECTED = 'REJECTED'
    PENDING_APPROVAL = 'PENDING_APPROVAL'
    # NEW: Default status for the form header
    CREATED = 'CREATED'

# --- Schemas for Persons (Encuestados/Entrevistados) ---
class PersonBase(BaseModel):
    '''
        Base schema for a person (encuestado/entrevistado).
    '''
    first_name: str = Field(..., description = 'First name of the person.')
    paternal_last_name: str = Field(..., description = 'Paternal last name of the person.')
    maternal_last_name: Optional[str] = Field(None,
        description = 'Maternal last name of the person.')
    email: Optional[str] = Field(None, description = 'Email address of the person.')
    phone_number: Optional[str] = Field(None,
        description = 'Primary phone number of the person.', min_length = 7, max_length = 50)
    phone_number_2: Optional[str] = Field(None,
        description = 'Secondary phone number of the person.', min_length = 7, max_length = 50)
    birth_date: Optional[datetime] = Field(None, description = 'Date of birth of the person.')
    identification_document_type: Optional[int] = Field(None,
        description = 'Type of identification document.')
    identification_number: Optional[str] = Field(None,
        description = 'Identification number (e.g., ID card, passport).')
    identification_expedition_place: Optional[int] = Field(None,
        description = 'Place of expedition for the identification document.')
    observations: Optional[str] = Field(None,
        description = 'Notes or observations about the person.')

    is_referred: Optional[bool] = Field(False,
        description = 'Indicates if the person was referred by another person.')
    referred_note: Optional[str] = Field(None,
        description = 'Notes related to the referral.')

class PersonCreate(PersonBase):
    '''
        Schema for creating a new person record.
    '''
    # pass

class PersonUpdate(BaseModel):
    '''
        Schema for updating an existing person record. All fields are optional.
    '''
    first_name: Optional[str] = None
    paternal_last_name: Optional[str] = None
    maternal_last_name: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    phone_number_2: Optional[str] = None
    birth_date: Optional[datetime] = None
    identification_document_type: Optional[int] = None
    identification_number: Optional[str] = None
    identification_expedition_place: Optional[int] = None
    affiliation_date: Optional[datetime] = None
    affiliation_user_id: Optional[int] = None
    observations: Optional[str] = None
    is_referred: Optional[bool] = None
    is_affiliated: Optional[bool] = None
    referred_note: Optional[str] = None

class PersonResponse(PersonBase):
    '''
        Response schema for a person record.
        Includes the auto-generated ID.
    '''
    id: int
    is_affiliated: bool
    affiliation_date: Optional[datetime]
    affiliation_user_id: Optional[int]

    class Config:# pylint: disable=too-few-public-methods
        '''
            PersonResponse - Config Class - To get form attributes
        '''
        from_attributes = True

class PersonListResponse(BaseModel):
    '''
        Response schema for a list of persons, useful for listings.
    '''
    items: List[PersonResponse]
    total: int

# --- Schemas for Contacts (Georeferenced Location & Time of Interaction) ---
class ContactBase(BaseModel):
    '''
        Base schema for contact/location information related to a form response.
    '''
    latitude: float = Field(..., ge = -90.0, le = 90.0,
        description = 'Latitude of the location where the response started.')
    longitude: float = Field(..., ge = -180.0, le = 180.0,
        description = 'Longitude of the location where the response started.')
    start_datetime: datetime = Field(...,
        description = 'Date and time when the response interaction started.')

class ContactCreate(ContactBase):
    '''
        Schema for creating new contact information.
        Links to a Person by ID.
    '''
    person_id: int = Field(...,
        description = 'ID of the person associated with this contact entry.')
    executed_route_point_id: int = Field(...,
        description = 'ID from the localization service for the executed point.')

class ContactResponse(ContactBase):
    '''
        Response schema for contact information.
        Includes the auto-generated ID.
    '''
    id: int
    person: PersonResponse # Nested schema for the associated person
    executed_route_point_id: int = Field(...,
        description = 'ID from the localization service for the executed point.')

    class Config:# pylint: disable=too-few-public-methods
        '''
            ContactResponse - Config Class - To get form attributes
        '''
        from_attributes = True

# --- Schemas for Form Answers (Individual Answers) ---
class FormAnswerBase(BaseModel):
    '''
        Base schema for an individual answer to a question within a form response.
    '''
    question_id: int = Field(..., description = 'ID of the question being answered.')
    answer_value: Optional[str] = Field(None, description = 'The value of the answer provided.')

class FormAnswerCreate(FormAnswerBase):
    '''
        Schema for creating a new individual form answer.
    '''
    # pass

class FormAnswerResponse(FormAnswerBase):
    '''
        Response schema for an individual form answer.
        Includes the auto-generated ID.
    '''
    id: int
    class Config:# pylint: disable=too-few-public-methods
        '''
            FormAnswerResponse - Config Class - To get form attributes
        '''
        from_attributes = True

# --- Schemas for Form Responses (Completed Forms) ---
class FormResponseBase(BaseModel):
    '''
        Base schema for a completed form response submission.
    '''
    form_id: int = Field(..., description = 'ID of the form to which these answers belong.')
    user_id: int = Field(..., description = 'User ID from the Frontend who submitted the form.')
    contact_id: int = Field(...,
        description = 'ID of the contact/location associated with this response.')
    status: str = Field(...,
        description = 'Current status of the form response (e.g., completed, reviewed).')

    rejection_reason: Optional[str] = Field(None,
        description = 'Reason for rejection if the response status is REJECTED.')
    affiliation_type: Optional[str] = Field(None,
        description = 'Type of affiliation (e.g., "new", "re-enrollment", etc.).')
    company_id: Optional[int] = Field(None)
    affiliation_number: Optional[int] = Field(None,
        description = 'Number of affiliation from 1 to N.')
    service_id: Optional[int] = Field(None,
        description = 'ID of the service associated with this response.')

class FormResponseCreate(FormResponseBase):
    '''
        Schema for creating a new completed form response.
        Includes all individual answers.
    '''
    answers: List[FormAnswerCreate] = Field(..., min_items = 1,
        description = 'List of all individual answers for this completed form.')
    person_id: int = Field(..., description = 'ID of the person associated with this response.')

class FormResponseUpdate(BaseModel):
    '''
        Schema for updating a completed form response.
        Primarily used for updating the status after review.
    '''
    user_id: Optional[int] = Field(None,
        description = 'User ID from the Frontend who submitted the form.')
    status: Optional[str] = Field(None,
        description = 'New status for the form response (e.g., reviewed, approved).')
    observations: Optional[str] = Field(None,
        description = 'Notes or observations on the status change.')
    rejection_reason: Optional[str] = Field(None,
        description = 'Reason for rejection, only required if status is REJECTED.')
    affiliation_number: Optional[int] = Field(None,
        description = 'Number of affiliation from 1 to N.')
    affiliation_type: Optional[str] = Field(None,
        description = 'Type of affiliation (e.g., "new", "re-enrollment", etc.).')

class FormResponseFlowBase(BaseModel):
    '''
        Base schema for a record in the form response status flow.
    '''
    user_id: int
    initial_status: str
    next_status: str
    observations: Optional[str] = None

class FormResponseFlowCreate(FormResponseFlowBase):
    '''
        Schema for creating a new flow record.
    '''
    form_response_id: int

class FormResponseFlowResponse(FormResponseFlowBase):
    '''
        Response schema for a form response flow record.
    '''
    id: int
    date_time: datetime

    class Config: # pylint: disable=too-few-public-methods
        '''
            This setting allows the class to be instantiated without arguments in
            the @router.get() decorator.
        '''
        from_attributes = True

class FormResponseDetailResponse(FormResponseBase):
    '''
        Response schema for a detailed completed form response.
        Includes ID, submission_date, and nested answers.
    '''
    id: int
    person_id: int = Field(..., description = 'ID of the person associated with this response.')
    submission_date: datetime = Field(...,
        description = 'Timestamp when the form response was submitted.')
    answers: List[FormAnswerResponse] = []
    contact: ContactResponse
    status_flow: List[FormResponseFlowResponse] = []

    class Config:# pylint: disable=too-few-public-methods
        '''
            FormResponseDetailResponse - Config Class - To get form attributes
        '''
        from_attributes = True

class FormResponseSummaryResponse(BaseModel):
    '''
        Summary response schema for a form response, useful for listings.
        Does not include all nested answers.
    '''
    id: int
    form_id: int
    submission_date: datetime
    status: str
    user_id: int
    contact_id: int
    company_id: Optional[int] = Field(None)
    affiliation_number: Optional[int] = Field(None)
    rejection_reason: Optional[str] = Field(None)
    affiliation_type: Optional[str] = Field(None)

    class Config:# pylint: disable=too-few-public-methods
        '''
            FormResponseSummaryResponse - Config Class - To get form attributes
        '''
        from_attributes = True

# --- Schemas for Temporary Form Session in DynamoDB (Cache) ---
class TemporaryAnswer(BaseModel):
    '''
        Schema for an individual answer stored temporarily in DynamoDB.
    '''
    question_id: int = Field(..., description = 'ID of the question.')
    question_number: int = Field(..., description = 'Number of the question.')
    answer_value: Optional[str] = Field(None,
        description = 'The value of the answer provided.')
    response_type: str = Field(...,
        description = 'Type of question response (e.g., "numeric", "true_false").')

class CurrentFormSession(BaseModel):
    '''
        Schema representing the current state of a user's form session in DynamoDB.
        This is the primary structure stored in the cache.
    '''
    session_id: str = Field(..., description = 'Unique ID for the temporary form filling session.')
    form_id: int = Field(..., description = 'ID of the form being answered.')
    current_question_number: int = Field(...,
        description = 'The number of the question currently being displayed/answered.')
    answers: Dict[str, TemporaryAnswer] = Field(default_factory = dict,
        description = '''Dictionary of answers, keyed by question_id or question_number
        for easy lookup/update.''')
    start_time: datetime = Field(..., description = 'Timestamp when the session began.')
    ttl: int = Field(..., description = '''Time-to-live for the session in Unix epoch seconds.
        Used by DynamoDB to automatically expire items.''')
    user_id: int = Field(..., description = 'User ID (from frontend)')
    contact_info_id: Optional[int] = Field(None,
        description = '''ID of the temporary contact/person record if created at session start.
        This would eventually become the definitive contact_id.''')
    contact_temp_latitude: Optional[float] = Field(None,
        description = 'Temporary latitude from session start.')
    contact_temp_longitude: Optional[float] = Field(None,
        description = 'Temporary longitude from session start.')
    person_info_id: Optional[int] = Field(None,
        description = 'ID of the person created at the start of the session.')

    rejection_reason: Optional[str] = Field(None,
        description = 'Reason for rejection if the response status is REJECTED.')
    affiliation_type: Optional[str] = Field(None,
        description = 'Type of affiliation (e.g., "new", "re-enrollment", etc.).')
    form_response_id: Optional[int] = Field(None,
        description = 'ID of the initial FormResponse record created in MySQL.')
    service_id: int = Field(...,
        description = 'ID of the service for file path generation in S3.')
# --- Schemas for Request/Response related to Question Flow and Answers ---
class StartFormSessionRequest(BaseModel):
    '''
        Request schema to initiate a new form-filling session.
        Requires form ID and initial contact/person info.
    '''
    form_id: int = Field(..., description = 'ID of the form to start answering.')
    user_id: int = Field(..., description = 'User ID (from frontend)')
    affiliation_type: str = Field(...,
        description = 'Type of affiliation (e.g., "new", "re-enrollment", etc.).')
    executed_route_point_id: int = Field(...,
        description = 'ID from the localization service for the executed point.')
    person_data: PersonCreate = Field(...,
        description = 'Initial details of the person being interviewed/surveyed.')
    contact_data: ContactBase = Field(...,
        description = 'Geospatial and time data for the start of the interaction.')
    status: Optional[str] = Field('CREATED',
        description = 'Initial status of the form header. Defaults to CREATED if not provided.')
    service_id: int = Field(...,
        description = 'ID of the service for file path generation.')
class StartFormSessionResponse(BaseModel):
    '''
        Response schema upon starting a new form session.
        Returns the first question to be displayed.
    '''
    session_id: str = Field(..., description = 'Unique ID for the temporary form filling session.')
    form_id: int = Field(..., description = 'ID of the form being answered.')
    affiliation_type: str = Field(...,
        description = 'Type of affiliation (e.g., "new", "re-enrollment", etc.).')
    question_number: int = Field(..., description = 'Number of the first question to display.')
    question_content: str = Field(..., description = 'Content of the first question.')
    response_type: str = Field(..., description = 'Expected response type of the first question.')
    options: Optional[List[Dict[str, Any]]] = Field(None,
        description = 'Options for multiple choice questions.')
    message: str = 'Form session started. Here is the first question.'
    form_response_id: int = Field(...,
        description = 'ID of the initial FormResponse record created in MySQL.')
    status: str = Field(...,
        description = 'Initial status of the form header, passed from the request.')

class SubmitAnswerRequest(BaseModel):
    '''
        Request schema for submitting an answer to a question during a form session.
    '''
    session_id: str = Field(..., description = 'ID of the temporary form filling session.')
    question_id: int = Field(..., description = 'ID of the question being answered.')
    question_number: int = Field(..., description = 'Number of the question being answered.')
    answer_value: Optional[str] = Field(None, description = 'The user\'s answer to the question.')
    uploaded_file: Optional[UploadFile] = None

class NextQuestionResponse(BaseModel):
    '''
        Response schema for the next question to be displayed or a completion message.
    '''
    session_id: str = Field(..., description = 'ID of the temporary form filling session.')
    question_number: Optional[int] = Field(None,
        description = 'Number of the next question to display. None if form is complete.')
    question_content: Optional[str] = Field(None,
        description = 'Content of the next question. None if form is complete.')
    response_type: Optional[str] = Field(None,
        description = 'Expected response type of the next question. None if form is complete.')
    options: Optional[List[Dict[str, Any]]] = Field(None,
        description = 'Options for multiple choice questions.')
    is_form_complete: bool = Field(..., description = 'True if all questions have been answered.')
    message: str = Field(...,
        description = 'Status message (e.g., "Next question", "Form completed").')
    current_answers: Optional[Dict[str, Any]] = Field(None,
        description = '''Currently recorded answers for the session,
        including the last submitted one. Keyed by question_number.''')

    company_id: Optional[int] = Field(None)
    affiliation_number: Optional[int] = Field(None)
    rejection_reason: Optional[str] = Field(None)
    affiliation_type: Optional[str] = Field(None)

class GetQuestionToModifyRequest(BaseModel):
    '''
        Request schema for retrieving a specific question and its current answer
        for modification during a session.
    '''
    session_id: str = Field(..., description = 'ID of the temporary form filling session.')
    question_number: int = Field(...,
        description = 'Number of the question to retrieve for modification.')

class GetQuestionToModifyResponse(BaseModel):
    '''
        Response schema for a specific question and its current answer for modification.
    '''
    session_id: str = Field(..., description = 'ID of the temporary form filling session.')
    question_number: int = Field(..., description = 'Number of the question.')
    question_content: str = Field(..., description = 'Content of the question.')
    response_type: str = Field(..., description = 'Expected response type of the question.')
    current_answer: Optional[str] = Field(None,
        description = 'The current answer for this question in the session.')
    options: Optional[List[Dict[str, Any]]] = Field(None,
        description = 'Options for multiple choice questions.')
    message: str = 'Question retrieved for modification.'

class UpdateAnswerInSessionRequest(BaseModel):
    '''
        Request schema for updating a specific answer within a form session.
    '''
    session_id: str = Field(..., description = 'ID of the temporary form filling session.')
    question_id: int = Field(..., description = 'ID of the question whose answer is being updated.')
    question_number: int = Field(...,
        description = 'Number of the question whose answer is being updated.')
    new_answer_value: Optional[str] = Field(None, description = 'The new value for the answer.')

class FinalizeFormRequest(BaseModel):
    '''
        Request schema to finalize a form session and persist answers.
    '''
    session_id: str = Field(..., description = 'ID of the temporary form filling session.')
    status: str = Field(...,
        description = 'Initial status of the form header, passed from the request.')

class FinalizeFormResponse(BaseModel):
    '''
        Response schema upon successful finalization of a form.
    '''
    form_response_id: int = Field(...,
        description = 'ID of the newly created permanent form response record.')
    message: str = 'Form successfully finalized and answers saved permanently.'
    affiliation_number: Optional[int] = Field(None)

class FormResponseStatusFlow(BaseModel):
    '''
        Schema to represent a single entry in the status flow history.
        Records the chronological changes in a form response's status.
    '''
    id: int = Field(..., description = 'Unique ID for the status flow entry.')
    form_response_id: int = Field(...,
        description = 'ID of the form response to which this status change belongs.')
    date_time: datetime = Field(...,
        description = 'Timestamp when the status change occurred.')
    user_id: int = Field(...,
        description = 'ID of the user who initiated the status change.')
    initial_status: str = Field(...,
        description = 'The status of the form before the change.')
    next_status: str = Field(...,
        description = 'The new status of the form after the change.')
    observations: Optional[str] = Field(None,
        description = 'Notes or observations related to the status change.')

    class Config:# pylint: disable=too-few-public-methods
        '''
            FormResponseStatusFlow - Config Class - To get form attributes
        '''
        from_attributes = True

class PersonSearchFilters(BaseModel):
    '''
        Schema to filter persons based on various criteria.
        All fields are optional, to be used as query parameters.
    '''
    identification_number: Optional[str] = Query(None,
        description = 'The identification number (e.g., ID card, passport) of the person.')
    first_name: Optional[str] = Query(None,
        description = 'The first name of the person (supports partial matching).')
    paternal_last_name: Optional[str] = Query(None,
        description = 'The paternal last name of the person (supports partial matching).')
    maternal_last_name: Optional[str] = Query(None,
        description = 'The maternal last name of the person (supports partial matching).')
    phone_number: Optional[str] = Query(None,
        description = 'The primary phone number of the person.')
    email: Optional[str] = Query(None,
        description = 'The email address of the person.')

    class Config:# pylint: disable=too-few-public-methods
        '''
            Pydantic config.
        '''
        arbitrary_types_allowed = True
