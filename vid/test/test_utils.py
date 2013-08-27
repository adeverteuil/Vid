# vim:cc=80:fdm=marker:fdl=0:fdc=1
#
# test_utils.py
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


import io
import queue
import select
import shutil
import os.path
import logging
import unittest
import unittest.mock
import threading
import subprocess

from .. import *


LOG_TEST_END = "---- Test ended " + ("-" * 54)
TEST_SHOT = "A roll/testsequence/M2U00054.mpg"


workdir = os.path.abspath(os.path.dirname(__file__))
header = (b'YUV4MPEG2 W720 H480 F30000:1001 '
          b'It A32:27 C420mpeg2 XYSCSS=420MPEG2\n')
initial_fds = sorted(os.listdir("/proc/self/fd"))
    # Opened file descriptors will be checked against this list after
    # each test to make sure files are not left open by the tested module.


class UtilsTestCase(unittest.TestCase):

    def setUp(self):
        os.chdir(workdir)

    def tearDown(self):
        logger = logging.getLogger(__name__+".tearDown")
        fds = os.listdir("/proc/self/fd")
        if sorted(fds) != initial_fds:
            for fd in initial_fds:
                try:
                    fds.remove(fd)
                except ValueError:
                    pass
            for fd in fds:
                try:
                    os.close(int(fd))
                except OSError:
                    # Maybe it was in the process of being closed.
                    fds.remove(fd)
                    continue
            if fds:
                logger.warning("File descriptors left opened: {}.".format(fds))
        logger.debug(LOG_TEST_END)

    def test_removeheader(self):
        logger = logging.getLogger(__name__+".test_removeheader")
        logger.debug("Testing RemoveHeader")

        # Simple usage, no errors.
        r, w = os.pipe()
        logger.debug("Created pipe {} -> {}".format(w, r))
        input = io.BytesIO(b"YUV4MPEG2\nsome data")
        output_w = open(w, "wb")
        output_r = open(r, "rb")
        t = RemoveHeader(input, output_w)
        t.start()
        self.assertEqual(output_r.read(), b"some data")
        t.join()
        self.assertEqual(t.get_bytes_read(), 9)
        self.assertEqual(t.get_bytes_written(), 9)
        self.assertIsNone(t.exception)
        self.assertTrue(input.closed)
        self.assertTrue(output_w.closed)
        output_r.close()

        # Test with much more data.
        p = subprocess.Popen(
            [
                "ffmpeg", "-y", "-i", TEST_SHOT, "-an",
                "-f", "yuv4mpegpipe", "-vcodec", "rawvideo",
                "-t", "2", "pipe:",
                ],
            stdin=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            )
        t = RemoveHeader(p.stdout, open(os.devnull, "wb"))
        t.start()
        t.join()
        self.assertEqual(t.get_bytes_read(), t.get_bytes_written())
        logger.debug("{} bytes copied.".format(t.get_bytes_read()))
        self.assertIsNone(t.exception)
        self.assertTrue(t.input.closed)
        self.assertTrue(t.output.closed)

        # Must check if arguments are proper file objects.
        with self.assertRaises(AssertionError):
            t = RemoveHeader(0, None)
        with self.assertRaises(AssertionError):
            t = RemoveHeader(open(os.devnull, "wb"), open(os.devnull, "wb"))

        # Test waiting for input.
        r, w = os.pipe()
        logger.debug("Created pipe {} -> {}".format(w, r))
        input_w = open(w, "wb")
        input_r = open(r, "rb")
        output = io.BytesIO()
        t = RemoveHeader(input_r, output, parties=2)
        t.start()
        input_w.write(b"YUV4MPEG2\nsome data")
        #os.write(w, b"YUV4MPEG2\nsome data")
        #os.fsync(w)
        input_w.flush()
        #os.fsync(input_w.fileno())
        try:
            while t.get_bytes_read() != 9:
                t.read_barrier.wait(timeout=2)
                t.write_barrier.wait(timeout=2)
        except threading.BrokenBarrierError:
            if not t.finished.is_set():
                logger.error(
                    "Thread blocked after \"some data\"!\n"
                    "{} bytes read, {} written.".format(
                        t.get_bytes_read(), t.get_bytes_written()
                        )
                    )
                raise
        self.assertTrue(t.is_alive())
        self.assertEqual(t.get_bytes_read(), 9)
        # Make sure it had time to increment bytes_written.
        t.read_barrier.wait(timeout=2)
        self.assertEqual(t.get_bytes_written(), 9)
        # Make a few other assertions on the way.
        self.assertEqual(output.getvalue(), b"some data")
        self.assertIsNone(t.exception)
        self.assertFalse(output.closed)
        self.assertFalse(input_r.closed)
        input_w.write(b"x")
        input_w.flush()
        try:
            t.write_barrier.wait(timeout=2)
            self.assertEqual(t.get_bytes_read(), 10)
            input_w.close()
            t.read_barrier.wait(timeout=2)
            self.assertEqual(output.getvalue(), b"some datax")
            t.write_barrier.wait(timeout=2)
        except threading.BrokenBarrierError:
            if not t.finished.is_set():
                logger.error("Thread blocked after \"x\"!")
                raise
        self.assertTrue(t.finished.is_set())
        t.join()
        self.assertFalse(t.is_alive())
        self.assertIsNone(t.exception)
        self.assertTrue(t.input.closed)
        self.assertTrue(t.output.closed)

    def test_concatenatestreams(self):
        logger = logging.getLogger(__name__+".test_concatenatestreams")
        logger.debug("Testing ConcatenateStreams")
        r, w = os.pipe()
        output_w = open(w, "wb")
        output_r = open(r, "rb")
        logger.debug("Created pipe {} -> {}".format(w, r))
        q = queue.Queue()
        cat = ConcatenateStreams(q, output_w)
        q.put(io.BytesIO(b"1111"))
        q.put(io.BytesIO(b"2222"))
        q.put(io.BytesIO(b"3333"))
        q.put(None)
        cat.start()
        q.join()
        cat.join()
        self.assertTrue(output_w.closed)
        self.assertEqual(output_r.read(), b"111122223333")
        output_r.close()

        r1, w1 = os.pipe()
        out1_w = open(w1, "wb")
        out1_r = open(r1, "rb")
        r2, w2 = os.pipe()
        out2_w = open(w2, "wb")
        out2_r = open(r2, "rb")
        logger.debug(
            "Created pipes {} -> {} and {} -> {}.".format(w1, r1, w2, r2)
            )
        q1 = queue.Queue()
        q2 = queue.Queue()
        cat1 = ConcatenateStreams(q1, out1_w)
        cat2 = ConcatenateStreams(q2, out2_w)
        q1.put(io.BytesIO(b"1111"))
        q1.put(io.BytesIO(b"2222"))
        q1.put(io.BytesIO(b"3333"))
        q1.put(None)
        q2.put(io.BytesIO(b"start"))
        q2.put(out1_r)
        q2.put(io.BytesIO(b"end"))
        q2.put(None)
        cat1.start()
        cat2.start()
        cat2.queue.join()
        self.assertEqual(out2_r.read(), b"start111122223333end")
        self.assertTrue(cat1.finished.is_set())
        cat2.join()
        self.assertTrue(cat2.finished.is_set())
        out2_r.close()

    def test_shot(self):
        logger = logging.getLogger(__name__+".test_shot")
        logger.debug("Testing Shot.")
        self.assertRaises(FileNotFoundError, Shot, 1)
        self.assertRaises(FileNotFoundError, Shot, "1")
        self.assertRaises(ValueError, Shot, "a")
        self.assertEqual(Shot(54).name, "A roll/testsequence/M2U00054.mpg")
        self.assertRaises(FileNotFoundError, Shot, 56)

        shot = Shot(54)
        self.assertEqual(repr(shot), "<Shot(54), seek=0, dur=None>")

        shot.cut(dur=5)
        self.assertEqual(shot.seek, 0)
        self.assertEqual(shot.dur, 5)

        shot.cut(seek=5)
        self.assertEqual(shot.seek, 5)
        self.assertEqual(shot.dur, None)

        shot.cut(5, 6)
        self.assertEqual(shot.seek, 5)
        self.assertEqual(shot.dur, 6)

        shot.cut()
        self.assertEqual(shot.seek, 0)
        self.assertEqual(shot.dur, None)

        shot.cut(45)
        self.assertEqual(shot.seek, 45)
        self.assertEqual(shot.dur, None)

        self.assertRaises(
            AssertionError,
            shot.cut,
            "1",
            )

        logger.debug("Testing Shot.demux().")
        # With header.
        logger.debug("Testing with header.")
        shot = Shot(54)
        shot.cut(5, 1)
        shot.demux(audio=False)
        self.assertEqual(
            shot.v_stream.readline()[0:9],
            b'YUV4MPEG2',
            )
        self.assertEqual(
            shot.v_stream.readline(),
            b'FRAME\n',
            )
        with open(os.devnull, "wb") as dn:
            # Pipe the rest of the file in os.devnull to be sure there
            # is no blocking.
            shutil.copyfileobj(shot.v_stream, dn)
        shot.v_stream.close()

        # Without header.
        logger.debug("Testing without header.")
        shot = Shot(54)
        shot.cut(5, 1)
        shot.demux(audio=False, remove_header=True)
        self.assertEqual(
            shot.v_stream.readline(),
            b'FRAME\n',
            )
        with open(os.devnull, "wb") as dn:
            # Pipe the rest of the file in os.devnull to be sure there
            # is no blocking.
            shutil.copyfileobj(shot.v_stream, dn)
        shot.v_stream.close()

        # Close buffer before EOF.
        logger.debug("Test with closing buffer before EOF.")
        shot = Shot(54)
        shot.cut(5, 1)
        shot.demux(audio=False)
        b = shot.v_stream.read(1024)
        shot.v_stream.close()
        shot.v_process.wait()
        del b

        # Play it.
        logger.debug("Test playing the file")
        shot = Shot(54)
        shot.cut(6, 1)
        shot.demux(audio=False)
        args = (["ffplay", "-autoexit"] + RAW_VIDEO +
                ["-i", "pipe:{}".format(shot.v_stream.fileno())])
        p = subprocess.Popen(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            pass_fds=(shot.v_stream.fileno(),), # shot.a_stream.fileno()),
            )
        shot.v_stream.close()
        p.wait()

    def test_player(self):
        logger = logging.getLogger(__name__+".test_player")
        logger.debug("Testing Player")
        shot = Shot(54)
        shot.cut(7, 1)
        shot.demux(audio=False)
        player = Player(shot.v_stream)
        self.assertEqual(
            player.process.wait(),
            0
            )

        # Try with a pipe.
        p = subprocess.Popen(
            [
                "ffmpeg", "-y", "-i", "A roll/testsequence/M2U00054.mpg",
                "-f", "avi", "-t", "1", "pipe:"
            ],
            stdin=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            )
        logger.debug("Reading ffmpeg output from pipe {}".format(p.stdout))
        player = Player(p.stdout)
        self.assertEqual(
            player.process.wait(),
            0
            )
        p.wait()

    def test_multiplexer(self):
        logger = logging.getLogger(__name__+".test_multiplexer")
        logger.debug("Testing Multiplexer")
        shot = Shot(54).cut(0, 1)
        shot.demux()
        muxer = Multiplexer(shot.v_stream, shot.a_stream)
        player = Player(muxer.mux())
        self.assertEqual(player.process.wait(), 0)

        # Add filter "showdata" for Shot and Multiplexer.
        l = 2
        shot = Shot(54).cut(0, l).add_filter("showdata")
        shot.demux()
        muxer = Multiplexer(shot.v_stream, shot.a_stream)
        muxer.add_filter("showdata", length=l)
        player = Player(muxer.mux())
        self.assertEqual(player.process.wait(), 0)

    def test_subprocesssupervisor(self):
        logger = logging.getLogger(__name__+".test_subprocesssupervisor")
        logger.debug("Testing SubprocessSupervisor.")
        lock = threading.Lock()
        lock.acquire()
        p = subprocess.Popen("sleep 0.1", shell=True)
        SubprocessSupervisor(
            (p.wait,p.wait),
            lock.release,
            name="test",
            ).start()
        self.assertTrue(lock.acquire(timeout=1))

    def test_concatenateshots(self):
        logger = logging.getLogger(__name__+".test_concatenateshots")
        logger.debug("Testing ConcatenateShots.")
        fvr, fvw = os.pipe()
        vr = open(fvr, "rb")
        vw = open(fvw, "wb")
        far, faw = os.pipe()
        ar = open(far, "rb")
        aw = open(faw, "wb")
        logger.debug(
            "Created pipes video {} -> {} and audio {} -> {}.".format(
                fvw, fvr, faw, far
                )
            )
        q = queue.Queue()
        cat = ConcatenateShots(q, vw, aw)
        muxer = Multiplexer(vr, ar)
        player = Player(muxer.mux())
        #q.put(Shot(54).cut(0, 10))
        silence = 0
        for i in [4, 2, 6, 1, 5, 3, 9, 8, 7, 0]:
            shot = Shot(54).cut(i, .1)
            if silence % 2 == 0:
                shot.generate_silence()
            q.put(shot)
            silence += 1
        q.put(None)
        cat.start()
        #q.join()
        muxer.process.wait()
        player.process.wait()

    def test_shot_silent(self):
        logger = logging.getLogger(__name__+".test_shot_silent")
        logger.debug("Testing Shot.silent()")
        shot = Shot(54).cut(0, 0.1).generate_silence()
        silence = shot.demux(video=False)[0].read()
        logger.debug("Stream length {}.".format(len(silence)))
        # Let's assume it generated between 0.1 and 0.13 seconds of silence.
        # 2 channels, 2 bytes (16 bits) per sample, 44100 sample rate.
        duration = len(silence) / 2 / 2 / 44100
        self.assertGreaterEqual(duration, 0.1)
        self.assertLessEqual(duration, 0.13)
        # It must have generated the same duration as the sound from the
        # same clip.
        shot = Shot(54).cut(0, 0.1)
        sound = shot.demux(video=False)[0].read()
        shot.a_stream.close()
        self.assertEqual(len(sound), len(silence))
        # Try the same without specifying duration.
        shot = Shot(54)
        sound = shot.demux(video=False)[0].read()
        shot.a_stream.close()
        shot = Shot(54).generate_silence()
        silence = shot.demux(video=False)[0].read()
        shot.a_stream.close()
        self.assertEqual(len(sound), len(silence))

    def test_add_filter(self):
        logger = logging.getLogger(__name__+".test_add_filter")
        logger.debug("Testing Shot.add_filter()")
        shot = Shot(54).cut(4, 5).add_filter("showdata")
        shot.add_filter(
            "drawtext",
            x="w/2-text_w/2",
            y="h/2-text_h/2",
            #text="':,[]\\",
            text="special characters escaping :',\\['];",
            fontcolor="white",
            fontsize="25",
            fontfile="/usr/share/fonts/TTF/ttf-inconsolata.otf",
            box="1",
            boxcolor="0x000000aa",
            )
        shot.demux()
        multiplexer = Multiplexer(shot.v_stream, shot.a_stream)
        player = Player(multiplexer.mux())
        player.process.wait()

    def test_audioprocessing_mix(self):
        logger = logging.getLogger(__name__+".test_audioprocessing_mix")
        logger.debug("Testing Shot.add_filter()")
        shot = Shot(54).cut(4, 5)
        shot.demux()
        mixer = AudioProcessing(shot.a_stream)
        mixer.mix("music/Anitek_-_Nightlife.mp3")
        multiplexer = Multiplexer(shot.v_stream, mixer.output_audio)
        player = Player(multiplexer.mux())
        returncodes = {
            'shot.v_process': shot.v_process.wait(),
            'shot.a_process': shot.a_process.wait(),
            'mixer.process': mixer.process.wait(),
            'multiplexer.process': multiplexer.process.wait(),
            'player.process': player.process.wait(),
            }
        for k, v in returncodes.items():
            self.assertEqual(v, 0, msg="Return codes: {}".format(returncodes))

    def test_probe_duration(self):
        logger = logging.getLogger(__name__+".test_audioprocessing_mix")
        logger.debug("Testing Shot.add_filter()")
        probe = Probe("A roll/testsequence/M2U00054.mpg")
        self.assertIsInstance(probe.get_duration(), float)
