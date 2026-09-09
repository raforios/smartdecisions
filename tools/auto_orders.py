'''    
    Def: AUTHOMATIZATION ORDERS
'''
import json
import os
import sys
import requests as req
import pandas as pd
from datetime import datetime

def get_data(url, auth = '', headers = '', params = '', primary = True, field = 'data'):
    '''
        Def: Getting data from an API
        Args:
            url: API's url to get data
            auth: If the API nees a authorization string
            headers: Headers if the API need them
            params: Params if the API need them
            primary: True by default: If the response from API has the "data's"
            attribute or not
        Returns:
            SERVER ERROR: + status_code
            df: Pandas Data Frame
    '''
    try :
        response = req.request(
            'GET',
            url = url,
            headers = headers,
            auth = auth,
            params = params,
            timeout = 600
        )
        if response.status_code >= 300 or response.status_code < 200:
            return f'SERVER ERROR: {response.status_code}'
            # return response.status_code
        print(response.status_code)
        print('Success!')
        data = response.json()
        # print(json.dumps(data, indent = 4, sort_keys = True))
        df = pd.json_normalize(data[field]) if primary else data
        return df
    except Exception as error :
        print(f'ERROR FROM get_data. This is why: {error}')
        raise

def post_data(url, data, headers = ''):
    '''
        Def: Posting data into an API
        Args:
            url: API's url to get data
            data: if the POST request needs data into the payload
            headers: Headers if the API need them
        Returns:
            SERVER ERROR: + status_code
            data: Dictionary
    '''
    try :
        response = req.post(
            url = url,
            json = data,
            headers = headers,
            timeout = 600
        )
        if response.status_code >= 300 or response.status_code < 200:
            return f'SERVER ERROR: {response.text}'
        print(response.status_code)
        print('Success!')
        data = response.json()
        return data
    except Exception as error :
        print(f'ERROR FROM post_data. This is why: {error}')
        raise

def login(url) -> str :
    '''
        Def: Getting login from an API
        Args:
            url: API's url to get data
        Returns:
            token: JSON TOKEN
    '''
    data = {
        'username' : 'raforios@gmail.com',
        'password' : 'MotoAzud'
    }
    endpoint_login = '/auth/login'
    url_login = f'{url}/{endpoint_login}'
    response = post_data(url = url_login, data = data)
    return response['token']

def orders(token, url, destination_path, status, num_days) -> str :
    '''
        Def: Executing the orders from an API BEES to API VENDER
        Args:
            main_url: API's url to get data
            token: JSON TOKEN
            destination: Path to save the file
        Returns:
            output: JSON OBJECT
    '''
    now = datetime.now()
    day = now.strftime('%Y-%m-%d %H:%M:%S')
    headers = {'Authorization': f'Bearer {token}'}
    endpoit_orders = f'/api/v1/orders/{'cancel' if status == 'PENDING_CANCELLATION' else 'load'}'
    status_request = f'status={status}'
    days_request = f'numDays={num_days}'
    url_orders = f'{url}/{endpoit_orders}?{status_request}&{days_request}'
    response_orders = get_data(url = url_orders, headers = headers, primary = False)
    output = json.dumps(response_orders, indent = 4, sort_keys = True)
    with open(destination_path, 'w+', encoding='utf-8') as file :
        file.write(f'{day}\n\n')
        file.write(output)
    return output

def main():
    '''
        Def: Main function
        Args:
        Returns:
    '''
    filename = 'Orders'
    destination_folder = os.path.join(os.getcwd(), '')
    destination_path = os.path.join(destination_folder, f'{filename}.log')
    protocol = sys.argv[1]
    link = sys.argv[2]
    port = int(sys.argv[3])
    status = sys.argv[4]
    num_days = int(sys.argv[5])
    url = f'{protocol}://{link}:{port}' if (port > 0) else f'{protocol}://{link}'
    # url = 'http://localhost:8008'
    # url = 'http://10.235.2.112:8008'

    token = login(url)
    output = orders(token, url, destination_path, status, num_days)
    print(output)

if __name__ == "__main__":
    main()
