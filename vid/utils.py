# vim:cc=80:fdm=marker:fdl=0:fdc=1
#
# utils.py
# Copyright (C) 2013  Alexandre de Verteuil


import io
import sys
import glob
import queue
import atexit
import os.path
import logging
import threading
import subprocess


FOLDER = "A roll"
PREFIX = "M2U"
NUMFMT = "05d"
EXT = "mpg"
EXTRA_OPTIONS = [
    "-vcodec", "libx264",
    "-crf", "23",
    "-preset", "medium",
    "-acodec", "aac",
    "-strict", "experimental",
    "-ac", "2",
    "-ar", "44100",
    "-ab", "128k",
    ]
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
h = logging.StreamHandler()
h.setLevel(logging.DEBUG)
logger.addHandler(h)
logger.info("logging started")


@atexit.register
def cleanup():
    logging.shutdown()
    for f in glob.glob("/tmp/vid*"):
        os.unlink(f)


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

    def process(self, video=None, audio=None):
        """Write audio and video to provided keyword arguments."""
        assert audio or video
        if audio:
            logger.info("Writing raw audio to {}.".format(audio))
            self.audio_process = subprocess.Popen(
                [
                    "ffmpeg",
                    "-y",
                    "-i", self.pathname,
                    "-vn",
                    "-f", "u16le",
                    "-acodec", "pcm_s16le",
                    "-ac", "2",
                    "-ar", "44100",
                    audio,
                ],
                stderr=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                )
        if video:
            logger.info("Writing raw video to {}.".format(video))
            self.video_process = subprocess.Popen(
                [
                    "ffmpeg",
                    "-y",
                    "-i", self.pathname,
                    "-an",
                    "-f", "yuv4mpegpipe",
                    "-vcodec", "rawvideo",
                    video,
                ],
                stderr=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                )

    def _merge_streams(self, video, audio, output):
        logger.info(
            "Merging {} and {} into {}.".format(
                video, audio, output
                )
            )
        cmd = [
            "ffmpeg",
            "-y",
            ]
        for k, v in self.input_args.items():
            cmd.append(k)
            if v is not None:
                cmd.append(v)
        cmd += [
            "-f", "yuv4mpegpipe", "-vcodec", "rawvideo", "-i", video,
            ]
        for k, v in self.input_args.items():
            cmd.append(k)
            if v is not None:
                cmd.append(v)
        cmd += [
            "-f", "u16le", "-acodec", "pcm_s16le",
            "-ac", "2", "-ar", "44100", "-i", audio,
            "-f", "avi",
            "-codec", "copy",
            ]
        for k, v in self.output_args.items():
            cmd.append(k)
            if v is not None:
                cmd.append(v)
        cmd += [output]
        self.merge_process = subprocess.Popen(
            cmd,
            #[
            #    "ffmpeg",
            #    "-y",
            #    "-f", "yuv4mpegpipe", "-vcodec", "rawvideo", "-i", video,
            #    "-f", "u16le", "-acodec", "pcm_s16le",
            #    "-ac", "2", "-ar", "44100", "-i", audio,
            #    "-f", "avi",
            #    "-codec", "copy",
            #    output
            #],
            stderr=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            )

    def play(self):
        """Play the footage with ffplay."""
        fifo_v = "/tmp/vid_play_v"
        fifo_a = "/tmp/vid_play_a"
        fifo_m = "/tmp/vid_play_m"
        for path in (fifo_v, fifo_a, fifo_m):
            try:
                os.mkfifo(path)
            except FileExistsError:
                pass
        self.process(video=fifo_v, audio=fifo_a)
        self._merge_streams(fifo_v, fifo_a, fifo_m)
        self._play(fifo_m)
        rv = self.player_process.wait()
        if rv > 0:
            raise subprocess.SubprocessError

    def _play(self, filename):
        logger.info("Reading {}.".format(filename))
        self.player_process = subprocess.Popen(
            [
                "ffplay",
                "-autoexit",
                "-f", "avi",
                "-vcodec", "rawvideo",
                "-acodec", "pcm_s16le", "-ac", "2", "-ar", "44100",
                "-i", filename,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            )

    def cut(self, seek=0, dur=None):
        """Sets the starting position and duration of the required frames."""
        if '-ss' in self.input_args:
            del self.input_args['-ss']
        if '-ss' in self.output_args:
            del self.output_args['-ss']
        if '-t' in self.output_args:
            del self.output_args['-t']
        float(seek)
        if seek >= 30:
            fastseek = seek - 20
            seek = 20
            self.input_args['-ss'] = str(fastseek)
        if seek > 0:
            self.output_args['-ss'] = str(seek)
        if dur:
            float(dur)
            self.output_args['-t'] = str(dur)

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
