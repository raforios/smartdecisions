'''
    Calculations asked of ML_FUNCTIONS, the base service of calculations
    (Rafael, 17-oct-2026): the projection, the tiers by rank, the association
    rules and the route algorithm live there once, and this service asks for
    them by HTTP with the caller's token, like it asks FILES for a file.

    What stays here is what only makes sense for COMMERCIAL: which series,
    which clients, which baskets and which stops, and how the answer is shown.
'''
from typing import Any

import requests

from services.exceptions import ServiceUnavailableError
from services.logger_config import custom_logger as logger
from services.utils import API_URL, REQUEST_TIMEOUT_SECONDS


def ask_ml_functions(
    path: str,
    body: dict[str, Any],
    auth_token: str,
    error_code: str
) -> dict[str, Any]:
    '''
        Posts one calculation to ML_FUNCTIONS and returns its answer.

        Args:
            path (str): The endpoint, as `/v1/prediction/forecast`.
            body (dict[str, Any]): The request ML_FUNCTIONS defines.
            auth_token (str): The caller's Authorization header.
            error_code (str): The code the caller answers when it fails.

        Returns:
            dict[str, Any]: The JSON answer.

        Raises:
            ServiceUnavailableError: `error_code`, when ML_FUNCTIONS cannot be
                reached or refuses the calculation.
    '''
    try:
        response = requests.post(f'{API_URL}{path}', json = body,
                                 headers = {'Authorization': auth_token},
                                 timeout = REQUEST_TIMEOUT_SECONDS)
    except requests.exceptions.RequestException as error:
        error_msg = f'Network error asking ML_FUNCTIONS for {path}: {error}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(detail = error_code) from error
    if not response.ok:
        error_msg = (f'ML_FUNCTIONS refused {path}: status={response.status_code} '
                     f'body={response.text[:200]}')
        logger.error(error_msg)
        raise ServiceUnavailableError(detail = error_code)
    return response.json()


def rank_tiers(
    values: list[float],
    cuts: list[float],
    auth_token: str,
    error_code: str
) -> list[int]:
    '''
        The tier of each value by its place in the ranking (0 = the top).

        Args:
            values (list[float]): One value per member.
            cuts (list[float]): Shares of the ranking where each tier ends.
            auth_token (str): The caller's Authorization header.
            error_code (str): The code the caller answers when it fails.

        Returns:
            list[int]: The tier of each value, in the order of `values`.
    '''
    answer = ask_ml_functions('/v1/classification/tiers', {'values': values, 'cuts': cuts},
                              auth_token, error_code)
    return [int(tier) for tier in answer['tiers']]
