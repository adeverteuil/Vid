# vim:cc=80:fdm=marker:fdl=0:fdc=1
#
# utils.py
# Copyright © 2013  Alexandre de Verteuil        {{{1
#
# This file is part of Vid.
#
# Vid is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# Vid is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#}}}


# Imports                                        {{{1
import os
import io
import re
import sys
import glob
import stat
import json
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


# Global variables                               {{{1
FASTSEEK_THRESHOLD = 30  # Seconds
RAW_VIDEO = ["-f", "yuv4mpegpipe", "-vcodec", "rawvideo"]
RAW_AUDIO = [
    "-f", "s16le", "-acodec", "pcm_s16le",
    "-ac", "2", "-ar", "44100",
    ]
SUBPROCESS_LOG = "Subprocess pid {}:\n{}"
# Set the default font for drawtext filter.
FONTFILE = "/usr/share/fonts/TTF/ttf-inconsolata.otf"
OUTPUT_FORMATS = { # Generally, make keys refer to file extensions.
    'avi': [
        "-f", "avi",
        "-vcodec", "libx264",
        "-crf", "23", "-preset", "medium",
        "-acodec", "mp3", "-strict", "experimental",
        "-ac", "2", "-ar", "44100", "-ab", "128k",
        "-qscale:v", "6",
        ],
    # ogg and webm format from http://diveintohtml5.info/video.html.
    'ogv': [
        "-f", "ogg",
        "-vcodec", "libtheora",
        "-qscale:v", "5",
        # Max quality is 10.
        "-acodec", "libvorbis",
        "-qscale:a", "3",
        ],
    'webm': [
        "-f", "webm",
        "-vcodec", "libvpx", "-b", "614400",
        "-acodec", "libvorbis",
        ],
    # Low latency, high bandwidth for local pipe.
    'pipe': [
        "-f", "matroska",
        "-vcodec", "rawvideo", # I don't use "copy" because filters may apply.
        "-acodec", "pcm_s16le", "-ac", "2", "-ar", "44100",
        ],
    }


logger = logging.getLogger(__name__)
logdir = os.getcwd() + "/log"


@atexit.register
def cleanup():
    logging.shutdown()
#}}}


def _redirect_stderr_to_log_file():              #{{{1
    # This function is passed as the preexec_fn to subprocess.Popen
    pid = os.getpid()
    file = open(logdir+"/p{}.log".format(pid), "w")
    os.dup2(file.fileno(), sys.stderr.fileno())
    file.close()
    sys.stderr.write("Log for subprocess id {}.\n\n".format(pid))
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
    sys.stderr.write(ls)
    sys.stderr.write("\n-- start stderr stream -- \n\n")
#}}}


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


class PipeHelper(threading.Thread):              #{{{1
    """Thread subclass that simply pipes data without processing.

    For some reason yet to be known, this helps get bytes through
    complex piping schemes. This ascii art graphic illustrates where
    PipeHelper was necessary for successfully piping between two ffmpeg
    instances. I think it has something to do with the block size of the
    reading process which is too big for a pipe.

           ,-> video_stream -----------------------,
    demux <                                         ',
           '-> audio_stream -,                        ',
                              >-> mixer -> PipeHelper ---> mux
               music_file ---'
    """

    def __init__(self, infile):
        self.logger = logging.getLogger(__name__+".PipeHelper")

        assert isinstance(infile, io.IOBase)
        assert infile.readable()

        self.input = infile
        r, w = os.pipe()
        self.output = open(r, "rb")
        self._output = open(w, "wb")
        self.bytes_read = 0
        self.bytes_written = 0
        self.exception = None

        super(PipeHelper, self).__init__()

    def run(self):
        self.logger.debug(
            "Thread starging: "
            "Pulling data from {}, pushing through {}.".format(
                self.input, self.output
                )
            )
        try:
            while True:
                buf = self.input.read1(64 * 1024)
                if buf == b"":
                    break
                self.bytes_read += len(buf)
                self.bytes_written += self._output.write(buf)
        except OSError as err:
            self.logger.warning("Pipe unexpectedly broken.")
        finally:
            if not self._output.closed:
                self._output.close()


class GenerateSilence(threading.Thread):         #{{{1
    """Threading subclass that pipes raw audio replacing all bytes with zeroes.
    """

    def __init__(self, input, output):
        self.logger = logging.getLogger(__name__+".GenerateSilence")

        assert isinstance(input, io.IOBase)
        assert input.readable()
        assert isinstance(output, io.IOBase)
        assert output.writable()

        self.input = input
        self.output = output
        self.bytes_read = 0     # Number of bytes read.
        self.bytes_written = 0  # Number of bytes written.
        self.exception = None
        self.finished = threading.Event()

        super(GenerateSilence, self).__init__()

    def run(self):
        self.logger.debug(
            "Thread starting: "
            "Replacing all bytes from {} with zeroes, piping to {}.".format(
                self.input, self.output
                )
            )
        try:
            while True:
                buf = self.input.read1(64 * 1024)
                self.bytes_read += len(buf)
                if buf == b'':
                    self.finished.set()
                    break
                self.bytes_written += self.output.write(b'\x00'*len(buf))
        finally:
            if not self.input.closed:
                self.input.close()
                self.logger.debug("Closed {}".format(self.input))
            if not self.output.closed:
                self.output.close()
                self.logger.debug("Closed {}".format(self.output))


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
                    self.logger.debug("Received end of queue signal.")
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


class SubprocessSupervisor(threading.Thread):    #{{{1
    """Thread subprocess that calls fn, then calls action.

    fn is an iterable of callable objects.
    name keyword argument will be passed to the parent class constructor and
    used in the debugging stream.

    This is useful as a subprocess supervisor and lock releaser. Here is an
    example usage:
    SubprocessSupervisor(subprocess.wait, lock.release)
    """

    def __init__(self, fn, action, *args, **kwargs):
        self.logger = logging.getLogger(__name__+".SubprocessSupervisor")
        self.fn = fn
        self.action = action

        super(SubprocessSupervisor, self).__init__(*args, **kwargs)

    def run(self):
        self.logger.debug("Thread started, waiting on {}.".format(self.fn))
        for callable in self.fn:
            rv = callable()
            self.logger.debug(
                "Process {} terminated. Returned {}.".format(callable, rv)
                )
        self.logger.debug(
            "Process \"{}\" finished. Executing action.".format(self.name)
            )
        self.action()


class ConcatenateShots(threading.Thread):        #{{{1
    """Threading subclass to concatenate many cuts in one movie.

    Works with two streams at once. Instantiates ConcatenateStreams and
    manages resources by limiting spawned subprocesses.

    Constructor takes three arguments: one queue.Queue objects, one writable
    file object to write video and another for audio.

    Queued objects must be Shot instances, and None to signal end of queue.
    """

    def __init__(self, q, v_out, a_out):
        self.logger = logging.getLogger(__name__+".ConcatenateShots")

        assert isinstance(q, queue.Queue)
        assert isinstance(v_out, io.IOBase)
        assert isinstance(a_out, io.IOBase)
        assert v_out.writable()
        assert a_out.writable()

        self.queue = q
        self.exception = None
        self.finished = threading.Event()
        # A semaphore with a limit of 2 ensures that one process is in a
        # waiting, blocked state while the previous process is working.
        self.semaphore = threading.Semaphore(value=2)
        self.v_queue = queue.Queue()
        self.a_queue = queue.Queue()
        self.v_out = v_out
        self.a_out = a_out

        super(ConcatenateShots, self).__init__()

    def run(self):
        self.logger.debug("Thread starting: Concatenating shots.")
        try:
            v_cat = ConcatenateStreams(self.v_queue, self.v_out)
            a_cat = ConcatenateStreams(self.a_queue, self.a_out)
            v_cat.start()
            a_cat.start()
            i = 0
            buffer = []
            # Allow that many seconds of buffer by releasing more semaphores.
            min_buffer = 10
            while True:
                shot = self.queue.get()
                if shot is None:
                    self.logger.debug("End of queue signal recieved.")
                    self.v_queue.put(None)
                    self.a_queue.put(None)
                    self.queue.task_done()
                    raise queue.Empty
                assert isinstance(shot, Shot)
                buffer.append(shot.dur)
                if (sum(buffer) < min_buffer and
                    not self.semaphore.acquire(blocking=False)
                    ):
                    self.logger.debug(
                        "Buffer not long enough. ({}) "
                        "Allowing one more subprocess to run.".format(buffer)
                        )
                    self.semaphore.release()
                # This is not thought through.
                #self.semaphore.acquire()
                self.logger.debug(
                    "Concatenating {}.".format(shot)
                    )
                shot.demux(remove_header=i)
                i += 1
                self.v_queue.put(shot.v_stream)
                self.a_queue.put(shot.a_stream)
                SubprocessSupervisor(
                    (shot.v_process.wait, shot.a_process.wait),
                    self.semaphore.release,
                    name="Demuxing {}.".format(shot),
                    ).start()
        except queue.Empty:
            self.finished.set()
        except Exception as err:
            self.logger.error("Error occured: {}.".format(err))
            self.exception = err
            raise


class FFmpegWrapper():                           #{{{1
    """Provides utilities for subclasses that spawn ffmpeg subprocesses."""

    def __init__(self):
        self.filters = []

    def _format_filters(self):
        """Build filter string for ffmpeg argument.

        Make this happen:
        ["-filter:v", "name,name=k=v,name=k=v:k=v:k=v"]
        """
        if not self.filters:
            return []
        self.logger.debug(
            "Processing filters {}.".format(self.filters)
            )
        returnvalue = []
        filterchain = []
        for filter in self.filters:
            name = filter[0]
            args = filter[1]
            if args:
                arglist = []
                for k, v in args.items():
                    # Convert numbers to string.
                    v = str(v)
                    # Third level of escaping.
                    v = re.sub("([][,;])", r"\\\1", v)
                    # Second level of escaping for filtergraph description string.
                    v = v.replace("\\", "\\\\").replace("'", "'\\\\\\''")
                    # First level of escaping for the filter arguments.
                    v = v.replace(":", "\\:")
                    # Quoting.
                    v = "'{}'".format(v)
                    arglist.append("=".join((k, v)))
                string = "=".join([name, ":".join(arglist)])
            else:
                string = name
            filterchain.append(string)
        returnvalue.append(",".join(filterchain))
        return ["-filter:v"] + returnvalue

    def add_filter(self, filtername, **kwargs):
        self.logger.debug(
            "Adding filter {} with options {}.".format(filtername, kwargs)
            )
        if filtername == "drawtext":
            defaults = {
                'fontfile': FONTFILE,
                'fontcolor': "white",
                'fontsize': "25",
                'boxcolor': "0x000000aa",
                }
            defaults.update(kwargs)
            kwargs = defaults
        self.filters.append((filtername, kwargs))
        return self


class Shot(FFmpegWrapper):                       #{{{1
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
        self.silent = False
        self.filters = [("yadif", {})]  # Always deinterlace.
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
        self._probe = Probe(self.name)

    def __repr__(self):
        return "<Shot({}), seek={}, dur={}>".format(
            self.number,
            self.seek,
            self.dur,
            )

    def get_duration(self):
        return self._probe.get_duration()

    def demux(self, video=True, audio=True, remove_header=False):
        """Return readable video and audio streams.

        This method will demultiplex the shot and pipe the raw video and audio
        streams to those files. The caller is responsible for closing
        the files.

        The return value is (audio,), (video,) or (video, audio)
        This method also sets it's instance's a_stream and v_stream properties.

        Because of this bug
        https://ffmpeg.org/trac/ffmpeg/ticket/2700
        and by following the model in this script
        http://ffmpeg.org/trac/ffmpeg/wiki/How%20to%20concatenate%20%28join%2C%20merge%29%20media%20files#Script
        I call one subprocess per stream.
        """
        assert video or audio
        args = ["ffmpeg", "-loglevel", "debug", "-y"]
        write_fds = []
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
            v_args = args[:]  # Shallow copy.
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
                write_fds.append(video1_w)
                self.v_stream = open(video2_r, "rb")
                if seek:
                    v_args += ["-ss", str(seek)]
                if self.dur:
                    v_args += ["-t", str(self.dur)]
                v_args += self._format_filters()
                v_args += RAW_VIDEO + ["-an", "pipe:{}".format(video1_w)]
                t.start()
            else:
                video_r, video_w = os.pipe()
                self.logger.debug(
                    "Video pipe created:\n"
                    "subprocess {} -> {} self.v_stream.".format(
                        video_w, video_r
                        )
                    )
                write_fds.append(video_w)
                self.v_stream = open(video_r, "rb")
                if seek:
                    v_args += ["-ss", str(seek)]
                if self.dur:
                    v_args += ["-t", str(self.dur)]
                v_args += self._format_filters()
                v_args += RAW_VIDEO + ["-an", "pipe:{}".format(video_w)]
            returnvalue.append(self.v_stream)

            # Create subprocess
            self.v_process = subprocess.Popen(
                v_args,
                pass_fds=write_fds,
                stdout=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                preexec_fn=_redirect_stderr_to_log_file,
                )
            self.logger.debug(
                SUBPROCESS_LOG.format(
                    self.v_process.pid, v_args
                    )
                )

        # Define audio arguments
        if audio:
            a_args = args[:]  # Shallow copy
            if self.silent:
                audio1_r, audio1_w = os.pipe()
                audio2_r, audio2_w = os.pipe()
                audio_w = audio1_w
                self.logger.debug(
                    "Audio pipes created:\n"
                    "subprocess {} -> {} GenerateSilence;\n"
                    "GenerateSilence {} -> {} self.a_stream".format(
                        audio1_w, audio1_r, audio2_w, audio2_r
                        )
                    )
                t = GenerateSilence(open(audio1_r, "rb"), open(audio2_w, "wb"))
                write_fds.append(audio1_w)
                self.a_stream = open(audio2_r, "rb")
                if seek:
                    a_args += ["-ss", str(seek)]
                if self.dur:
                    a_args += ["-t", str(self.dur)]
                a_args += RAW_AUDIO + ["-vn", "pipe:{}".format(audio1_w)]
                t.start()
            else:
                audio_r, audio_w = os.pipe()
                self.a_stream = open(audio_r, "rb")
                self.logger.debug(
                    "Audio pipe created:\n"
                    "subprocess {} -> {} self.a_stream.".format(
                        audio_w, audio_r
                        )
                    )
                write_fds.append(audio_w)
                if seek:
                    a_args += ["-ss", str(seek)]
                if self.dur:
                    a_args += ["-t", str(self.dur)]
                a_args += RAW_AUDIO + ["-vn", "pipe:{}".format(audio_w)]
            returnvalue.append(self.a_stream)

            # Create subprocess.
            self.a_process = subprocess.Popen(
                a_args,
                pass_fds=(audio_w,),
                stdout=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                preexec_fn=_redirect_stderr_to_log_file,
                )
            self.logger.debug(
                SUBPROCESS_LOG.format(
                    self.a_process.pid, a_args
                    )
                )
        for fd in write_fds:
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

    def generate_silence(self):
        self.logger.debug("Make silent movie.")
        self.silent = True
        return self

    def add_filter(self, filtername, **kwargs):
        self.logger.debug(
            "Adding filter {} with options {}.".format(filtername, kwargs)
            )
        if filtername == "showdata":
            # Add a gliding cursor which indicates the current position
            # along the bottom of the frame.
            self.add_filter(
                "drawtext",
                x="t/{length}*w".format(length=self.get_duration()),
                y="h-text_h",
                text=">",
                fontsize="10",
                shadowcolor="black",
                shadowx="2",
                )
            self.add_filter(
                "drawtext",
                text="%{{pts}}    %{{n}}\n{}".format(self.name),
                y="h-text_h-20",
                x="30",
                box="1",
                )
        else:
            super().add_filter(filtername, **kwargs)
        return self


class Player():                                  #{{{1
    """A wrapper for ffplay.

    Constructor argument may be a path name string, a file descriptor integer
    or a file object which has a fileno() method.
    """
    def __init__(self, file):
        self.logger = logging.getLogger(__name__+".Player")
        args = ["ffplay", "-loglevel", "debug", "-autoexit"]
        # Find out what is file.
        if isinstance(file, str):
            self.logger.debug("File is string \"{}\".".format(file))
            args.append(file)
            file = subprocess.DEVNULL
        elif isinstance(file, int):
            self.logger.debug("File is int {}.".format(file))
            args.append("pipe:")
        elif isinstance(file.fileno(), int):
            self.logger.debug("File is file object {}.".format(file))
            args.append("pipe:")
        else:
            raise ValueError(
                "Argument must be string, int or file object, got {}.".format(
                    type(file)
                    )
                )
        self.process = subprocess.Popen(
            args,
            stdin=file,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=_redirect_stderr_to_log_file,
            )
        self.logger.debug(
            SUBPROCESS_LOG.format(
                self.process.pid, args
                )
            )
        if isinstance(file, int):
            os.close(file)
            self.logger.debug("Closed fd {}.".format(file))
        elif isinstance(file, io.IOBase):
            file.close()
            self.logger.debug("Closed file object {}.".format(file))

class Multiplexer(FFmpegWrapper):                #{{{1
    """Multiplex video and audio stream in a container format."""

    def __init__(self, v_stream, a_stream):
        self.logger = logging.getLogger(__name__+".Multiplexer")
        self.v_fd = self._get_fileno(v_stream)
        self.a_fd = self._get_fileno(a_stream)
        self._args = [
            "ffmpeg", "-loglevel", "debug", "-y",
            ] + RAW_VIDEO + ["-i", "pipe:{}".format(self.v_fd),
            ] + RAW_AUDIO + ["-i", "pipe:{}".format(self.a_fd),
            ]
        super().__init__()

    def mux(self, format=OUTPUT_FORMATS['pipe']):
        self.logger.debug("Muxing video {} and audio {}.".format(
            self.v_fd, self.a_fd))
        if isinstance(format, str):
            format = OUTPUT_FORMATS[format]
        else:
            assert isinstance(format, list)
        args = self._args + self._format_filters() + format + ["pipe:1"]
        self.process = subprocess.Popen(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            pass_fds=(self.v_fd, self.a_fd),
            preexec_fn=_redirect_stderr_to_log_file,
            )
        self.logger.debug(
            SUBPROCESS_LOG.format(
                self.process.pid, args
                )
            )
        os.close(self.v_fd)
        os.close(self.a_fd)
        self.output = self.process.stdout
        self.logger.debug(
            "Closed fd {} and {} after spawning subprocess.\n"
            "Output is {}.".format(
                self.v_fd, self.a_fd, self.output
                )
            )
        return self.process.stdout

    def write_to_files(self, *files):
        """Multiplex streams and write to files.

        Each file extension will be used as a key to the OUTPUT_FORMATS
        dictionary.
        """
        self.logger.debug("Muxing video {} and audio {} to files {}.".format(
            self.v_fd, self.a_fd, files
            ))
        assert files
        outputs = []
        for file in files:
            assert isinstance(file, str)
            ext = file.rsplit('.', 1)[-1]
            outputs += self._format_filters()
            outputs += OUTPUT_FORMATS[ext]
            outputs.append(file)
        args = self._args + outputs
        self.process = subprocess.Popen(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            pass_fds=(self.v_fd, self.a_fd),
            preexec_fn=_redirect_stderr_to_log_file,
            )
        self.logger.debug(
            SUBPROCESS_LOG.format(
                self.process.pid, args
                )
            )
        os.close(self.v_fd)
        os.close(self.a_fd)
        self.logger.debug(
            "Closed fd {} and {} after spawning subprocess.".format(
                self.v_fd, self.a_fd
                )
            )
        return

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

    def add_filter(self, filtername, **kwargs):
        self.logger.debug(
            "Adding filter {} with options {}.".format(filtername, kwargs)
            )
        if filtername == "showdata":
            # Print timecode and, if length is provided, length.
            try:
                t = "/{:.6f}".format(kwargs['length'])
                # Add a gliding cursor which indicates the current position
                # along the top of the frame.
                self.add_filter(
                    "drawtext",
                    x="t/{length}*w".format(length=kwargs['length']),
                    text=">",
                    fontsize="10",
                    shadowcolor="black",
                    shadowx="2",
                    )
                del kwargs['length']
            except KeyError:
                t = ""
            super().add_filter(
                "drawtext",
                text="%{{pts}}{}".format(t),
                y="20",
                x="w-text_w-20",
                box="1",
                )
        else:
            super().add_filter(filtername, **kwargs)
        return self

class AudioProcessing():                         #{{{1
    """Apply audio filters to a stream."""

    def __init__(self, audio_stream):
        self.logger = logging.getLogger(__name__+".AudioProcessing")
        assert isinstance(audio_stream, io.IOBase)
        assert audio_stream.readable()

        self.input_audio = audio_stream
        self.process = None

    def mix(self, music):
        assert isinstance(music, str)

        args = [
            "ffmpeg", "-y", "-loglevel", "debug",
            ] + RAW_AUDIO + [
            "-i", "pipe:0",
            "-i", music,
            "-filter_complex", "amix=duration=first",
            ] + RAW_AUDIO + [
            "pipe:1",
            ]
        self.process = subprocess.Popen(
            args,
            stdin=self.input_audio,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            preexec_fn=_redirect_stderr_to_log_file,
            )
        self.logger.debug(
            SUBPROCESS_LOG.format(
                self.process.pid, args
                )
            )
        p = PipeHelper(self.process.stdout)
        p.start()
        self.output_audio = p.output
        self.input_audio.close()
        self.logger.debug(
            "Closed {} after spawning subprocess.\n"
            "Output is {}.".format(
                self.input_audio, self.output_audio
                )
            )
        return self


class Probe():                                   #{{{1
    """A wrapper for ffprobe, used to gather information about a video file."""

    def __init__(self, filename):
        self.filename = filename
        self.data = None

    def get_duration(self):
        self._probe()
        return float(self.data['format']['duration'])

    def get_format(self):
        self._probe()
        return self.data['format']['format_name']

    def _probe(self):
        """Actually call ffprobe and parse json output.

        This method returns immediately if the file has already been probed.
        """
        if self.data is not None:
            return
        self.process = subprocess.Popen(
            [
                "ffprobe", "-of", "json",
                "-show_error",
                "-show_format",
                "-show_streams",
                self.filename
            ],
            stderr=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            universal_newlines=True,
            )
        self.data = json.load(self.process.stdout)
        self.process.stdout.close()
