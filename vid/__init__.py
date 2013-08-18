# __init__.py
# Copyright © 2013  Alexandre de Verteuil        {{{1
#
# This file is part of Vid.
#
# Vid is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# Vid is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#}}}
# vim:cc=80:fdm=marker:fdl=0:fdc=1


import os
import logging
import logging.config
import textwrap


from .utils import *


__all__ = [
    "RAW_AUDIO",
    "RAW_VIDEO",
    "RemoveHeader",
    "ConcatenateStreams",
    "ConcatenateShots",
    "Shot",
    "Player",
    "Multiplexer",
    "SubprocessSupervisor",
    ]


try:
    shutil.rmtree("log")
except FileNotFoundError:
    pass
os.mkdir("log")


msg_indent = textwrap.TextWrapper(
    width=79,
    expand_tabs=True,
    tabsize=4,
    replace_whitespace=False,
    initial_indent="    ",
    subsequent_indent="    ",
    break_on_hyphens=False,
    )


class CustomFormatter(logging.Formatter):
    """Wraps long lines in log messages and indents by 4 spaces.

    Example log entry:
    2013-08-11 19:02:41,231 - DEBUG - vid.utils.Multiplexer
        Subprocess pid 14479:
        ['ffmpeg', '-y', '-f', 'yuv4mpegpipe', '-vcodec', 'rawvideo',
        '-i', 'pipe:4', '-f', 'u16le', '-acodec', 'pcm_s16le', '-ac',
        '2', '-ar', '44100', '-i', 'pipe:6', '-f', 'avi', '-vcodec',
        'libx264', '-crf', '23', '-preset', 'medium', '-acodec', 'mp3',
        '-strict', 'experimental', '-ac', '2', '-ar', '44100', '-ab',
        '128k', '-qscale:v', '6', 'pipe:1']

    """
    def format(self, record):
        #import pdb; pdb.set_trace()
        msg = []
        for line in record.msg.split("\n"):
            msg.append(msg_indent.fill(line))
        record.msg = "\n".join(msg)
        return super().format(record)


formatters = {
    'sf': {
        'format': "{levelname} - {name} - {message}",
        'style': "{",
        },
    'ff': {
        'format': "{asctime} - {levelname} - {name}\n{message}",
        '()': CustomFormatter,
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
        'filename': "log/main.log".format(os.getpid()),
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


logging.debug("My pid is {}.".format(os.getpid()))


#logger = logging.getLogger(__name__)
#logger.debug('Test debug message')
#logger.info('Test info message')
#logger.warn('Test warn message')
#logger.error('Test error message')
#logger.critical('Test critical message')
