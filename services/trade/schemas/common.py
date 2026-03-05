'''
    Common Schemas (Request/Response)
'''
from typing import List, Optional
from datetime import datetime
from fastapi import File, Form, UploadFile
from pydantic import BaseModel, Field, ConfigDict

# --- BASE SCHEMAS ---
class BaseSchema(BaseModel):
    '''
        Base schema with `from_attributes=True` enabled to handle
        ORM objects from SQLAlchemy.
    '''
    model_config = ConfigDict(from_attributes = True)

class PhotoResponseSchema(BaseSchema):
    '''
        Response scheme for a Photo object.
    '''
    id: int = Field(
        ...,
        description = 'Photo ID'
    )
    file_url: str = Field(
        ...,
        description = 'Public URL of the file in S3.'
    )
    description: Optional[str] = Field(
        None,
        description = 'Photo description (or alt_text).'
    )
    entity_type: str = Field (
        ...,
        description = 'This is the type of element to which the photo corresponds \
        (e.g., PRODUCT, POS, BANDING).'
    )
    entity_id: int = Field(
        ...,
        description = 'Unique ID of the entity to which the photo corresponds.'
    )
    created_at: Optional[datetime] = Field(
        None,
        description = 'Upload date.'
    )

class PhotoUploadForm:# pylint: disable=too-few-public-methods
    '''
        Dependency class to group all fields
        of the photo upload form.
    '''
    # pylint: disable=too-many-arguments, too-many-positional-arguments
    def __init__(
        self,
        company_id: int = Form(..., description='ID of the company'),
        entity_type: str = Form(..., description='Entity type (e.g., PRODUCT, POS)'),
        entity_id: int = Form(..., description='ID of the entity (e.g., product_id)'),
        description: Optional[str] = Form(None, description = 'Photo Description'),
        file: UploadFile = File(..., description = 'Image file to upload')
    ):
        self.company_id = company_id
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.description = description
        self.file = file

class PhotoUploadData(BaseSchema):
    '''
        Data container for the photo upload service.
    '''
    company_id: int
    entity_type: str
    entity_id: int
    description: Optional[str]
    file: UploadFile

class PhotoListResponseSchema(BaseSchema):
    '''
        Response schema for a paginated list of Photos.
    '''
    items: List[PhotoResponseSchema]
    total: int
