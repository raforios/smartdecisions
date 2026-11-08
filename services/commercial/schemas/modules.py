'''
    The modules a company's data turns on (Rafael, 8-nov-2026).

    The reduced version is the official one: a module the business does not
    use —objectives, credit, routes— is not shown as missing, it is simply
    not there. Which ones are on is read from the data itself, never set by
    hand: the sales say whether there are real clients, credit or
    coordinates, and the companions attached say the rest.
'''
from enum import Enum

from pydantic import BaseModel, Field


class SalesProfile(BaseModel):
    '''
        What a dataset's sales carry, worked out once when they are stored.
    '''
    named_clients: bool = Field(False, description = 'Some sale names a client other than '
                                                     'the counter client.')
    credit_sales: bool = Field(False, description = 'Some sale was made on credit.')
    coordinates: bool = Field(False, description = 'Some sale carries a usable location.')


class ActiveModules(BaseModel):
    '''
        The modules the portal shows for a dataset; the rest it hides.
    '''
    clients: bool = Field(False, description = 'Analyses by client: segmentation, portfolio '
                                               'health, client card, opportunities.')
    receivables: bool = Field(False, description = 'Credit sales or payments loaded.')
    stock: bool = Field(False, description = 'Stock photos loaded.')
    purchases: bool = Field(False, description = 'Purchases loaded.')
    objectives: bool = Field(False, description = 'Objectives loaded.')
    routes: bool = Field(False, description = 'Locations in the sales or visits loaded.')


class AnalysisUnavailable(str, Enum):
    '''
        Why part of an analysis the business does use comes back empty: the
        data is not there yet. One reason, one name, wherever it shows.
    '''
    INSUFFICIENT_HISTORY = 'INSUFFICIENT_HISTORY'
    SINGLE_MONTH = 'SINGLE_MONTH'
    NO_OBJECTIVES = 'NO_OBJECTIVES'
    NO_PRICE_HISTORY = 'NO_PRICE_HISTORY'
    NO_CATEGORIES = 'NO_CATEGORIES'
