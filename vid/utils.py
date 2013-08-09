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
import select
import atexit
import os.path
import logging
import threading
import subprocess


FASTSEEK_THRESHOLD = 30  # Seconds
RAW_VIDEO = ["-f", "yuv4mpegpipe", "-vcodec", "rawvideo", "-an"]
RAW_AUDIO = ["-f", "u16le", "-acodec", "pcm_s16le",
    "-ac", "2", "-ar", "44100", "-vn"]

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
        self.seek_time = 0  # Don't override super().seek().
        self.dur = None
        self.process = None
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

    def demux(self, video=None, audio=None, remove_header=False):
        """Write video and audio to the provided keyword arguments."""
        assert video or audio
        args = ["ffmpeg", "-y"]
        pass_fds = []

        # Define input arguments
        if (FASTSEEK_THRESHOLD is not None and
            FASTSEEK_THRESHOLD > 10 and
            self.seek_time > FASTSEEK_THRESHOLD
            ):
            fastseek = self.seek_time - (FASTSEEK_THRESHOLD - 10)
            seek = FASTSEEK_THRESHOLD - 10
            args += ["-ss", str(fastseek)]
        else:
            seek = self.seek_time  # This will actually be used for output.
        args += ["-i", "pipe:0"]  # Will read from stdin

        # Define output arguments
        if video:
            vfd = video if isinstance(video, int) else video.fileno()
            if remove_header:
                pipe_r, pipe_w = os.pipe()
                logger.info("Piping {} to {}.".format(pipe_w, pipe_r))
                logger.info("Piping {} to {}.".format(pipe_r, vfd))
                t = threading.Thread(
                    target=self._remove_header,
                    args=(pipe_r, vfd),
                    )
                t.start()
                vfd = pipe_w
            logger.info("Video pipe is {}.".format(vfd))
            args += RAW_VIDEO + ["pipe:{}".format(vfd)]
            pass_fds.append(vfd)
        if audio:
            afd = audio if isinstance(audio, int) else audio.fileno()
            args += RAW_AUDIO + ["pipe:{}".format(afd)]
            pass_fds.append(vfd)

        # Create subprocess
        print(args)
        self.process = subprocess.Popen(
            args,
            pass_fds=pass_fds,
            stderr=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stdin=self,
            )

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
