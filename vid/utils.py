# vim:cc=80:fdm=marker:fdl=0:fdc=1
#
# utils.py
# Copyright (C) 2013  Alexandre de Verteuil


import os
import io
import sys
import glob
import stat
import errno
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


def _redirect_stderr_to_log_file():              #{{{1
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


class RemoveHeader(threading.Thread):            #{{{1
    """Threading class to remove one line from input and pipe to output.

    Passed parameters must be one readable file object and one writable
    file object. One line is read and dumped from the input. The rest is
    copied to output. Both files are closed upon completion of the task.

    The parties parameter is passed to the threading.Barrier
    constructor to impose a barrier just before writing and just before
    reading. Added for debugging and developement.
    """

    def __init__(self, input, output, parties=1):
        self.logger = logging.getLogger(__name__+".RemoveHeader")

        assert isinstance(input, io.IOBase)
        assert input.readable()
        assert isinstance(output, io.IOBase)
        assert output.writable()

        self.input = input
        self.output = output
        self.bytes_read = 0     # Number of bytes read.
        self.bytes_written = 0  # Number of bytes written.
        self.exception = None

        # This was added for debugging.
        self.read_barrier = threading.Barrier(parties)
        self.write_barrier = threading.Barrier(parties)
        self.finished = threading.Event()

        super(RemoveHeader, self).__init__()

    def run(self):
        self.logger.debug(
            "Thread starting: "
            "removing header from {}, piping the rest through {}.".format(
                self.input, self.output
                )
            )
        try:
            line = self.input.readline()
            if line == b"":
                self.logger.warning(
                    "No data found on input {}!".format(self.input)
                    )
                self.exception = ValueError("No data found on input.")
                self.finished.set()
                return
            if line[0:9] != b"YUV4MPEG2":
                # This might mean that the seek value exceeds the file
                # length, in which case line == b''.
                self.logger.warning(
                    "File {} does not seem to start with a header.".format(
                        self.input
                        )
                    )
            self.logger.debug("Header removed:\n{}".format(repr(line)))

            while True:
                # Copy bytes from input to output. Increment tallies.
                # Check self.finished.is_set() in main thread befor waiting.
                self.read_barrier.wait()
                # read1() is more predictable for unittests.
                buf = self.input.read1(64 * 1024)
                if buf == b"":
                    self.finished.set()
                    self.write_barrier.wait()
                    break
                self.bytes_read += len(buf)
                self.write_barrier.wait()
                # If timed out, check self.finished.is_set() in the main
                # thread.
                self.bytes_written += self.output.write(buf)
        except OSError as err:
            if err.errno in (errno.EPIPE, errno.EBADFD):
                self.logger.warning("Pipe unexpectedly broken.")
            else:
                self.exception = err
                self.logger.error(
                    "Pipe closed while piping {} to {}: {}".format(
                        self.input, self.output
                        )
                    )
        except threading.BrokenBarrierError as err:
            self.exception = err
            if self.read_barrier.broken:
                barrier = "read"
            elif self.write_barrier.broken:
                barrier = "write"
            else:
                barrier = "some unknown"
            self.logger.error(
                "{} barrier broken while piping {} to {}: {}".format(
                    barrier, self.input, self.output, err
                    )
                )
        except Exception as err:
            self.exception = err
            self.logger.error(
                "Error occurred while piping {} to {}: {}".format(
                    self.input, self.output, err
                    )
                )
        finally:
            if not self.input.closed:
                self.input.close()
                self.logger.debug("Closed {}".format(self.input))
            if not self.output.closed:
                self.output.close()
                self.logger.debug("Closed {}".format(self.output))

    def get_bytes_read(self):
        return self.bytes_read

    def get_bytes_written(self):
        return self.bytes_written


class ConcatenateStreams(threading.Thread):      #{{{1
    """Threading class to concatenate many inputs in one output.

    Passed parameters must be one Queue of file objects to read and one
    file object to write to. All files are closed when done with.
    """

    def __init__(self, q, output):
        self.logger = logging.getLogger(__name__+".ConcatenateStreams")

        assert isinstance(q, queue.Queue)
        assert isinstance(output, io.IOBase)
        assert output.writable()

        self.queue = q
        self.output = output
        self.exception = None
        self.finished = threading.Event()

        super(ConcatenateStreams, self).__init__()

    def run(self):
        self.logger.debug(
            "Thread starting: Concatenating inputs to {}.".format(self.output)
            )
        try:
            while True:
                fileobj = self.queue.get()
                if fileobj is None:
                    self.queue.task_done()
                    raise queue.Empty
                assert isinstance(fileobj, io.IOBase)
                assert fileobj.readable()
                self.logger.debug(
                    "Concatenating {} to {}.".format(fileobj, self.output)
                    )
                shutil.copyfileobj(fileobj, self.output)
                fileobj.close()
                self.logger.debug("{} closed.".format(fileobj))
                self.queue.task_done()
        except queue.Empty:
            self.finished.set()
        except Exception as err:
            self.exception = err
        finally:
            if not self.output.closed:
                self.output.close()
            self.logger.debug(
                "Concatenation achieved. {} closed.".format(self.output)
                )


class Shot():                                    #{{{1
    """Abstraction for a movie file copied from the camcorder.

    The constructor takes an integer as a parameter and finds the
    appropriate file.

    The demux() method returns readable file objects for the requested streams.

    This is the simplest building block for a movie.
    """
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

    def _probe(self):
        #TODO use ffprobe to gather information about the file.
        pass

    def demux(self, video=True, audio=True, remove_header=False):
        """Return readable video and audio streams.

        This method will demultiplex the shot and pipe the raw video and audio
        streams to those files. The caller is responsible for closing
        the files.

        The return value is (audio,), (video,) or (video, audio)
        This method also sets it's instance's a_stream and v_stream properties.
        """
        assert video or audio
        args = ["ffmpeg", "-y"]
        pass_fds = []
        returnvalue = []
        self.logger.debug("Demuxing {}.".format(self))

        # Define input arguments.
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

        # Define video arguments.
        if video:
            args += ["-filter:v", "yadif"]  # Always deinterlace.
            if remove_header:
                video1_r, video1_w = os.pipe()
                video2_r, video2_w = os.pipe()
                self.logger.debug(
                    "Video pipes created:\n"
                    "subprocess {} -> {} RemoveHeader;\n"
                    "RemoveHeader {} -> {} self.v_stream.".format(
                        video1_w, video1_r, video2_w, video2_r
                        )
                    )
                t = RemoveHeader(open(video1_r, "rb"), open(video2_w, "wb"))
                pass_fds.append(video1_w)
                self.v_stream = open(video2_r, "rb")
                if seek:
                    args += ["-ss", str(seek)]
                if self.dur:
                    args += ["-t", str(self.dur)]
                args += RAW_VIDEO + ["pipe:{}".format(video1_w)]
                t.start()
            else:
                video_r, video_w = os.pipe()
                self.logger.debug(
                    "Video pipe created:\n"
                    "subprocess {} -> {} self.v_stream.".format(
                        video_w, video_r
                        )
                    )
                pass_fds.append(video_w)
                self.v_stream = open(video_r, "rb")
                if seek:
                    args += ["-ss", str(seek)]
                if self.dur:
                    args += ["-t", str(self.dur)]
                args += RAW_VIDEO + ["pipe:{}".format(video_w)]
            returnvalue.append(self.v_stream)

        # Define audio arguments
        if audio:
            audio_r, audio_w = os.pipe()
            pass_fds.append(audio_w)
            self.a_stream = open(audio_r, "rb")
            returnvalue.append(self.a_stream)
            self.logger.debug(
                "Audio pipe created:\n"
                "subprocess {} -> {} self.a_stream.".format(
                    audio_fdw, audio_fdr
                    )
                )
            args += RAW_AUDIO
            if seek:
                args += ["-ss", str(seek)]
            if self.dur:
                args += ["-t", str(self.dur)]
            args += ["pipe:{}".format(audio_w)]

        # Create subprocess.
        self.process = subprocess.Popen(
            args,
            pass_fds=pass_fds,
            stdout=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
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
        self.logger.debug("Streams returned: {}.".format(returnvalue))
        return tuple(returnvalue)

    def cut(self, seek=0, dur=None):
        """Sets the starting position and duration of the required frames."""
        assert isinstance(seek, (int, float))
        if dur is not None:
            assert isinstance(seek, (int, float))
        self.seek = seek
        self.dur = dur
        return self
        # This allows instantiation and cutting at once :
        # Shot(<number>).cut(seek, dur)
