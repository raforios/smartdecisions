'''
    ETL Schemas for the Mining Summit participant batch load.

    The load endpoint itself is multipart/form-data (file + form fields); these
    schemas describe the JSON summary it returns, including the not-accredited
    report kept as evidence (constancia).
'''
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ResponsibleSchema(BaseModel):
    '''
        The institution's responsible person that accompanies each file and
        receives the consolidated accreditation document.
    '''
    name: str = Field(..., min_length = 1, max_length = 120)
    phone: str = Field(..., min_length = 1, max_length = 30)

    model_config = ConfigDict(extra = 'ignore')


class EtlAcceptedSchema(BaseModel):
    '''
        A participant successfully accredited by the load.
    '''
    ci: str
    first_name: str
    last_name: str
    axis: str
    axis_label: str
    mesa_code: str


class EtlRejectedSchema(BaseModel):
    '''
        A spreadsheet row that could not be accredited, with the reason. Feeds
        the not-accredited report (constancia).
    '''
    row: int = Field(..., description = 'Spreadsheet row number (1-based, header excluded).')
    ci: Optional[str] = None
    reason: str


class EtlLoadResponseSchema(BaseModel):
    '''
        Summary of a participant batch load for a single institution file.
    '''
    batch_id: str
    institution_id: str
    institution_name: str
    role: str
    cupos: int
    already_accredited: int = Field(
        ..., description = 'Active participants of the institution before this load.'
    )
    accepted_count: int
    rejected_count: int
    responsible: ResponsibleSchema
    accepted: List[EtlAcceptedSchema]
    rejected: List[EtlRejectedSchema]
