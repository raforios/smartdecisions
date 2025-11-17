'''
    Load environment variables
'''
import os
from typing import Dict, Any, Type
from dotenv import dotenv_values
from services.logger_config import custom_logger as logger
from services.exceptions import ServiceUnavailableError

def load_and_validate_env_vars(
    env_vars: Dict[str, Type],
    optional_env_vars: Dict[str, Type] = None
) -> Dict[str, Any]:
    '''
        Loads and validates a dictionary of environment variables,
        with optional fallback to .env file.
        Args:
            env_vars (Dict[str, Type]): Dictionary of required variable names and their types.
            optional_env_vars (Dict[str, Type]): Dictionary of optional variable names and
            their types.
        Returns:
            Dict[str, Any]: A dictionary with the loaded and validated values.
        Raises:
            ServiceUnavailableError: If a required variable is missing or has an invalid type.
    '''
    loaded_values = {}
    local_env_params = dotenv_values('.env') if os.path.exists('.env') else {}

    # Combine required and optional variables for a single loop
    all_env_vars = {}
    all_env_vars.update(env_vars)
    if optional_env_vars:
        all_env_vars.update(optional_env_vars)

    for var_name, var_type in all_env_vars.items():
        # Prioritize system environment variables over .env file
        value = os.environ.get(var_name) or local_env_params.get(var_name)

        # Check if the variable is required and missing
        if not value and var_name in env_vars:
            error_msg = f'Required environment variable: {var_name} is not configured.'
            logger.critical(error_msg)
            raise ServiceUnavailableError(detail = error_msg)

        if value:
            try:
                loaded_values[var_name] = var_type(value)
            except (TypeError, ValueError) as e:
                error_msg = f'Environment variable: {var_name} is not a valid {
                    var_type.__name__}.'
                logger.critical(error_msg)
                raise ServiceUnavailableError(detail = error_msg) from e
        else:
            # For optional variables that are not set, assign a default of None
            loaded_values[var_name] = None

    return loaded_values
