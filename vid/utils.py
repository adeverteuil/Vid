# vim:cc=80:fdm=marker:fdl=0:fdc=1
#
# utils.py
# Copyright (C) 2013  Alexandre de Verteuil


import os
import io
import sys
import glob
import queue
import pprint
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
SUBPROCESS_LOG = "Subprocess pid {}:\n{}"


logger = logging.getLogger(__name__)
logdir = os.getcwd() + "/log"


@atexit.register
def cleanup():
    logging.shutdown()


def _redirect_stderr_to_log_file():
    # This function is passed as the preexec_fn to subprocess.Popen
    pid = os.getpid()
    file = open(logdir+"/{}.log".format(pid), "w")
    os.dup2(file.fileno(), sys.stderr.fileno())


class Shot():    #{{{
    """Abstraction for a movie file copied from the camcorder."""
    def __init__(self, number):
        self.logger = logging.getLogger(__name__+".Shot")
        self.number = int(number)
        self.seek = 0
        self.dur = None
        self.process = None
        self.v_stream = None
        self.a_stream = None
        pattern = "{folder}/*/{prefix}{number:{numfmt}}.{ext}".format(
            folder="A roll",
            prefix="M2U",
            number=self.number,
            numfmt="05d",
            ext="mpg",
            )
        try:
            self.name = glob.glob(pattern)[0]
        except IndexError as err:
            self.name = None
            raise FileNotFoundError(
                "Didn't find footage number {}.\n"
                "Pattern is \"{}\".".format(self.number, pattern)
                ) from err
        except :
            self.logger.exception("That's a new exception?!")

    def __repr__(self):
        return "<Shot({}), seek={}, dur={}>".format(
            self.number,
            self.seek,
            self.dur,
            )

    def cut(self, seek=0, dur=None):
        """Sets the starting position and duration of the required frames."""
        assert isinstance(seek, (int, float))
        if dur is not None:
            assert isinstance(seek, (int, float))
        self.seek = seek
        self.dur = dur

    def _probe(self):
        pass

    def demux(self, video=True, audio=True, remove_header=False):
        """Write video and audio as specified. Sets v_stream and a_stream.

        This method will demultiplex the shot and pipe the raw video and audio
        streams to those files. The caller is responsible for closing
        the files.

        """
        assert video or audio
        args = ["ffmpeg", "-y"]
        write_fds = []

        # Define input arguments
        if (FASTSEEK_THRESHOLD is not None and
            FASTSEEK_THRESHOLD > 10 and
            self.seek > FASTSEEK_THRESHOLD
            ):
            fastseek = self.seek - (FASTSEEK_THRESHOLD - 10)
            seek = FASTSEEK_THRESHOLD - 10
            args += ["-ss", str(fastseek)]
        else:
            seek = self.seek  # This will actually be used for output.
        args += ["-i", self.name]

        # Define output arguments
        if video:
            if remove_header:
                video1_r, video1_w = os.pipe()
                video2_r, video2_w = os.pipe()
                t = threading.Thread(
                    target=self._remove_header,
                    args=(video1_r, video2_w),
                    )
                write_fds.append(video1_w)
                self.v_stream = open(video2_r, "rb")
                if seek:
                    args += ["-ss", str(seek)]
                if self.dur:
                    args += ["-t", str(self.dur)]
                args += (RAW_VIDEO +
                         ["-filter:v", "yadif", "pipe:{}".format(video1_w)])
                t.start()
            else:
                video_fdr, video_fdw = os.pipe()
                write_fds.append(video_fdw)
                self.v_stream = open(video_fdr, "rb")
                if seek:
                    args += ["-ss", str(seek)]
                if self.dur:
                    args += ["-t", str(self.dur)]
                args += RAW_VIDEO + ["pipe:{}".format(video_fdw)]
        if audio:
            audio_fdr, audio_fdw = os.pipe()
            write_fds.append(audio_fdw)
            self.a_stream = open(audio_fdr, "rb")
            args += RAW_AUDIO + ["pipe:{}".format(audio_fdw)]

        # Create subprocess
        self.process = subprocess.Popen(
            args,
            pass_fds=write_fds,
            stdout=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            preexec_fn=_redirect_stderr_to_log_file,
            )
        for fd in write_fds:
            # Close write file descriptors.
            os.close(fd)
        self.logger.debug(
            SUBPROCESS_LOG.format(
                self.process.pid, pprint.pformat(args, indent=4)
                )
            )

    @staticmethod
    def _remove_header(input, output):
        try:
            with open(input, "rb") as input, open(output, "wb") as output:
                line = input.readline()
                assert line[0:9] == b'YUV4MPEG2' and line[-1:] == b'\n', \
                    [line, line[0:9], line[-1]]
                # An AssertionError here might mean that the seek value
                # exceeds the file length, in which case line == b''.
                shutil.copyfileobj(input, output)
        except:
            raise

#}}}
class Cat():     #{{{
    """Concatenate supplied Shot objects, provide read pipes.

    Caller is responsible for closing the pipes.

    """
    def __init__():
        pass

#}}}
class Player():  #{{{
    """ffplay

    Argument can be a path name sting, an int or a file object
    which has a fileno() method.

    """
    def __init__(self, file):
        args = ["ffplay", "-autoexit"]
        pass_fds = ()
        # Find out what is file.
        if isinstance(file, str):
            args.append(file)
        if isinstance(file, int):
            args.append("pipe:{}".format(file))
            pass_fds = (file,)
        if isinstance(file.fileno(), int):
            args.append("pipe:{}".format(file.fileno()))
            pass_fds = (file.fileno(),)
        self.process = subprocess.Popen(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            pass_fds=pass_fds,
            preexec_fn=_redirect_stderr_to_log_file,
            )
        for fd in pass_fds:
            os.close(fd)
        logger.debug(
            SUBPROCESS_LOG.format(
                self.process.pid, pprint.pformat(args, indent=4)
                )
            )
