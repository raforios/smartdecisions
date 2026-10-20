''' API Client module mapped strictly to the backend endpoints. '''
import requests
import streamlit as st
from utils.config import API_BASE_URL

def _get_headers():
    token = st.session_state.get('auth_token')
    return {'Authorization': f'Bearer {token}'} if token else {}

def fetch_mineral_prices():
    url = f'{API_BASE_URL}/prices'
    res = requests.get(url, headers=_get_headers())
    return res.json() if res.status_code == 200 else []

def fetch_daily_mineral_report(ref_date):
    '''
    Fetches the daily mineral report (Minerales_01).

    Args:
        ref_date (datetime.date | str): Reference date in YYYY-MM-DD.

    Returns:
        dict: API payload with 'rows' or an empty dict on failure.
    '''
    url = f'{API_BASE_URL}/reports/daily'
    res = requests.get(url, params={'date': str(ref_date)}, headers=_get_headers())
    return res.json() if res.status_code == 200 else {}


def fetch_biweekly_mineral_report(year, month, half):
    '''
    Fetches the biweekly official mineral report (Minerales_02).

    Args:
        year (int): Calendar year.
        month (int): Month 1-12.
        half (int): 1 for days 1-15, 2 for 16-end.

    Returns:
        dict: API payload with 'rows' or an empty dict on failure.
    '''
    url = f'{API_BASE_URL}/reports/biweekly'
    res = requests.get(
        url,
        params={'year': year, 'month': month, 'half': half},
        headers=_get_headers(),
    )
    return res.json() if res.status_code == 200 else {}
