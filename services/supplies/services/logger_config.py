'''
    Configuring Logger
'''
import os
import logging
import sys

def setup_logger(name):
    ''' 
        Logger Config
    '''
    log_level_str = os.environ.get('LOG_LEVEL', 'INFO').upper()
    level = getattr(logging, log_level_str, logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        logger.addHandler(stream_handler)
        # error_handler = logging.StreamHandler(sys.stderr)
        # error_handler.setFormatter(formatter)
        # logger.addHandler(error_handler)

    logger.propagate = False

    return logger

custom_logger = setup_logger('smartbear')
