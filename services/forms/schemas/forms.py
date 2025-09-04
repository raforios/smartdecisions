'''
    Forms Schemas (Request/Response)
'''
from datetime import datetime
from typing import List, Optional
from enum import Enum
from pydantic import BaseModel, Field

# Enum for FormHeader status
class FormStatus(str, Enum):
    '''
        Enum for the possible statuses of a form header.
        'active' indicates the form is available for use.
        'inactive' indicates the form is not available.
    '''
    ACTIVE = 'ACTIVE'
    INACTIVE = 'INACTIVE'

# Enum for QuestionDetail response type
class QuestionType(str, Enum):
    '''
        Enum for the expected response type of a question.
        Defines how the answer should be captured and validated.
    '''
    TRUE_FALSE = 'TRUE_FALSE'       # Expected answer: 'Si' or 'No'
    MULTIPLE_CHOICE = 'MULTIPLE_CHOICE' # Expected answer: one of predefined options
    NUMERIC = 'NUMERIC'             # Expected answer: a number
    LITERAL = 'LITERAL'             # Expected answer: long text
    FILE_UPLOAD = 'FILE_UPLOAD'     # Expected answer: a file upload (JPG/PNG)

# --- Schemas for Multiple Choice Options ---
class MultipleChoiceOptionBase(BaseModel):
    '''
        Base schema for a multiple choice option.
    '''
    option_text: str = Field(..., description = 'Text of the multiple choice option.')
    order: int = Field(..., description = 'Order of the option within the question.')

class MultipleChoiceOptionCreate(MultipleChoiceOptionBase):
    '''
        Schema for creating a new multiple choice option.
    '''
    # pass

class MultipleChoiceOptionResponse(MultipleChoiceOptionBase):
    '''
        Response schema for a multiple choice option.
        Includes the ID of the option.
    '''
    id: int
    question_id: int # Foreign key to QuestionDetail

    class Config:# pylint: disable=too-few-public-methods
        '''
            MultipleChoiceOptionResponse - Config Class - To get form attributes
        '''
        from_attributes = True

# --- Schemas for Question Flow ---
class QuestionFlowBase(BaseModel):
    '''
        Base schema for defining the flow logic between questions.
    '''
    answer_value: Optional[str] = Field(None,
                description = '''The specific answer value that triggers this flow rule
                (e.g., "Si", "No", "Option A"). Null for default sequential flow.''')
    next_question_number: int = Field(...,
                description = 'The number of the question to jump to if the rule is met.')
    is_default_sequential: bool = Field(False,
                description = '''True if this is the default sequential flow for the current
                question (i.e., no specific answer value triggers it).''')

class QuestionFlowCreate(QuestionFlowBase):
    '''
        Schema for creating a new question flow rule.
    '''
    # pass

class QuestionFlowResponse(QuestionFlowBase):
    '''
        Response schema for a question flow rule.
        Includes the ID of the flow rule.
    '''
    id: int
    form_detail_id: int # Foreign key to QuestionDetail

    class Config:# pylint: disable=too-few-public-methods
        '''
            QuestionFlowResponse - Config Class - To get form attributes
        '''
        from_attributes = True

# --- Schemas for Question Detail ---
class QuestionDetailBase(BaseModel):
    '''
        Base schema for a form question detail.
    '''
    question_number: int = Field(...,
                description = '''Sequential number of the question within the form.
                Defines display order.''')
    content: str = Field(..., description = 'The text content of the question.')
    response_type: QuestionType = Field(...,
                description = 'Expected type of response for the question.')

class QuestionDetailCreate(QuestionDetailBase):
    '''
        Schema for creating a new form question detail.
        Includes multiple choice options and flow rules if applicable.
    '''
    options: Optional[List[MultipleChoiceOptionCreate]] = Field(None,
            description = 'List of options for multiple choice questions.')
    flow_rules: Optional[List[QuestionFlowCreate]] = Field(None,
            description = 'List of flow rules for this question.')

class QuestionDetailUpdate(QuestionDetailBase):
    '''
        Schema for updating an existing form question detail.
        All fields are optional for partial updates.
    '''
    question_number: Optional[int] = None
    content: Optional[str] = None
    response_type: Optional[QuestionType] = None
    options: Optional[List[MultipleChoiceOptionCreate]] = Field(None,
            description = 'List of options for multiple choice questions to update/replace.')
    flow_rules: Optional[List[QuestionFlowCreate]] = Field(None,
            description = 'List of flow rules for this question to update/replace.')


class QuestionDetailResponse(QuestionDetailBase):
    '''
        Response schema for a form question detail.
        Includes ID, form_id, and nested options/flow rules.
    '''
    id: int
    form_id: int # Foreign key to FormHeader
    options: List[MultipleChoiceOptionResponse] = []
    flow_rules: List[QuestionFlowResponse] = []

    class Config:# pylint: disable=too-few-public-methods
        '''
            QuestionDetailResponse - Config Class - To get form attributes
        '''
        from_attributes = True

# --- Schemas for Form Header ---
class FormHeaderBase(BaseModel):
    '''
        Base schema for a form header.
    '''
    form_code: str = Field(..., max_length = 10,
            description = 'Alphanumeric code for the form, max 10 chars, unique.')
    name: str = Field(..., description = 'Name or description of the form.')
    status: str = Field(..., description = 'Status of the form: active or inactive.')
    company_id: int = Field(..., description = 'Company ID from the Frontend.')
    app_id: int = Field(..., description = 'Application ID from the Frontend.')

class FormHeaderCreate(FormHeaderBase):
    '''
        Schema for creating a new form header.
        Includes a list of question details to create the full form.
    '''
    questions: List[QuestionDetailCreate] = Field(..., min_items = 1,
            description = 'List of question details for the form.')

class FormFilters(BaseModel):
    '''
        Schema for FormFilters
    '''
    company_id: Optional[int] = Field(None,
            description = 'The ID of the company to filter by')
    form_code: Optional[str] = Field(None,
            description = 'The unique code of the form to filter by')
    name: Optional[str] = Field(None,
            description = 'The name of the form (supports partial matching)')
    status: Optional[str] = Field(None,
            description = 'The status of the form to filter by')
class FormHeaderUpdate(FormHeaderBase):
    '''
        Schema for updating an existing form header.
        All fields are optional for partial updates.
    '''
    form_code: Optional[str] = Field(None, max_length = 10)
    name: Optional[str] = None
    status: Optional[str] = None
    company_id: Optional[int] = None
    app_id: Optional[int] = None
    # Questions are updated via their own endpoints (e.g.,
    # PUT /forms/{formId}/questions/{questionId})
    # or a dedicated endpoint for bulk updates if needed, not directly
    # via header update.

class FormHeaderResponse(FormHeaderBase):
    '''
        Response schema for a form header.
        Includes ID, creation_date, and nested question details.
    '''
    id: int
    creation_date: datetime = Field(...,
                description = 'Autogenerated creation timestamp from the server.')
    questions: List[QuestionDetailResponse] = []

    class Config:# pylint: disable=too-few-public-methods
        '''
            FormHeaderResponse - Config Class - To get form attributes
        '''
        from_attributes = True
