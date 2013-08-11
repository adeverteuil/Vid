# vim:cc=80:fdm=marker:fdl=0:fdc=1
#
# __init__.py
# Copyright (C) 2013  Alexandre de Verteuil


import os
import logging
import logging.config


from .utils import *


__all__ = [
    #"Editor",
    "RAW_AUDIO",
    "RAW_VIDEO",
    "Shot",
    "Player",
    "Cat",
    "Multiplexer",
    #"Stream",
    #"VideoStream",
    #"AudioStream",
    ]


try:
    shutil.rmtree("log")
except FileNotFoundError:
    pass
os.mkdir("log")


formatters = {
    'sf': {
        'format': "{levelname} - {name} - {message}",
        'style': "{",
        },
    'ff': {
        'format': "{asctime} - {levelname} - {name}\n    {message}",
        'style': "{",
        },
    }
handlers = {
    'sh': {
        'class': "logging.StreamHandler",
        'level': "INFO",
        'formatter': "sf",
        },
    'fh': {
        'class': "logging.FileHandler",
        'level': "DEBUG",
        'formatter': "ff",
        'filename': "log/vid.log",
        },
    }
root = {
    'handlers': ["sh", "fh"],
    'level': "DEBUG",
    }
d = {
    'version': 1,
    'formatters': formatters,
    'handlers': handlers,
    'root': root,
    }
logging.config.dictConfig(d)


logger = logging.getLogger(__name__)
logger.debug('Test debug message')
logger.info('Test info message')
logger.warn('Test warn message')
logger.error('Test error message')
logger.critical('Test critical message')
