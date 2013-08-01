# vim:cc=80:fdm=marker:fdl=0:fdc=3
#
# utils.py
# Copyright (C) 2013  Alexandre de Verteuil


import sys
import glob
import os.path
import logging


FOLDER = "A roll"
PREFIX = "M2U"
NUMFMT = "05d"
EXT = "mpg"


class Shot():
    """Plays the requested file with ffplay."""

    def __init__(self, number):
        self.number = int(number)

    @property
    def pathname(self):
        assert isinstance(self.number, int)
        try:
            return glob.glob(
                "{folder}/*/{prefix}{number:{numfmt}}.{ext}".format(
                    folder=FOLDER,
                    prefix=PREFIX,
                    number=self.number,
                    numfmt=NUMFMT,
                    ext=EXT,
                    )
                )[0]
        except IndexError as err:
            raise FileNotFoundError(
                "Didn't find footage number {}.".format(self.number)
                ) from err
        except :
            logging.error("That's a new exception?!")
            logging.error(sys.exc_info())

if __name__ == "__main__":
    import sys
    player = Player(sys.argv[1])
    print(player.pathname)
