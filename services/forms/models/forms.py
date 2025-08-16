'''
   Forms Models
'''
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy import Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy import Enum as SQLAlchemyEnum

from services.db_connection import Base
from schemas.forms import FormStatus, QuestionType

class FormHeader(Base):# pylint: disable=too-few-public-methods, too-many-ancestors, too-many-ancestors
    '''
        SQLAlchemy model for the 't_form_headers' table.
        Represents the main definition/header of a form.
    '''
    __tablename__ = 't_form_headers'

    id = Column(Integer, primary_key = True, index = True)
    form_code = Column(String(50), unique = True, nullable = False, index = True)
    name = Column(String(255), nullable = False)
    status = Column(SQLAlchemyEnum(
        *[status_member.value for status_member in FormStatus.__members__.values()]),
        nullable = False, default = FormStatus.ACTIVE)
    creation_date = Column(DateTime, server_default = func.now(), nullable = False)# pylint: disable=not-callable
    user_id = Column(Integer, nullable = False, index = True)

    # Relationships: one-to-many with QuestionDetail and FormResponse
    questions = relationship(
        'QuestionDetail',
        back_populates = 'form_header',
        cascade = 'all, delete-orphan' # Deletes associated questions if form header is deleted
    )
    form_responses = relationship(
        'FormResponse',
        back_populates = 'form_header',
        cascade = 'all, delete-orphan' # Deletes associated form responses if form header is deleted
    )

class QuestionDetail(Base):# pylint: disable=too-few-public-methods, too-many-ancestors
    '''
        SQLAlchemy model for the 't_question_details' table.
        Represents individual questions within a form.
    '''
    __tablename__ = 't_question_details'

    id = Column(Integer, primary_key = True, index = True)
    form_id = Column(Integer, ForeignKey('t_form_headers.id'), nullable = False)
    question_number = Column(Integer, nullable = False)
    content = Column(Text, nullable = False)
    response_type = Column(SQLAlchemyEnum(
        *[qtype_member.value for qtype_member in QuestionType.__members__.values()]),
        nullable = False)

    # Relationships: many-to-one with FormHeader, one-to-many
    # with MultipleChoiceOption, QuestionFlow, FormAnswer
    form_header = relationship('FormHeader', back_populates = 'questions')
    options = relationship(
        'MultipleChoiceOption',
        back_populates = 'question_detail',
        cascade = 'all, delete-orphan' # Deletes associated options if question is deleted
    )
    flow_rules = relationship(
        'QuestionFlow',
        back_populates = 'question_detail',
        cascade = 'all, delete-orphan' # Deletes associated flow rules if question is deleted
    )
    answers = relationship(
        'FormAnswer',
        back_populates = 'question_detail',
        # Deletes associated answers if question is deleted
        # (less common, but for cascade consistency)
        cascade = 'all, delete-orphan'
    )

    # Constraint to ensure unique question_number per form_id
    __table_args__ = (
        UniqueConstraint('form_id', 'question_number', name = '_form_question_uc'),
    )

class MultipleChoiceOption(Base):# pylint: disable=too-few-public-methods, too-many-ancestors
    '''
        SQLAlchemy model for the 't_multiple_choice_options' table.
        Stores options for multiple choice questions.
    '''
    __tablename__ = 't_multiple_choice_options'

    id = Column(Integer, primary_key = True, index = True)
    question_id = Column(Integer, ForeignKey('t_question_details.id'), nullable = False)
    option_text = Column(String(255), nullable = False)
    order = Column(Integer, nullable = False)

    # Relationships: many-to-one with QuestionDetail
    question_detail = relationship('QuestionDetail', back_populates = 'options')

    # Constraint to ensure unique order per question_id
    __table_args__ = (
        UniqueConstraint('question_id', 'order', name = '_question_option_order_uc'),
    )

class QuestionFlow(Base):# pylint: disable=too-few-public-methods, too-many-ancestors
    '''
        SQLAlchemy model for the 't_question_flows' table.
        Defines conditional jumps between questions based on answers.
    '''
    __tablename__ = 't_question_flows'

    id = Column(Integer, primary_key = True, index = True)
    form_detail_id = Column(Integer, ForeignKey('t_question_details.id'), nullable = False)
    # Specific answer that triggers the jump (e.g., 'Si', 'No', 'Option A')
    answer_value = Column(String(255), nullable = True)
    next_question_number = Column(Integer, nullable = False)
    is_default_sequential = Column(Boolean, nullable = False, default = False)

    # Relationships: many-to-one with QuestionDetail
    question_detail = relationship('QuestionDetail', back_populates = 'flow_rules')

    # Constraint to ensure unique flow rule per question_detail_id and answer_value.
    # A question can have a default sequential flow (answer_value is NULL) and specific flows.
    __table_args__ = (
        UniqueConstraint('form_detail_id', 'answer_value', name = '_question_flow_uc'),
    )
