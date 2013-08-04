# vim:cc=80:fdm=marker:fdl=0:fdc=1
#
# utils.py
# Copyright (C) 2013  Alexandre de Verteuil


import io
import sys
import glob
import queue
import os.path
import logging
import threading
import subprocess


FOLDER = "A roll"
PREFIX = "M2U"
NUMFMT = "05d"
EXT = "mpg"
logger = logging.getLogger(__name__)


class Shot():
    """Footage file abstraction object."""
    def __init__(self, number):
        self.number = int(number)
        self.input_args = dict()
        self.output_args = dict()
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
            logger.exception("That's a new exception?!")

    def play(self, seek=0, dur=None):
        """Play the footage with ffplay."""
        fd = self.cut(seek, dur, audio=False)
        self._pipe_to_player(fd, self.pathname)

    @staticmethod
    def _pipe_to_player(fd, textline=None):
        with open("/tmp/timecode_drawtext", "wt") as f:
            if textline:
                f.write(textline + "\n")
            f.write("%{pts}\n%{n}")
        drawtext = (
            "textfile=/tmp/timecode_drawtext:"
            "y=h-text_h-20:x=30:fontcolor=red:fontsize=25:"
            "fontfile=/usr/share/fonts/TTF/ttf-inconsolata.otf"
            )
        cmd = [
            "ffplay",
            "-autoexit",
            "-vf", "yadif,drawtext=" + drawtext,
            #"-ss", seek,
            #] + dur + [
            "-f", "yuv4mpegpipe",
            "pipe:0",
            ]
        player = subprocess.Popen(
            cmd,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            )
        player.stdin.write(fd.read())
        player.stdin.close()
        returncode = player.wait()
        if returncode > 0:
            raise subprocess.CalledProcessError(returncode, cmd, "")

    def cut(self, seek=0, dur=None):
        """Sets the starting position and duration of the required frames."""
        float(seek)
        if seek >= 30:
            fastseek = seek - 20
            seek = 20
            self.input_args['seek'] = ["-ss", str(fastseek)]
        self.output_args['seek'] = ["-ss", str(seek)]
        if dur:
            float(dur)
            self.output_args['duration'] = ["-t", str(dur)]

    def add_filter(self, filter, **kwargs):
        """Append filter and its arguments to the filter list."""
        try:
            vf = [self.output_args['vf']]
        except KeyError:
            vf = []
        args = []
        for k, v in kwargs.items():
            args.append(k + "=" + v)
        args = ":".join(args)
        filter = filter + "=" + args
        vf.append(filter)
        self.output_args['vf'] = ",".join(vf)

    def drawtext(self, textline="", **kwargs):
        """Shortcut to add drawtext filter with default values."""
        #with open("/tmp/timecode_drawtext", "wt") as f:
        #    if textline:
        #        f.write(textline + "\n")
        #    f.write("%{pts}\n%{n}")
        arguments = {
            'text': textline + "\n%{pts}\n%{n}",
            'y': "h-text_h-20", 'x': 30,
            'fontcolor': "red", 'fontsize': "25",
            'fontfile': "/usr/share/fonts/TTF/ttf-inconsolata.otf",
            }
        arguments.update(**kwargs)
        self.add_filter("drawtext", arguments)
        
        

class Cat():
    """Concatenates video streams.

    Threading help from this StackOverflow post:
    http://stackoverflow.com/questions/2829329/catch-a-threads-exception-in-the-caller-thread-in-python

    """

    def __init__(self, sequences, video=None, audio=None):
        self.sequences = sequences
        self.video = None
        self.audio = None
        self.bucket = queue.Queue()
        threads = []
        if video is not None:
            self.vthread = threading.Thread(
                target=self._cat,
                args=("v", video),
                )
            self.vthread.start()
            threads.append(self.vthread)
        if audio is not None:
            self.athread = threading.Thread(
                target=self._cat,
                args=("a", audio),
                )
            self.athread.start()
            threads.append(self.athread)
        while threads:
            for thread in threads:
                thread.join(0.1)
                if thread.is_alive():
                    continue
                else:
                    threads.remove(thread)
        try:
            exc = self.bucket.get(block=False)
        except queue.Empty:
            pass
        else:
            exc_type, exc_obj, exc_trace = exc
            raise exc_obj

    def _cat(self, stream, fd):
        """Concatenates streams, return file object.

        self.sequences is an iterator of tuples whose first item is the
        footage identifier, the second item is the seek position and the
        optional third is the clip duration.

        Returns a file object of the contatenated streams.

        If both audio and video are true, then a tuple of file object is
        returned as (video_stream, audio_stream).  If either audio or
        video is false, then only a file object is returned.

        At least one of video or audio must be true.

        """
        assert stream == "a" or stream == "v"
        audio = True if stream == "a" else False
        video = True if stream == "v" else False
        header = True
        try:
            for sequence in self.sequences:
                cut = Shot(sequence[0]).cut(
                    *sequence[1:],
                    audio=audio,
                    video=video,
                    header=header
                    )
                #if not header:
                #    print(cut.readline())
                fd.write(
                    cut.read()
                    )
                cut.close()
                header = False
            fd.close()
        except:
            self.bucket.put(sys.exc_info())
