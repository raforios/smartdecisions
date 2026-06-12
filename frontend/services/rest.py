'''
    Rest functions
'''

import streamlit as st
# import json
import pandas as pd
import requests as req
# from utils.environment import PARAMETERS

def get_data(url, headers = '', primary = 0, field = 'data') -> pd.DataFrame:
    '''
        Get data from SmartDecisions API
    '''
    try :
        response = req.request(
            'GET',
            url = url,
            headers = headers,
            timeout = 600
        )
        if response.status_code >= 300 or response.status_code < 200:
            return f'SERVER ERROR: {response.status_code}'

        print(f'GET STATUS CODE: {response.status_code}')
        print('GET MESSAGE: Success!')

        data = response.json()
        if primary == 0:
            return pd.json_normalize(data[field])

        if primary == 1:
            return pd.json_normalize(data)

        return data
    except Exception as error :
        print(f'ERROR FROM get_data. This is why: {error}')
        raise error

def post_data(url, data, headers = '') -> dict:
    '''
        Post data into SmartDecisions API
    '''
    try :
        response = req.post(
            url = url,
            json = data,
            headers = headers,
            timeout = 600
        )
        status_code = response.status_code
        message = 'ERROR!' if status_code >= 300 or status_code < 200 else 'SUCCESS!'
        print()
        print(f'POST STATUS CODE: {response.status_code}')
        print(f'POST MESSAGE: {message}')
        data = response.json()
        return data
    except Exception as error :
        print(f'ERROR FROM post_data. This is why: {error}')
        raise error

def login(url) -> str:
    '''
        Login into SmartDecisions API
    '''
    data = {
        # 'email' : PARAMETERS.get('EMAIL'),
        # 'password' : PARAMETERS.get('PASSWORD')
        'email' : st.secrets['EMAIL'],
        'password' : st.secrets['PASSWORD']
    }
    endpoint_login = '/api/v1/login'
    url_login = f'{url}{endpoint_login}'
    response = post_data(url = url_login, data = data)
    if not response.get('access_token'):
        return f'ROOT CAUSE: {response}'
    return response.get('access_token')

def data_api(token, url, endpoint, route_id, day, primary, dist = 1500) -> pd.DataFrame:#pylint: disable=R0917 disable=R0913
    '''
        Extract and prepare data from SmartDecisions API and return it
    '''
    headers = {'Authorization': f'Bearer {token}'}
    endpoit_map = f'/api/v1/optimization/{endpoint}'
    url_data_map = f'{url}{endpoit_map}?route_id={route_id}&day={day}&dist={dist}'
    print()
    print(url_data_map)
    response = get_data(url = url_data_map, headers = headers, primary = primary)

    return response
