# vim:cc=80:fdm=marker:fdl=0:fdc=1
#
# utils.py
# Copyright (C) 2013  Alexandre de Verteuil


import os
import io
import sys
import glob
import queue
import shutil
import atexit
import os.path
import logging
import threading
import subprocess


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
h = logging.StreamHandler()
h.setLevel(logging.DEBUG)
logger.addHandler(h)
logger.info("Logging started.")


@atexit.register
def cleanup():
    logging.shutdown()


class Editor():
    """The Editor fetches streams, applies filters and outputs a movie.

    """
    def __init__():
        pass


class Shot():
    """Abstraction for a movie file copied from the camcorder."""
    def __init__():
        pass


class Stream():
    """Base class for a video or audio stream."""
    pass


class VideoStream(Stream):
    pass


class AudioStream(Stream):
    pass
