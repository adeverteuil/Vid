# vim:cc=80:fdm=marker:fdl=0:fdc=3
#
# utils.py
# Copyright (C) 2013  Alexandre de Verteuil


import sys
import glob
import os.path
import logging
import subprocess


FOLDER = "A roll"
PREFIX = "M2U"
NUMFMT = "05d"
EXT = "mpg"


class Shot():
    """Footage file abstraction object."""

    def __init__(self, number):
        self.number = int(number)
        pattern = "{folder}/*/{prefix}{number:{numfmt}}.{ext}".format(
            folder=FOLDER,
            prefix=PREFIX,
            number=self.number,
            numfmt=NUMFMT,
            ext=EXT,
            )
        try:
            self.pathname = glob.glob(pattern)[0]
        except IndexError as err:
            self.pathname = None
            raise FileNotFoundError(
                "Didn't find footage number {}.\n"
                "Pattern is \"{}\".".format(self.number, pattern)
                ) from err
        except :
            logging.error("That's a new exception?!")
            logging.error(sys.exc_info())

    def play(self, seek=0, dur=None):
        """Play the footage with ffplay."""
        dur = ["-t", str(dur)] if dur is not None else []
        seek = str(seek)
        with open("/tmp/timecode_drawtext", "wt") as f:
            f.write(self.pathname + "\n%{pts}\n%{n}")
        drawtext = (
            "textfile=/tmp/timecode_drawtext:"
            "y=h-text_h-20:x=30:fontcolor=red:fontsize=25:"
            "fontfile=/usr/share/fonts/TTF/ttf-inconsolata.otf"
            )
        player = subprocess.check_output(
            [
                "ffplay",
                "-autoexit",
                "-vf", "yadif,drawtext=" + drawtext,
                "-ss", seek,
                ] + dur + [
                self.pathname,
            ],
            stderr=subprocess.DEVNULL,
            )
