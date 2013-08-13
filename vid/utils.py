# vim:cc=80:fdm=marker:fdl=0:fdc=1
#
# utils.py
# Copyright (C) 2013  Alexandre de Verteuil


import os
import io
import sys
import glob
import stat
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
RAW_AUDIO = [
    "-f", "u16le", "-acodec", "pcm_s16le",
    "-ac", "2", "-ar", "44100", "-vn",
    ]
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
    file = open(logdir+"/p{}.log".format(pid), "w")
    os.dup2(file.fileno(), sys.stderr.fileno())
    file.write("Log for subprocess id {}.\n\n".format(pid))
    ls = "Open file descriptors:\n"
    for fd in os.listdir("/proc/self/fd"):
        pathname = "/proc/self/fd/" + str(fd)
        try:
            st = os.stat(pathname, follow_symlinks=False)
            mode = stat.filemode(st.st_mode)
            link = os.readlink(pathname)
            ls += "    {} {:2} -> {}\n".format(
                mode,
                fd,
                link,
                )
        except FileNotFoundError:
            continue
    file.write(ls)
    file.write("\n-- start stderr stream -- \n\n")


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

        Because of this bug
        https://ffmpeg.org/trac/ffmpeg/ticket/2700
        and by following the model in this script
        http://ffmpeg.org/trac/ffmpeg/wiki/How%20to%20concatenate%20%28join%2C%20merge%29%20media%20files#Script
        I call one subprocess per stream.

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
            v_args = args + ["-filter:v", "yadif"]
            if remove_header:
                video1_r, video1_w = os.pipe()
                video2_r, video2_w = os.pipe()
                self.logger.debug(
                    "Video pipes created:\n"
                    "subprocess {} -> {} _remove_headers;\n"
                    "_remove_headers {} -> {} self.v_stream.".format(
                        video1_w, video1_r, video2_w, video2_r
                        )
                    )
                t = threading.Thread(
                    target=self._remove_header,
                    args=(video1_r, video2_w),
                    )
                write_fds.append(video1_w)
                self.v_stream = open(video2_r, "rb")
                if seek:
                    v_args += ["-ss", str(seek)]
                if self.dur:
                    v_args += ["-t", str(self.dur)]
                v_args += RAW_VIDEO + ["pipe:{}".format(video1_w)]
                t.start()
            else:
                video_fdr, video_fdw = os.pipe()
                self.logger.debug(
                    "Video pipe created:\n"
                    "subprocess {} -> {} self.v_stream.".format(
                        video_fdw, video_fdr
                        )
                    )
                write_fds.append(video_fdw)
                self.v_stream = open(video_fdr, "rb")
                if seek:
                    v_args += ["-ss", str(seek)]
                if self.dur:
                    v_args += ["-t", str(self.dur)]
                v_args += RAW_VIDEO + ["pipe:{}".format(video_fdw)]

            # Create subprocess
            self.process = subprocess.Popen(
                v_args,
                pass_fds=write_fds,
                stdout=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                preexec_fn=_redirect_stderr_to_log_file,
                )
            self.logger.debug(
                SUBPROCESS_LOG.format(
                    self.process.pid, v_args
                    )
                )
        if audio:
            audio_fdr, audio_fdw = os.pipe()
            write_fds.append(audio_fdw)
            self.a_stream = open(audio_fdr, "rb")
            self.logger.debug(
                "Audio pipe created:\n"
                "subprocess {} -> {} self.a_stream.".format(
                    audio_fdw, audio_fdr
                    )
                )
            a_args = args + RAW_AUDIO
            if seek:
                a_args += ["-ss", str(seek)]
            if self.dur:
                a_args += ["-t", str(self.dur)]
            a_args += ["pipe:{}".format(audio_fdw)]

            # Create subprocess
            self.process = subprocess.Popen(
                a_args,
                pass_fds=write_fds,
                stdout=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                preexec_fn=_redirect_stderr_to_log_file,
                )
            self.logger.debug(
                SUBPROCESS_LOG.format(
                    self.process.pid, a_args
                    )
                )
        for fd in write_fds:
            # Close write file descriptors.
            os.close(fd)
            self.logger.debug("closed fd {}.".format(fd))

    @staticmethod
    def _remove_header(input, output):
        logger = logging.getLogger(__name__+".Shot._remove_header")
        logger.debug(
            "Removing header from {}, piping the rest through {}.".format(
                input, output
                )
            )
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
        self.logger = logging.getLogger(__name__+".Cat")
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
        self.logger.debug(
            "Video pipe created:\nwrite to {}, read from {}\n"
            "Audio pipe created:\nwrite to {}, read from {}".format(
                self._vpipe_w, vpipe_r, self._apipe_w, apipe_r
                )
            )
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
            self.logger.debug(
                "Demultiplexing {}\n"
                "Reading video from {} and audio from {}".format(
                    shot, shot.v_stream, shot.a_stream
                    )
                )
        v_queue.put(None)
        a_queue.put(None)

    @staticmethod
    def _concatenate_streams(queue, output):
        logger = logging.getLogger(__name__+".Cat")
        #import pdb; pdb.set_trace()
        while True:
            i = queue.get()
            if i is not None:
                logger.debug("Concatenating {} to {}.".format(i, output))
                #shutil.copyfileobj(i, output)
                while True:
                    buf = i.read(16*1024)
                    logger.debug("{} {:9} -> {:9} {}".format(
                            i.fileno(), len(buf), "", output.fileno()
                            )
                        )
                    if buf == b'':
                        break
                    l = output.write(buf)
                    logger.debug("{} {:9} -> {:9} {}".format(
                            i.fileno(), "", l, output.fileno()
                            )
                        )
                i.close()
                logger.debug("Finished reading {} and closed it.".format(i))
            else:
                break
        output.close()
        logger.debug("Closed {}.".format(output))

#}}}
class Player():       #{{{
    """ffplay

    Argument can be a path name sting, an int or a file object
    which has a fileno() method.

    """
    def __init__(self, file):
        self.logger = logging.getLogger(__name__+".Player")
        args = ["ffplay", "-autoexit"]
        pass_fds = ()
        # Find out what is file.
        if isinstance(file, str):
            self.logger.debug("File is string \"{}\".".format(file))
            args.append(file)
            file = subprocess.DEVNULL
        elif isinstance(file, int):
            self.logger.debug("File is int {}.".format(file))
            args.append("pipe:")
            pass_fds = (file,)
        elif isinstance(file.fileno(), int):
            self.logger.debug("File is file object {}.".format(file))
            args.append("pipe:")
            pass_fds = (file.fileno(),)
        else:
            raise ValueError(
                "Argument must be string, int or file object, got {}.".format(
                    type(file)
                    )
                )
        self.logger.debug("Passing file descriptors : {}".format(pass_fds))
        self.process = subprocess.Popen(
            args,
            stdin=file,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            #pass_fds=pass_fds,
            preexec_fn=_redirect_stderr_to_log_file,
            )
        self.logger.debug(
            SUBPROCESS_LOG.format(
                self.process.pid, args
                )
            )
        for fd in pass_fds:
            os.close(fd)
            self.logger.debug("Closed fd {}.".format(fd))

#}}}
class Multiplexer():  #{{{
    def __init__(self, v_stream, a_stream):
        self.logger = logging.getLogger(__name__+".Multiplexer")
        self.v_stream = self._get_fileno(v_stream)
        self.a_stream = self._get_fileno(a_stream)

    def mux(self):
        self.logger.debug("Muxing video {} and audio {}.".format(
            self.v_stream, self.a_stream))
        rv = RAW_VIDEO[:]
        rv.remove("-an")
        ra = RAW_AUDIO[:]
        ra.remove("-vn")
        args = [
            "ffmpeg", "-y",
            ] + rv + ["-i", "pipe:{}".format(self.v_stream),
            ] + ra + ["-i", "pipe:{}".format(self.a_stream),
            ] + OUTPUT_FORMAT + ["pipe:1",
            ]
        self.process = subprocess.Popen(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            pass_fds=(self.v_stream, self.a_stream),
            preexec_fn=_redirect_stderr_to_log_file,
            )
        self.logger.debug(
            SUBPROCESS_LOG.format(
                self.process.pid, args
                )
            )
        os.close(self.v_stream)
        os.close(self.a_stream)
        self.logger.debug(
            "Closed fd {} and {} after spawning subprocess.".format(
                self.v_stream, self.a_stream
                )
            )
        self.output = self.process.stdout
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
