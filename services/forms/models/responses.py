'''
   Responses Models - Defines the database models for form submissions,
   including respondent (person) and contact details, and individual answers.
'''
from sqlalchemy import (
    Column,
    Integer,
    Numeric,
    String,
    DateTime,
    Text,
    ForeignKey,
    UniqueConstraint,
    Boolean,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from services.db_connection import Base

# --- Person Model (Encuestado/Entrevistado) ---
class Person(Base): # pylint: disable=too-few-public-methods, too-many-ancestors
    '''
        SQLAlchemy model for the 't_persons' table.
        Represents an individual (e.g., interviewee, surveyed person).
    '''
    __tablename__ = 't_persons'
    __table_args__ = (
        # UniqueConstraint('email', name = 'uq_person_email'),
        # UniqueConstraint('phone_number', name = 'uq_person_phone_number'),
        UniqueConstraint('identification_number', name = 'uq_person_identification_number'),
    )

    id = Column(Integer, primary_key = True, index = True)
    first_name = Column(String(255), nullable = False)
    paternal_last_name = Column(String(255), nullable = False)
    maternal_last_name = Column(String(255), nullable = True)
    email = Column(String(255), nullable = True, unique = True, index = True)
    phone_number = Column(String(50), nullable = True, unique = True, index = True)
    phone_number_2 = Column(String(50), nullable = True)
    birth_date = Column(DateTime, nullable = True)
    identification_document_type = Column(Integer, nullable = True)
    identification_number = Column(String(20), nullable = True, unique = True, index = True)
    identification_expedition_place = Column(Integer, nullable = True)
    observations = Column(String(1024), nullable = True)
    is_affiliated = Column(Boolean, default = False, nullable = False)
    affiliation_date = Column(DateTime, nullable = True)
    affiliation_user_id = Column(Integer, nullable = True)

    is_referred = Column(Boolean, default = False, nullable = False)
    referred_note = Column(Text, nullable = True)

    contacts = relationship(
        'Contact',
        back_populates = 'person',
        # cascade = 'all, delete-orphan'
    )
    form_responses = relationship(
        'FormResponse',
        back_populates = 'person'
    )

# --- Contact Model (Georeferenced Location & Time of Interaction) ---
class Contact(Base): # pylint: disable=too-few-public-methods, too-many-ancestors
    '''
        SQLAlchemy model for the 't_contacts' table.
        Stores georeferenced location and time details for an interaction.
    '''
    __tablename__ = 't_contacts'

    id = Column(Integer, primary_key = True, index = True)
    person_id = Column(Integer, ForeignKey('t_persons.id'), nullable = False)
    latitude = Column(Numeric(16, 14), nullable = False)
    longitude = Column(Numeric(16, 14), nullable = False)
    start_datetime = Column(DateTime, nullable = False)
    executed_route_point_id = Column(Integer, nullable = False)

    # Relationships: many-to-one with Person, one-to-many with FormResponse
    person = relationship('Person', back_populates = 'contacts')
    form_responses = relationship(
        'FormResponse',
        back_populates = 'contact',
        cascade = 'all, delete-orphan'
    )

# --- FormResponse Model (Completed Form Submission) ---
class FormResponse(Base): # pylint: disable=too-few-public-methods, too-many-ancestors
    '''
        SQLAlchemy model for the 't_form_responses' table.
        Represents a completed submission of a form.
    '''
    __tablename__ = 't_form_responses'
    __table_args__ = (
        UniqueConstraint('form_id', 'company_id', 'affiliation_number',
                         name = 'uq_form_company_affiliation_number'),
    )

    id = Column(Integer, primary_key = True, index = True)
    form_id = Column(Integer, ForeignKey('t_form_headers.id'), nullable = False)
    contact_id = Column(Integer, ForeignKey('t_contacts.id'), nullable = False)
    person_id = Column(Integer, ForeignKey('t_persons.id'), nullable = False)
    submission_date = Column(DateTime, server_default = func.now(), nullable = False)# pylint: disable=not-callable
    status = Column(String(50), nullable = False)
    user_id = Column(Integer, nullable = False, index = True)
    affiliation_number = Column(Integer, nullable = True)
    company_id = Column(Integer, nullable = True)

    rejection_reason = Column(Text, nullable = True)
    affiliation_type = Column(String(50), nullable = True)

    form_header = relationship('FormHeader', back_populates = 'form_responses')
    contact = relationship('Contact', back_populates = 'form_responses')

    answers = relationship(
        'FormAnswer',
        back_populates = 'form_response',
        cascade = 'all, delete-orphan'
    )
    person = relationship('Person', back_populates = 'form_responses')

    status_flow = relationship(
        'FormResponseFlow',
        back_populates='form_response',
        cascade='all, delete-orphan',
        order_by='FormResponseFlow.date_time'
    )

# --- FormAnswer Model (Individual Answer within a Submission) ---
class FormAnswer(Base): # pylint: disable=too-few-public-methods, too-many-ancestors
    '''
        SQLAlchemy model for the 't_form_answers' table.
        Stores individual answers for questions within a completed form response.
    '''
    __tablename__ = 't_form_answers'

    id = Column(Integer, primary_key = True, index = True)
    form_response_id = Column(Integer, ForeignKey('t_form_responses.id'), nullable = False)
    question_id = Column(Integer, ForeignKey('t_question_details.id'), nullable = False)
    # The actual answer value (text, number, 'Si'/'No', S3 URL)
    answer_value = Column(Text, nullable = True)

    # Relationships:
    # many-to-one with FormResponse and QuestionDetail
    form_response = relationship('FormResponse', back_populates = 'answers')
    question_detail = relationship('QuestionDetail', back_populates = 'answers')

    # Constraint to ensure unique answer per form_response_id and question_id
    __table_args__ = (
        UniqueConstraint('form_response_id', 'question_id', name = '_response_unique'),
    )

class FormResponseFlow(Base): # pylint: disable=too-few-public-methods, too-many-ancestors
    '''
        SQLAlchemy model for the 't_form_responses_flow' table.
        Records the history of status changes for each form response.
    '''
    __tablename__ = 't_form_responses_flow'

    id = Column(Integer, primary_key = True, index = True)
    form_response_id = Column(Integer, ForeignKey('t_form_responses.id'), nullable = False)
    date_time = Column(DateTime, server_default = func.now(), nullable = False)# pylint: disable=not-callable
    user_id = Column(Integer, nullable = False)
    initial_status = Column(String(50), nullable = False)
    next_status = Column(String(50), nullable = False)
    observations = Column(Text, nullable = True)

    # Relationships: many-to-one with FormResponse
    form_response = relationship('FormResponse', back_populates = 'status_flow')
