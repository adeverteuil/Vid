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
OUTPUT_FORMAT = [
    "-f", "avi",
    "-vcodec", "libx264",
    "-crf", "23", "-preset", "medium",
    "-acodec", "mp3", "-strict", "experimental",
    "-ac", "2", "-ar", "44100", "-ab", "128k",
    "-qscale:v", "6",
    ]


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


class Shot():         #{{{
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
        return self
        # This allows the method call Cat().append(Shot(#).cut(seek, dur))

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
        logger.info("demuxing {}".format(self))

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
            args += ["-filter:v", "yadif"]
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
                args += RAW_VIDEO + ["pipe:{}".format(video1_w)]
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
        logger.debug("Demuxing video {} and audio {}".format(self.v_stream, self.a_stream))

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
class Cat():          #{{{
    """Concatenate supplied Shot objects, provide read pipes.

    Caller is responsible for closing the pipes.

    """
    def __init__(self):
        self.v_stream = None
        self.a_stream = None
        self.sequence = []

    def append(self, shot):
        self.sequence += [shot]

    def process(self):
        vpipe_r, self._vpipe_w = os.pipe()
        apipe_r, self._apipe_w = os.pipe()
        self.v_stream = open(vpipe_r, "rb")
        self.a_stream = open(apipe_r, "rb")
        self.thread = threading.Thread(
            target=self._process_thread,
            )
        self.thread.start()

    def _process_thread(self):
        v_queue = queue.Queue(maxsize=2)
        v_thread = threading.Thread(
            target=self._concatenate_streams,
            args=(v_queue, open(self._vpipe_w, "wb"))
            )
        v_thread.start()
        a_queue = queue.Queue(maxsize=2)
        a_thread = threading.Thread(
            target=self._concatenate_streams,
            args=(a_queue, open(self._apipe_w, "wb")),
            )
        a_thread.start()
        i = 0
        for shot in self.sequence:
            shot.demux(remove_header=i)
            i += 1
            v_queue.put(shot.v_stream)
            a_queue.put(shot.a_stream)
        v_queue.put(False)
        a_queue.put(False)

    @staticmethod
    def _concatenate_streams(queue, output):
        #import pdb; pdb.set_trace()
        while True:
            i = queue.get()
            if i:
                logger.debug("Concatenating {} to {}.".format(i, output))
                shutil.copyfileobj(i, output)
                #while True:
                #    buf = i.read(16*1024)
                #    if buf == b'':
                #        break
                #    output.write(buf)
                i.close()
            else:
                break
        output.close()

#}}}
class Player():       #{{{
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

#}}}
class Multiplexer():  #{{{
    def __init__(self, v_stream, a_stream):
        self.v_stream = self._get_fileno(v_stream)
        self.a_stream = self._get_fileno(a_stream)

    def mux(self):
        logger.debug("Muxing video {} and audio {}.".format(
            self.v_stream, self.a_stream))
        args = [
            "ffmpeg", "-y",
            ] + RAW_VIDEO[:-1] + ["-i", "pipe:{}".format(self.v_stream),
            ] + RAW_AUDIO[:-1] + ["-i", "pipe:{}".format(self.a_stream),
            ] + OUTPUT_FORMAT + ["pipe:1",
            ]
        self.process = subprocess.Popen(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            pass_fds=(self.v_stream, self.a_stream),
            )
        os.close(self.v_stream)
        os.close(self.a_stream)
        return self.process.stdout

    @staticmethod
    def _get_fileno(file):
        # Find out what is file.
        if isinstance(file, int):
            return file
        else:
            try:
                return file.fileno()
            except AttributeError:
                return None
#}}}
