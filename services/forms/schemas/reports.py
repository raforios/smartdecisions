'''
    Reports Schemas (Request/Response)
'''

from datetime import date
from typing import List, Optional
from pydantic import BaseModel, Field

class AffiliationMonitorRequestSchema(BaseModel):
    '''
        Schema to handle the request payload for the Affiliation Monitor report.
        It includes all required and optional filtering variables and objective metrics.
    '''
    # --- Required Filtering Variables ---
    company_id: int = Field(...,
            description = 'ID of the company to filter affiliations.')
    service_id: int = Field(...,
            description = 'ID of the service to filter affiliations.')
    year: Optional[int] = Field(None,
            description = 'Year of management for the affiliations.')
    period: Optional[str] = Field(None,
            description = 'Period for the affiliations (e.g., "Q1", "January", "2025-01").')

    # --- Optional Filtering Variables ---
    date_from: Optional[date] = Field(None,
            description = 'Start date of the affiliation registration range.')
    date_to: Optional[date] = Field(None,
            description = 'End date of the affiliation registration range.')
    planned_route_ids: Optional[List[int]] = Field(None,
            description = 'List of planned route IDs to include.')
    affiliation_number_from: Optional[int] = Field(None,
            description = 'Start of the affiliation number range.')
    affiliation_number_to: Optional[int] = Field(None,
            description = 'End of the affiliation number range.')
    statuses: Optional[List[str]] = Field(None,
            description = 'List of affiliation statuses to include.')
    team_ids: Optional[List[int]] = Field(None,
            description = 'List of work team IDs to include.')
    user_ids: Optional[List[int]] = Field(None,
            description = 'List of affiliate user IDs to include.')
    city_ids: Optional[List[int]] = Field(None,
            description = 'List of city IDs to include.')

    # --- Objective Metrics (from other client applications) ---
    target_status: str = Field(...,
            description = 'The target status for an approved affiliation.')
    target_affiliations: int = Field(...,
            description = 'The quantity of target affiliations per affiliate.')
    working_days: int = Field(...,
            description = 'The number of working days in the period.')

    class Config: # pylint: disable=too-few-public-methods
        '''
            Pydantic config.
        '''
        from_attributes = True

# --- Sub-object for the "Records" table data ---
class RecordsSummary(BaseModel):
    '''
        Summary of registered affiliations, contacts, and persons.
        Maps to the "Cuadro de Registros" section.
    '''
    q_contacts_marked: int = Field(...,
            description = 'Quantity of registered contacts.')
    q_persons_registered: int = Field(...,
            description = 'Quantity of registered persons.')
    q_affiliations_registered: int = Field(...,
            description = 'Quantity of registered affiliations (all statuses).')
    q_affiliations_approved: int = Field(...,
            description = 'Quantity of approved affiliations (with target status).')
    percent_affiliations_approved: float = Field(...,
            description = 'Percentage of approved affiliations.')
    q_referred_registered: int = Field(...,
            description = 'Quantity of registered referred persons.')

# --- Sub-object for the "Goals" table data ---
class ObjectivesSummary(BaseModel):
    '''
        Summary of objectives for the selected period.
        Maps to the "Cuadro de Objetivos" section.
    '''
    working_days_in_period: int = Field(...,
            description = 'Total working days in the period.')
    period_target: int = Field(...,
            description = 'Total target affiliations for the period.')
    daily_target: float = Field(...,
            description = 'Daily target of affiliations.')

# --- Sub-object for the "Indicators" table data ---
class IndicatorsSummary(BaseModel):
    '''
        Summary of key performance indicators (KPIs).
        Maps to the "Cuadro de Indicadores" section.
    '''
    ratio: float = Field(...,
            description = 'Average of approved affiliations per day.')
    individual_ratio: float = Field(...,
            description = 'Average of approved affiliations per day per affiliate.')
    daily_need: float = Field(...,
            description = 'Daily need to reach the period target.')

# --- Main Response Scheme ---
class AffiliationMonitorResponseSchema(BaseModel):
    '''
        Main response schema for the Affiliation Monitor report.
        Groups the results into logical sub-objects for frontend consumption.
    '''
    records: RecordsSummary = Field(...,
            description = 'Report data for the "Records" section.')
    objectives: ObjectivesSummary = Field(...,
            description = 'Report data for the "Objectives" section.')
    indicators: IndicatorsSummary = Field(...,
            description = 'Report data for the "Indicators" section.')

class ContactsByRouteReportRequestSchema(BaseModel):
    '''
        Schema to handle the request payload for the "Forms by Points and Contact" report.
        Includes all required and optional filtering variables.
    '''
    # --- Required Filtering Variables ---
    company_id: Optional[int] = Field(None,
            description = 'ID of the company to filter the report.')
    service_id:  Optional[int] = Field(None,
            description = 'ID of the service to filter the report.')

    # --- Date Filter (Required) ---
    submission_date_from: date = Field(...,
            description = 'Start date for the form submission date range.')
    submission_date_to: date = Field(...,
            description = 'End date for the form submission date range.')

    # --- Optional Filtering Variables ---
    affiliation_number_start: Optional[int] = Field(None,
            description = 'Start of the affiliation number range.')
    affiliation_number_end: Optional[int] = Field(None,
            description = 'End of the affiliation number range.')
    team_id: Optional[int] = Field(None,
            description = 'Team ID to include.')
    user_ids: Optional[List[int]] = Field(None,
            description = 'List of user IDs (affiliator) to include.')
    city_id: Optional[int] = Field(None,
            description = 'City ID to include.')
    planned_route_ids: Optional[List[int]] = Field(None,
            description = 'Planned route IDs to include.', min_length=1)
    status: Optional[List[str]] = Field(None,
            description = 'List of form statuses to include.')

    class Config: # pylint: disable=too-few-public-methods
        '''
            Pydantic config for the schema.
        '''
        from_attributes = True
