# vim:cc=80:fdm=marker:fdl=0:fdc=1
#
# utils.py
# Copyright (C) 2013  Alexandre de Verteuil


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
        self.seek = 0
        self.dur = None
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

    def __repr__(self):
        return "<Shot #{}, seek {}, dur {}>".format(
            self.number, self.seek, self.dur
            )

    def process(self, video=None, audio=None, remove_header=False):
        """Write audio and video to provided keyword arguments."""
        assert audio or video
        input_args = []
        output_args = []
        for k, v in self.input_args.items():
            input_args += [k]
            if v:
                input_args += [v]
        for k, v in self.output_args.items():
            output_args += [k]
            if v:
                output_args += [v]
        if audio:
            logger.info("Writing raw audio to {}.".format(audio))
            self.audio_process = subprocess.Popen(
                [
                    "ffmpeg",
                    "-y",
                    ] + input_args + [
                    "-i", self.pathname,
                    ] + output_args + [
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
            if remove_header:
                self.thread_header_remover = threading.Thread(
                    target=self._remove_header,
                    args=(video + "_h", video)
                    )
                video += "_h"
                try:
                    os.mkfifo(video)
                except FileExistsError:
                    pass
                logger.info(
                    "Removing header because {}.".format(remove_header)
                    )
                self.thread_header_remover.start()
            logger.info("Writing raw video to {}.".format(video))
            self.video_process = subprocess.Popen(
                [
                    "ffmpeg",
                    "-y",
                    ] + input_args + [
                    "-i", self.pathname,
                    ] + output_args + [
                    "-an",
                    "-f", "yuv4mpegpipe",
                    "-vcodec", "rawvideo",
                    video,
                ],
                stderr=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                )

    def _remove_header(self, input, output):
        logger.info(
            "Removing header from {}, piping to {}.".format(input, output)
            )
        with open(input, "rb") as input, open(output, "wb") as output:
            line = input.readline()
            assert line == (
                b'YUV4MPEG2 W720 H480 F30000:1001 '
                b'It A32:27 C420mpeg2 XYSCSS=420MPEG2\n'
                ), line
            # An AssertionError here might mean that the seek value
            # exceeds the file length, in which case line == b''.
            shutil.copyfileobj(input, output)

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
        self.seek = seek
        self.dur = dur

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

    def __init__(self):
        self.sequence = []
        self.bucket = queue.Queue()

    def append(self, shot):
        self.sequence.append(shot)

    def process(self, output_file):
        clip_number = 0
        clips_v = []
        clips_a = []
        subprocesses = dict()
        for shot in self.sequence:
            fifo_v = "/tmp/vid_clip_{}_v".format(clip_number)
            fifo_a = "/tmp/vid_clip_{}_a".format(clip_number)
            os.mkfifo(fifo_v)
            os.mkfifo(fifo_a)
            clips_v.append(fifo_v)
            clips_a.append(fifo_a)
            # Remove headers on all but the first clip.
            shot.process(fifo_v, fifo_a, remove_header=clip_number)
            clip_number += 1
        fifo_v = "/tmp/vid_cat_v"
        fifo_a = "/tmp/vid_cat_a"
        os.mkfifo(fifo_v)
        os.mkfifo(fifo_a)
        thread_v = threading.Thread(target=self._cat, args=(clips_v, fifo_v))
        thread_a = threading.Thread(target=self._cat, args=(clips_a, fifo_a))
        thread_m = threading.Thread(
            target=self._merge_streams,
            args=(fifo_v, fifo_a, output_file),
            )
        thread_v.start()
        thread_a.start()
        thread_m.start()
        threads = [thread_v, thread_a, thread_m]
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
        try:
            exc = self.bucket.get(block=False)
        except queue.Empty:
            pass
        else:
            exc_type, exc_obj, exc_trace = exc
            raise exc_obj

    def _merge_streams(self, video, audio, output):
        logger.info(
            "Merging {} and {} into {}.".format(video, audio, output)
            )
        cmd = [
            "ffmpeg",
            "-y",
            "-f", "yuv4mpegpipe", "-vcodec", "rawvideo", "-i", video,
            "-f", "u16le", "-acodec", "pcm_s16le",
            "-ac", "2", "-ar", "44100", "-i", audio,
            "-f", "avi",
            "-codec", "copy",
            output,
            ]
        process = subprocess.Popen(
            cmd,
            stderr=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            )
        rv = process.wait()
        logger.info("Merge process returned {}.".format(rv))

    def _cat(self, clips, output):
        try:
            logger.info("Concatenating {} into {}.".format(clips, output))
            with open(output, "wb") as output_file:
                for clip in clips:
                    with open(clip, "rb") as input_file:
                        logger.info(
                            "_cat reading {}, writing {}.".format(
                                clip, output
                                )
                            )
                        shutil.copyfileobj(input_file, output_file)
        except:
            logger.error("Failed concatenation to {}.".format(output))
            self.bucket.put(sys.exc_info())
