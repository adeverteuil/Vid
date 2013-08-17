# vim:cc=80:fdm=marker:fdl=0:fdc=1
#
# test_utils.py
# Copyright (C) 2013  Alexandre de Verteuil


import io
import queue
import shutil
import os.path
import logging
import unittest
import unittest.mock
import threading
import subprocess

from .. import *


LOG_TEST_END = "---- Test ended " + ("-" * 54)


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
            logger.warning("File descriptors left opened: {}.".format(fds))
            for fd in fds:
                try:
                    os.close(int(fd))
                except OSError:
                    # Maybe it was in the process of being closed.
                    continue
        logger.debug(LOG_TEST_END)

    def test_shot_init(self):
        logger = logging.getLogger(__name__+".test_shot_init")
        logger.debug("Testing Shot.__init__")
        with self.assertRaises(
            FileNotFoundError,
            msg="Instanciation of Shot(1)",
            ):
            shot = Shot(1)
        with self.assertRaises(
            FileNotFoundError,
            msg="Instanciation of Shot(\"1\")",
            ):
            shot = Shot("1")
            self.assertIsInstance(
                shot,
                Shot,
                )
        self.assertRaises(ValueError, Shot, "a")
        self.assertEqual(
            Shot(54).name,
            "A roll/testsequence/M2U00054.mpg",
            msg="Looking for roll 54.",
            )
        self.assertEqual(
            Shot(55).name,
            "A roll/testsequence/M2U00055.mpg",
            msg="Looking for roll 55.",
            )
        with self.assertRaises(FileNotFoundError):
            pathname = Shot(56).name

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


    def test_shot_repr(self):
        logger = logging.getLogger(__name__+".test_shot_repr")
        logger.debug("Testing Shot.__repr__")
        self.assertEqual(
            repr(Shot(54)),
            "<Shot(54), seek=0, dur=None>",
            )

    def test_cut(self):
        logger = logging.getLogger(__name__+".test_cut")
        logger.debug("Testing Shot.cut")
        shot = Shot(54)

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

    def test_shot_remove_header(self):
        logger = logging.getLogger(__name__+".test_shot_remove_header")
        logger.debug("Testing Shot._remove_header")
        pipe1_r, pipe1_w = os.pipe()
        pipe2_r, pipe2_w = os.pipe()
        t = threading.Thread(
            target=Shot._remove_header,
            args=(pipe1_r, pipe2_w),
            )
        t.start()
        with open(pipe1_w, "wb") as w:
            w.write(header)
            w.write(b'test')
            w.close()
        with open(pipe2_r, "rb") as r:
            self.assertEqual(
                r.read(),
                b'test',
                )
            self.assertEqual(
                r.read(),
                b'',
                )
        t.join(timeout=0.1)
        self.assertFalse(t.is_alive())

    def test_shot_demux(self):
        logger = logging.getLogger(__name__+".test_shot_demux")
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
        shot.process.wait()
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

    def test_cat(self):
        logger = logging.getLogger(__name__+".test_cat")
        logger.debug("Testing Cat with 1 shot.")
        cat = Cat()
        cat.append(Shot(54).cut(4, 1))
        cat.process()
        muxer = Multiplexer(cat.v_stream, cat.a_stream)
        s = muxer.mux()
        logger.debug("muxer output = {}".format(s))
        #with open("testfile", "wb") as f:
        #    shutil.copyfileobj(s, f)
        player = Player(s)
        player.process.wait()

        logger.debug("Testing Cat with bogus streams.")
        cat = Cat()
        pipes = os.pipe(), os.pipe(), os.pipe()
        pipes += os.pipe(), os.pipe(), os.pipe()
        logger.debug(
            "Created 6 pipes:\n" +
            "\n".join(
                ["write {1} -> read {0}".format(*pipe) for pipe in pipes]
                ) +
            "\n"
            )
        os.write(pipes[0][1], b"header\nFRAME\nvideo 1FRAME\nvideo 1")
        os.write(pipes[1][1], b"audio 1, ")
        os.write(pipes[2][1], b"FRAME\nvideo 2FRAME\nvideo 2")
        os.write(pipes[3][1], b"audio 2, ")
        os.write(pipes[4][1], b"FRAME\nvideo 3FRAME\nvideo 3")
        os.write(pipes[5][1], b"audio 3")
        shots = [unittest.mock.Mock() for x in range(3)]
        shots[0].v_stream = open(pipes[0][0], "rb")
        shots[0].a_stream = open(pipes[1][0], "rb")
        shots[1].v_stream = open(pipes[2][0], "rb")
        shots[1].a_stream = open(pipes[3][0], "rb")
        shots[2].v_stream = open(pipes[4][0], "rb")
        shots[2].a_stream = open(pipes[5][0], "rb")
        cat.append(shots[0])
        cat.append(shots[1])
        cat.append(shots[2])
        cat.process()
        for pipe in pipes:
            os.close(pipe[1])
        self.assertEqual(
            cat.v_stream.read(),
            b"header\nFRAME\nvideo 1FRAME\nvideo 1"
            b"FRAME\nvideo 2FRAME\nvideo 2"
            b"FRAME\nvideo 3FRAME\nvideo 3"
            )
        self.assertEqual(
            cat.a_stream.read(),
            b"audio 1, audio 2, audio 3"
            )
        self.assertEqual(cat.v_stream.read(), b"")
        self.assertEqual(cat.a_stream.read(), b"")
        cat.v_stream.close()
        cat.a_stream.close()

    def test_cat_3_shots(self):
        logger = logging.getLogger(__name__+".test_cat_3_shots")
        logger.debug("Testing Cat with 3 shots.")
        cat = Cat()
        cat.append(Shot(54).cut(6, 1))
        #cat.append(Shot(54).cut(5, 1))
        cat.append(Shot(54).cut(4, 1))
        cat.process()
        muxer = Multiplexer(cat.v_stream, cat.a_stream)
        s = muxer.mux()
        logger.debug("muxer output = {}".format(s))
        #with open("testfile", "wb") as f:
        #    shutil.copyfileobj(s, f)
        player = Player(s)
        self.assertEqual(player.process.wait(), 0)

    def test_cat_concatenate_streams(self):
        logger = logging.getLogger(__name__+".test_cat_concatenate_streams")
        logger.debug("Testing Cat._concatenate_streams.")
        q = queue.Queue()
        p1r, p1w = os.pipe()
        p2r, p2w = os.pipe()
        p3r, p3w = os.pipe()
        logger.debug(
            "Created 3 pipes:\n"
            "write {} -> read {}\n"
            "write {} -> read {}\n"
            "write {} -> read {} (concatenated stream).".format(
                p1w, p1r, p2w, p2r, p3w, p3r
                )
            )
        q.put(open(p1r, "rb"))
        q.put(open(p2r, "rb"))
        q.put(None)
        os.write(p1w, b'asdf\n')
        os.write(p2w, b'fdsa\n')
        os.close(p1w)
        os.close(p2w)
        logger.debug("Wrote to and closed fds {} and {}.".format(p1w, p2w))
        t = threading.Thread(
            target=Cat._concatenate_streams,
            args=(q, open(p3w, "wb")),
            )
        t.start()
        self.assertEqual(
            os.read(p3r, 1024),
            b'asdf\nfdsa\n',
            )
        t.join()
        os.close(p3r)

    def test_multiplexer(self):
        logger = logging.getLogger(__name__+".test_multiplexer")
        logger.debug("Testing Multiplexer")
        shot = Shot(54).cut(0, 1)
        shot.demux()
        muxer = Multiplexer(shot.v_stream, shot.a_stream)
        #muxed = muxer.mux()
        player = Player(muxer.mux())
        self.assertEqual(player.process.wait(), 0)
