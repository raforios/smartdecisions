'''
    Frontend functions
'''

import os
import base64
from io import StringIO
import logging
from mimetypes import guess_type
from typing import List, Union
from dataclasses import asdict
import numpy as np
import pandas as pd
from lib.rest import (
    get_data,
    post_data,
    put_data,
    delete_data
)
from lib.models import (
    OptimizationParams,
    UploadFileParams,
    DeleteFileParams,
    LogisticCostParams,
    GradientDescentParams,
    NormalizeFeaturesParams,
    PredictLogisticParams,
    LinearGradientDescentParams,
    PredictLinearParams,
    LinearGradientSingleDescentParams
)
from dotenv import dotenv_values

logging.basicConfig(level = logging.INFO,
        format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

BASEDIR = os.path.dirname(os.path.abspath(__file__))
PARAMETERS = dotenv_values(os.path.join(os.path.dirname(os.path.dirname(BASEDIR)),
            'notebooks', '.env'))

def _prepare_payload_from_params(params: object) -> dict:
    '''
        Converts a parameter dataclass object into a dictionary,
        handling the conversion of NumPy arrays to JSON lists.
    '''
    payload = asdict(params)
    for key, value in payload.items():
        if isinstance(value, np.ndarray):
            payload[key] = value.tolist()
        elif isinstance(value, list):
            # Recorrer listas si contienen ndarrays (ej. listas de listas)
            processed_list = []
            for item in value:
                if isinstance(item, np.ndarray):
                    processed_list.append(item.tolist())
                else:
                    processed_list.append(item)
            payload[key] = processed_list
    return payload

 # pylint: disable=too-many-arguments,too-many-positional-arguments
def _call_api(
    token: str,
    base_url: str,
    endpoint_path: str,
    params: object = None, # Ahora acepta cualquier dataclass o None
    http_method: str = 'POST', # Puede ser 'POST' o 'DELETE'
    data_override: dict = None # Para payloads que no vienen de una dataclass (ej. login)
) -> dict:
    '''
        Generic function for making API calls (POST/DELETE).

        Args:
            token (str): Authentication token.
            base_url (str): Base URL of the API Gateway.
            endpoint_path (str): Endpoint-specific path (e.g., 
            'classification/predict-classification').
            params (object, optional): A dataclass object with parameters. 
            It will be converted to a payload.
            http_method (str): The HTTP method ('POST' or 'DELETE'). Defaults to 'POST'.
            data_override (dict, optional): A data dictionary to use as a payload directly,
            overriding the conversion of 'params'. Useful for cases like 'login'.

        Returns:
            dict: The API response.
    '''
    headers = {'Authorization': f'Bearer {token}'}
    full_url = f'{base_url}/v1/{endpoint_path}'

    if data_override:
        payload = data_override
    elif params:
        payload = _prepare_payload_from_params(params)
    else:
        payload = {}

    message = f'''Calling {http_method} {full_url} for {endpoint_path.split('/')[-1]}
    with payload: {payload}'''
    logging.info(message)

    if http_method.upper() == 'POST':
        response = post_data(url = full_url, data = payload, headers = headers)
    elif http_method.upper() == 'DELETE':
        response = delete_data(url = full_url, data = payload, headers = headers)
    else:
        raise ValueError(f'HTTP method not supported by _call_api: {http_method}')

    return response

def login(url: str, email: str = None, password: str = None) -> str:
    '''
        Login into SmartBear API.

        Args:
            url (str): The base URL of the API gateway.
            email (str, optional): User email. If None, retrieves from environment variables.
            password (str, optional): User password. If None,
            retrieves from environment variables.

        Returns:
            str: The access token if login is successful.

        Raises:
            ValueError: If login fails due to incorrect credentials or other API-level errors
                        reported by the API response.
            Exception: For unexpected errors during the HTTP request or response processing.
    '''
    message = f'BASEDIR:  {os.path.join(os.path.dirname(os.path.dirname(BASEDIR)),
            'notebooks', '.env')}'
    logging.info(message)
    login_email = email if email is not None else PARAMETERS.get('EMAIL')
    login_password = password if password is not None else PARAMETERS.get('PASSWORD')

    data = {
        'email': login_email,
        'password': login_password
    }

    endpoint_login = '/v1/auth/login'
    full_url = f'{url}{endpoint_login}'

    try:
        response_data = post_data(url = full_url, data = data)

        access_token = response_data.get('access_token')

        if access_token:
            logging.info('Login successful.')
            return access_token

        error_detail = response_data.get('detail',
                        response_data.get('message', 'Unknown login error'))
        error_message = f'Login failed: {error_detail}. Full API response: {response_data}'
        logging.error(error_message)
        raise ValueError(error_message)

    except ValueError as error:
        raise error
    except Exception as error:
        error_msg = f'An unexpected error occurred during login: {error}'
        logging.error(error_msg, exc_info = True)
        raise RuntimeError(error_msg) from error

def data_api(token: str, url: str, endpoint: str, params: OptimizationParams) -> pd.DataFrame:
    '''
        Extract and prepare data from SmartBear API and return it
    '''
    headers = {'Authorization': f'Bearer {token}'}
    # endpoint_path = f'/v1/{endpoint}'
    endpoint_path = f'/v1/optimization/{endpoint}'
    query_param = f'route_id={params.route_id}&day={params.day}&dist={params.dist}'
    full_url = f'{url}{endpoint_path}?{query_param}'
    logging.info(full_url)
    response = get_data(url = full_url, headers = headers, primary = params.primary)

    return response

def data_microservice(token: str, url: str, endpoint: str,
    data: Union[float, int, str],
    primary: int) -> Union[float, int, pd.DataFrame]:
    '''
        Extract and prepare data from SmartBear API and return it
    '''
    headers = {'Authorization': f'Bearer {token}'}
    full_url = f'{url}/v1/{endpoint}/{data}'
    message = f'Calling GET: {full_url}'
    logging.info(message)
    response = get_data(url = full_url, headers = headers, primary = primary)

    return response


def upload_file(token: str, url: str, endpoint: str, params: UploadFileParams) -> str:
    '''
        Function that reads a file from a given path and uploads it to an S3
        bucket through the use of a microservice whose URL and token are received
        as parameters
    '''
    headers = {'Authorization': f'Bearer {token}'}
    full_url = f'{url}/v1/{endpoint}'
    message = f'Calling POST: {full_url} upload file'
    logging.info(message)

    # Determinar el Content-Type para la subida
    upload_content_type, _ = guess_type(params.full_local_file_path)
    upload_content_type = upload_content_type if upload_content_type else 'application/octet-stream'

    # --- Paso 1: Solicitar la URL pre-firmada ---
    presigned_payload = {
        'bucket_name': params.bucket,
        'file_path': params.file_path,
        'file_name': params.file_name,
        'expiration_seconds': 3600,
        'validation': params.validation,
        'content_type': upload_content_type
    }

    presigned_response = post_data(full_url, data = presigned_payload, headers = headers)
    message = f'''\nStep 1: Pre-signed URL for: {params.file_name}
    for s3://{params.bucket}/{params.file_path}'''
    logging.info(message)
    # message = f'URL pre-signed: {presigned_response['presigned_url']}'
    # logging.info(message)
    message = f'The file will be uploaded to S3 Key: {presigned_response['file_key']}'
    logging.info(message)
    message = f'\nStep 2: Uploading file {params.file_name} directly to S3...'
    logging.info(message)

    try :
        with open(params.full_local_file_path, 'rb') as f:
            response = put_data(
                presigned_response['presigned_url'],
                data = f,
                headers = {'Content-Type': upload_content_type}
            )
            logging.info('\n--- API RESPONSE---')
            return response
    except Exception as error:
        error_msg = f'Unexpected error: {error}'
        logging.error(error_msg, exc_info = True)
        raise error

def read_file(
    token: str,
    url: str,
    endpoint: str,
    bucket_name: str,
    file_key: str,
    delimiter: str = None
) -> Union[pd.DataFrame, bytes, str]:
    '''
    Reads a file from S3 via the file microservice and returns its content.
    
    This function handles different file types:
    - CSV/Excel: Returns a pandas DataFrame.
    - TXT: Returns a string.
    - Binary (images, documents): Returns the raw bytes.
    '''
    headers = {'Authorization': f'Bearer {token}'}
    query_string = f'?delimiter={delimiter}' if delimiter else ''
    full_url = f'{url}/v1/{endpoint}/{bucket_name}/{file_key}{query_string}'

    try:
        response = get_data(url = full_url, headers = headers, primary = 2)

        if 'data' in response:
            return pd.DataFrame.from_records(response['data'])
        if 'content' in response:
            return response['content']
        if 'content_base64' in response:
            # Si el JSON contiene 'content_base64', decodifícalo a bytes.
            return base64.b64decode(response['content_base64'])

        logging.error('Unsupported response format from API for JSON.')
        return None

    except Exception as e:
        error_msg = f'Error reading file from API: {e}'
        logging.error(error_msg, exc_info = True)
        raise e

def list_bucket(token: str, url: str, endpoint: str, bucket: str) -> dict:
    '''
        Function that lists all the contents of a given S3 bucket name
    '''
    payload = {'bucket_name': bucket}
    return _call_api(token, url, endpoint, data_override = payload, http_method = 'POST')

def delete_file(token: str, url: str, endpoint: str, params: DeleteFileParams) -> dict:
    '''
        Function that deletes a file from an S3 bucket given the file
        and bucket names
    '''
    return _call_api(token, url, endpoint, params = params, http_method = 'DELETE')

def parse_txt_data(file_content: str, delimiter: str,
    until_col: int, skip_rows: int) -> tuple:
    '''
        Parses the contents of a TXT file (in CSV format) to extract a
        feature matrix X and a label array Y.

        Args:
            file_content (str): The contents of the TXT file as a string.

        Returns:
            tuple[np.ndarray, np.ndarray]: A tuple containing the matrix X and the array Y.
    '''
    # Usar StringIO para que numpy.loadtxt pueda leer la cadena como un archivo
    data_io = StringIO(file_content)

    data = np.loadtxt(data_io, delimiter = delimiter, skiprows = skip_rows, dtype = np.float64)
    x_matrix = data[:,:until_col]
    y = data[:,until_col]
    return x_matrix, y

def calculate_sigmoid_batch(token: str, url: str, endpoint: str,
        z_values: List[Union[float, int]]) -> List[float]:
    '''
        Calculates the sigmoid for a batch of Z-values via the classification
        microservice (POST endpoint).
        Returns:
            List[float]: A list of sigmoid values (each between 0 and 1).
    '''
    z_values_for_json = z_values.tolist() if isinstance(z_values, np.ndarray) else z_values
    payload = {'z_values': z_values_for_json}
    return _call_api(token, url, endpoint, data_override = payload, http_method = 'POST')

def calculate_cost_logistic(
    token: str,
    url: str,
    endpoint: str,
    params: LogisticCostParams
) -> float:
    '''
        Calculates the logistic regression cost via the classification
        microservice (POST endpoint).

        Args:
            token (str): Authentication token.
            url (str): Base URL of the API Gateway.
            endpoint (str): The specific endpoint path for cost calculation
            (e.g., 'classification/compute-cost-logistic').
            x_matrix (np.ndarray): Feature matrix X.
            y (np.ndarray): Target array y.
            w (np.ndarray): Weight parameters w.
            b (float): Bias parameter b.

        Returns:
            float: The calculated logistic regression cost.
    '''
    response = _call_api(token, url, endpoint, params = params, http_method = 'POST')
    return response

def calculate_gradient_logistic(
    token: str,
    url: str,
    endpoint: str,
    params: LogisticCostParams
) -> dict:
    '''
        Calculates the logistic regression gradient via the classification
        microservice (POST endpoint).

        Args:
            token (str): Authentication token.
            url (str): Base URL of the API Gateway.
            endpoint (str): The specific endpoint path for gradient calculation.
            params (LogisticCostParams): An object containing x_matrix, y, w, and b.

        Returns:
            dict: A dictionary containing 'dj_db' (float) and 'dj_dw' (List[float]).
    '''
    return _call_api(token, url, endpoint, params=params, http_method='POST')

def perform_gradient_descent_logistic(
    token: str,
    url: str,
    endpoint: str,
    params: GradientDescentParams
) -> dict:
    '''
        Performs logistic regression gradient descent via the classification
        microservice (POST endpoint).

        Args:
            token (str): Authentication token.
            url (str): Base URL of the API Gateway.
            endpoint (str): The specific endpoint path for gradient descent.
            params (GradientDescentParams): An object containing x_matrix, y,
            w_in, b_in, alpha, and num_iters.

        Returns:
            dict: A dictionary containing 'w' (final weights), 'b' (final bias),
                'J_history' (list of costs), and 'p_history' (list of [w, b] pairs).
    '''
    return _call_api(token, url, endpoint, params = params, http_method = 'POST')

def perform_prediction_logistic(
    token: str,
    url: str,
    endpoint: str,
    params: PredictLogisticParams
) -> List[int]:
    '''
        Performs logistic regression prediction via the classification microservice
        (POST endpoint).

        Args:
            token (str): Authentication token.
            url (str): Base URL of the API Gateway.
            endpoint (str): The specific endpoint path for prediction
                            (e.g., 'classification/predict-classification').
            params (PredictLogisticParams): An object containing x_matrix, w, and b for prediction.

        Returns:
            List[int]: A list of predicted labels (0 or 1).
    '''
    return _call_api(token, url, endpoint, params = params, http_method = 'POST')

def normalize_features(
    token: str,
    url: str,
    endpoint: str,
    params: NormalizeFeaturesParams
) -> dict:
    '''
        Normalizes a feature matrix X via the classification microservice
        (POST endpoint /normalize-features).

        Args:
            token (str): Authentication token.
            url (str): Base URL of the API Gateway.
            endpoint (str): The endpoint-specific path for normalization
            (e.g., 'classification/normalize-features').
            params (NormalizeFeaturesParams): An object containing the
            matrix X to normalize.

        Returns:
            dict: A dictionary containing 'x_norm' (List[List[float]]),
            'mu' (List[float]), and 'sigma' (List[float]).
    '''
    return _call_api(token, url, endpoint, params = params, http_method = 'POST')

# --- Funciones para el Microservicio de PREDICCIONES (Regresión Lineal) ---
# --- Regresión Lineal de Múltiples Características ---

def train_linear_regression(
    token: str,
    url: str,
    endpoint: str,
    params: LinearGradientDescentParams
) -> dict:
    '''
        Performs linear regression training using gradient descent via the
        prediction microservice (POST endpoint).

        Args:
            token (str): Authentication token.
            url (str): Base URL of the API Gateway.
            endpoint (str): The specific endpoint path for training.
            params (LinearGradientDescentParams): An object containing x_matrix, y,
            w_in, b_in, alpha, and num_iters.

        Returns:
            dict: A dictionary containing 'w_final' (final weights), 'b_final' (final bias),
                'J_history' (list of costs), and 'p_history' (list of [w, b] pairs).
    '''
    return _call_api(token, url, endpoint, params = params, http_method = 'POST')


def predict_linear_regression(
    token: str,
    url: str,
    endpoint: str,
    params: PredictLinearParams
) -> List[float]:
    '''
        Predicts values using learned linear regression parameters via the
        prediction microservice (POST endpoint).

        Args:
            token (str): Authentication token.
            url (str): Base URL of the API Gateway.
            endpoint (str): The specific endpoint path for prediction.
            params (PredictLinearParams): An object containing x_test, w, and b for prediction.

        Returns:
            List[float]: A list of predicted values.
    '''
    response = _call_api(token, url, endpoint, params = params, http_method = 'POST')
    return response.get('predictions', [])

def train_single_linear_regression(
    token: str,
    url: str,
    endpoint: str,
    params: LinearGradientSingleDescentParams
) -> dict:
    '''
        Performs single-feature linear regression training using gradient descent via the
        prediction microservice.
        Returns:
            dict: A dictionary containing 'w_final' (final weight), 'b_final' (final bias),
                'J_history' (list of costs), and 'p_history' (list of [w, b] pairs).
    '''
    return _call_api(token, url, endpoint, params = params, http_method = 'POST')
