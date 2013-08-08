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
    def __init__(self):
        pass


class Shot(io.FileIO):
    """Abstraction for a movie file copied from the camcorder."""
    def __init__(self, number):
        self.number = int(number)
        self.seek = 0
        self.dur = None
        pattern = "{folder}/*/{prefix}{number:{numfmt}}.{ext}".format(
            folder="A roll",
            prefix="M2U",
            number=self.number,
            numfmt="05d",
            ext="mpg",
            )
        try:
            pathname = glob.glob(pattern)[0]
        except IndexError as err:
            pathname = None
            raise FileNotFoundError(
                "Didn't find footage number {}.\n"
                "Pattern is \"{}\".".format(self.number, pattern)
                ) from err
        except :
            logger.exception("That's a new exception?!")
        super().__init__(pathname, "rb")

    #def __repr__(self):
    #    return "<Shot #{}, seek {}, dur {}>".format(
    #        self.number, self.seek, self.dur
    #        )

    def cut(self):
        pass


class Demuxer():
    pass


class Muxer():
    pass


class Black(Shot):
    """Generates silence on audio and black frames on video."""
    pass

class Stream():
    """Base class for a video or audio stream."""
    pass


class VideoStream(Stream):
    pass


class AudioStream(Stream):
    pass
