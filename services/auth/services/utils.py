'''
    Utils service
'''
from datetime import datetime
from zoneinfo import ZoneInfo
from services.environment import load_and_validate_env_vars

# Loads the environment variables this module needs
ENV_VARS = load_and_validate_env_vars(
    {
        'TARGET_TIMEZONE': str
    }
)

TARGET_TIMEZONE = ENV_VARS['TARGET_TIMEZONE']

def get_current_time_gmt() -> datetime:
    '''
        Returns the current datetime object aware of the target timezone.
        This function should be used as the default value for all SQLAlchemy 
        DateTime columns to ensure database consistency.
    '''
    tz = ZoneInfo(TARGET_TIMEZONE)
    return datetime.now(tz = tz)
