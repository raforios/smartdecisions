'''
    Rest functions
'''

# import json
import logging
from typing import Any, Dict, Union
import pandas as pd
import requests as req

logging.basicConfig(level=logging.INFO,
        format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def get_data(
    url: str,
    headers: dict = None,
    primary: int = 0,
    field: str = 'data',
    json_response: bool = True
)  -> Union[pd.DataFrame, Dict[str, Any], bytes]:
    '''
        Get data from a URL, handling JSON, binary, and other response types.
        
        Args:
            url (str): The URL to send the GET request to.
            headers (dict, optional): HTTP headers for the request. Defaults to None.
            primary (int, optional): Controls JSON normalization. 
                - 0: Normalize data based on the 'field' key.
                - 1: Normalize the entire JSON object.
            field (str, optional): The key to extract data from when primary is 0. 
                                Defaults to 'data'.
            json_response (bool, optional): If True, expects and processes a JSON response. 
                                            If False, returns raw binary content.
                                            Defaults to True.

        Returns:
            Union[pd.DataFrame, Dict[str, Any], bytes]: Processed data as a DataFrame,
                                                        a dictionary, or raw bytes,
                                                        depending on the input parameters
                                                        and the response content.
                                                        
        Raises:
            requests.exceptions.RequestException: For any HTTP or connection errors.
            Exception: For any other unexpected errors.
    '''
    if headers is None:
        headers = {}
    try :
        response = req.request(
            'GET',
            url = url,
            headers = headers,
            timeout = 600
        )
        response.raise_for_status()

        if json_response:
            data = response.json()
            if primary == 0:
                if field not in data:
                    error_msg = f'''Field {field} not found in JSON response.
                                Returning raw data.'''
                    logging.warning(error_msg)
                    return pd.json_normalize(data)
                return pd.json_normalize(data[field])
            if primary == 1:
                return pd.json_normalize(data)
            return data

        return response.content

    except req.exceptions.HTTPError as http_err:
        error_msg = f'Error - HTTP: {http_err}'
        logging.error(error_msg)
        error_msg = f'Response Text: {response.text}'
        logging.error(error_msg, exc_info = True)
        raise http_err
    except req.exceptions.ConnectionError as conn_err:
        error_msg = f'Error -  Connection: {conn_err}. Microservice Unavailable'
        logging.error(error_msg, exc_info = True)
        raise conn_err
    except Exception as error :
        error_msg = f'ERROR FROM get_data. This is why: {error}'
        logging.critical(error_msg, exc_info = True)
        raise error

def post_data(url: str, data: dict,
    headers: dict = None) -> dict:
    '''
        Post data into SmartBear API
    '''
    if headers is None:
        headers = {}
    try :
        response = req.post(
            url = url,
            json = data,
            headers = headers,
            timeout = 600
        )
        status_code = response.status_code
        logging.info(response.status_code)
        if status_code >= 300 or status_code < 200:
            logging.error('ERROR!')
        else:
            logging.info('SUCCESS!')
        response.raise_for_status()
        data = response.json()
        return data
    except req.exceptions.HTTPError as http_err:
        error_msg = f'Error - HTTP: {http_err}'
        logging.error(error_msg)
        error_msg = f'Response Text: {response.text}'
        logging.error(error_msg, exc_info = True)
        raise http_err
    except req.exceptions.ConnectionError as conn_err:
        error_msg = f'Error -  Connection: {conn_err}. Microservice Unavailable'
        logging.error(error_msg, exc_info = True)
        raise conn_err
    except Exception as error :
        error_msg = f'ERROR FROM get_data. This is why: {error}'
        logging.critical(error_msg, exc_info = True)
        raise error

def put_data(url: str, data: dict,
    headers: dict = None) -> dict:
    '''
        Put data into SmartBear API
    '''
    if headers is None:
        headers = {}
    try :
        response = req.put(
            url = url,
            data = data,
            headers = headers,
            timeout = 600
        )
        status_code = response.status_code
        logging.info(response.status_code)
        if status_code >= 300 or status_code < 200:
            logging.error('ERROR!')
        else:
            logging.info('SUCCESS!')
        response.raise_for_status()

        return {'message: ': 'Process succesfully!'} if response.text == '' else response.json()
    except req.exceptions.HTTPError as http_err:
        error_msg = f'Error - HTTP: {http_err}'
        logging.error(error_msg)
        error_msg = f'Response Text: {response.text}'
        logging.error(error_msg, exc_info = True)
        raise http_err
    except req.exceptions.ConnectionError as conn_err:
        error_msg = f'Error -  Connection: {conn_err}. Microservice Unavailable'
        logging.error(error_msg, exc_info = True)
        raise conn_err
    except Exception as error :
        error_msg = f'ERROR FROM get_data. This is why: {error}'
        logging.critical(error_msg, exc_info = True)
        raise error

def delete_data(url: str, data: dict,
    headers: dict = None) -> str:
    '''
        Delete data into SmartBear API
    '''
    if headers is None:
        headers = {}
    try :
        response = req.delete(
            url = url,
            json = data,
            headers = headers,
            timeout = 600
        )
        status_code = response.status_code
        logging.info(response.status_code)
        if status_code >= 300 or status_code < 200:
            logging.error('ERROR!')
        else:
            logging.info('SUCCESS!')
        response.raise_for_status()
        return response.json()
    except req.exceptions.HTTPError as http_err:
        error_msg = f'Error - HTTP: {http_err}'
        logging.error(error_msg)
        error_msg = f'Response Text: {response.text}'
        logging.error(error_msg, exc_info = True)
        raise http_err
    except req.exceptions.ConnectionError as conn_err:
        error_msg = f'Error -  Connection: {conn_err}. Microservice Unavailable'
        logging.error(error_msg, exc_info = True)
        raise conn_err
    except Exception as error :
        error_msg = f'ERROR FROM get_data. This is why: {error}'
        logging.critical(error_msg, exc_info = True)
        raise error
