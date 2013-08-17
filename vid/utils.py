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


class RemoveHeader(threading.Thread):
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
            "Thread starting : "
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
