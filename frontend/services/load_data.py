'''
    Load data from API
'''
import streamlit as st
import pandas as pd
from services.rest import login, data_api
# from utils.environment import PARAMETERS

def login_api() -> str | None:
    '''
        Function to connect with SmartDecisions API
    '''
    # url = PARAMETERS.get('API_URL')
    url = st.secrets['API_URL']
    token = login(url)

    return token

def get_data(token: str, endpoint: str, route_id: int,#pylint: disable=R0917 disable=R0913
             day: int, primary: int = 1, dist: int = 1500) -> pd.DataFrame:#pylint: disable=R0917 disable=R0913
    '''
        Function to connect with SmartDecisions API
    '''
    # url = PARAMETERS.get('API_URL')
    url = st.secrets['API_URL']
    data = data_api(token, url, endpoint, route_id, day, primary, dist)

    return data
