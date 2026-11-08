'''
    Which modules a company's data turns on (Rafael, 8-nov-2026): the
    portal hides the ones a business does not use instead of showing them
    empty.

    The sales profile is worked out once, when the sales are stored, so
    reading a dataset's status never reads its file; a dataset stored
    before the profile existed gets it the first time its status is read.
'''
from typing import Any

import pandas as pd

from schemas.modules import ActiveModules, SalesProfile
from services.commercial import COUNTER_CLIENT

# The payment terms of a sale on credit, as the sales contract stores them.
_CREDIT = 'CREDIT'


def sales_profile(frame: pd.DataFrame) -> SalesProfile:
    '''
        What a dataset's validated sales carry.

        Args:
            frame (pd.DataFrame): The accepted sales, canonical columns.

        Returns:
            SalesProfile: Whether there are real clients, credit and locations.
    '''
    if frame.empty:
        return SalesProfile()
    names = frame['pos_name'].dropna().astype(str).str.strip() if 'pos_name' in frame else None
    terms = (frame['payment_terms'].dropna().astype(str).str.upper()
             if 'payment_terms' in frame else None)
    located = False
    if {'latitude', 'longitude'} <= set(frame.columns):
        latitude = pd.to_numeric(frame['latitude'], errors = 'coerce')
        longitude = pd.to_numeric(frame['longitude'], errors = 'coerce')
        located = bool(((latitude.fillna(0) != 0) & (longitude.fillna(0) != 0)).any())
    return SalesProfile(
        named_clients = bool(names is not None and (names[names != ''] != COUNTER_CLIENT).any()),
        credit_sales = bool(terms is not None and (terms == _CREDIT).any()),
        coordinates = located
    )


def active_modules(
    dataset: dict[str, Any],
    profile: SalesProfile
) -> ActiveModules:
    '''
        The modules a dataset turns on: its sales profile and the companions
        attached to it.

        Args:
            dataset (dict[str, Any]): The dataset item.
            profile (SalesProfile): What its sales carry.

        Returns:
            ActiveModules: What the portal shows.
    '''
    def attached(name: str) -> bool:
        return bool(dataset.get(f'{name}_s3_key'))

    return ActiveModules(
        clients = profile.named_clients,
        receivables = profile.credit_sales or attached('collections'),
        stock = attached('stock'),
        purchases = attached('purchases'),
        objectives = attached('objectives'),
        routes = profile.coordinates or attached('visits')
    )
