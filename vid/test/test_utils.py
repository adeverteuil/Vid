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
import threading
import subprocess

from .. import *


workdir = os.path.abspath(os.path.dirname(__file__))
header = (b'YUV4MPEG2 W720 H480 F30000:1001 '
          b'It A32:27 C420mpeg2 XYSCSS=420MPEG2\n')


class UtilsTestCase(unittest.TestCase):

    def setUp(self):
        os.chdir(workdir)

    def tearDown(self):
        logger = logging.getLogger(__name__+".tearDown")
        fds = os.listdir("/proc/self/fd")
        std = ["0", "1", "2"]
        if sorted(fds) != std:
            for fd in std:
                try:
                    fds.remove(fd)
                except ValueError:
                    pass
            logger.warning("File descriptors left opened: {}.".format(fds))

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
        return

    def test_player(self):
        logger = logging.getLogger(__name__+".test_play")
        logger.debug("Testing Player")
        shot = Shot(54)
        shot.cut(7, 1)
        shot.demux(audio=False)
        player = Player(shot.v_stream)
        self.assertEqual(
            player.process.wait(),
            0
            )

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
        logger.debug("Testing Cat.")
        cat = Cat()
        cat.append(Shot(54).cut(6, 1))
        cat.append(Shot(54).cut(5, 1))
        cat.append(Shot(54).cut(4, 1))
        cat.process()
        logger.debug(
            "cat.v_stream = {}\n"
            "cat.a_stream = {}".format(
                cat.v_stream,
                cat.a_stream,
                )
            )
        muxer = Multiplexer(cat.v_stream, cat.a_stream)
        s = muxer.mux()
        logger.debug("muxer output = {}".format(s))
        with open("testfile", "wb") as f:
            shutil.copyfileobj(s, f)
        #player = Player(s)
        #s.close()
        #player.process.wait()

    def test_cat_concatenate_streams(self):
        q = queue.Queue()
        p1r, p1w = os.pipe()
        p2r, p2w = os.pipe()
        p3r, p3w = os.pipe()
        q.put(open(p1r, "rb"))
        q.put(open(p2r, "rb"))
        q.put(False)
        os.write(p1w, b'asdf\n')
        os.write(p2w, b'fdsa\n')
        os.close(p1w)
        os.close(p2w)
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
