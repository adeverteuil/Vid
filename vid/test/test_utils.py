# vim:cc=80:fdm=marker:fdl=0:fdc=3
#
# test_utils.py
# Copyright (C) 2013  Alexandre de Verteuil


import io
import os.path
import unittest
import subprocess

from .. import Shot
from .. import Cat


workdir = os.path.abspath(os.path.dirname(__file__))


class ShotTestCase(unittest.TestCase):

    def setUp(self):
        os.chdir(workdir)

    def test_init(self):
        with self.assertRaises(FileNotFoundError):
            shot = Shot(1)
            self.assertIsInstance(
                shot,
                Shot,
                msg="Instanciation of Shot(1).",
                )
            self.assertIsNone(shot.pathname)
        with self.assertRaises(FileNotFoundError):
            shot = Shot("1")
            self.assertIsInstance(
                shot,
                Shot,
                msg="Instanciation of Shot(\"1\")",
                )
            self.assertIsNone(shot.pathname)
        self.assertRaises(ValueError, Shot, "a")
        self.assertEqual(
            Shot(54).pathname,
            "A roll/testsequence/M2U00054.mpg",
            msg="Looking for roll 54.",
            )
        self.assertEqual(
            Shot(55).pathname,
            "A roll/testsequence/M2U00055.mpg",
            msg="Looking for roll 55.",
            )
        with self.assertRaises(FileNotFoundError):
            pathname = Shot(56).pathname

    def test_play(self):
        shot = Shot(54)
        #shot.play()
        shot.play(6, 0.5)
        shot.play(45)
        with self.assertRaises(subprocess.SubprocessError):
            shot.play("a")

    def test_cut(self):
        shot = Shot(54)
        cut = shot.cut(dur=5, audio=False)
        self.assertIsInstance(
            cut,
            io.BufferedIOBase,
            msg="Returned object: {}".format(type(cut))
            )
        self.assertEqual(
            cut.readline(),
            b'YUV4MPEG2 W720 H480 F30000:1001 It A32:27 '
            b'C420mpeg2 XYSCSS=420MPEG2\n'
            )
        self.assertEqual(
            cut.readline(),
            b'FRAME\n'
            )
        while cut.read():
            # Just pump the stdout from ffmpeg.
            continue
        self.assertEqual(shot.process.wait(), 0)

    def test_cat(self):
        temp = io.BytesIO()
        cat = Cat(((54, 0, .1),), video=temp)
        #self.assertEqual(
        #    temp.readline(),
        #    b'YUV4MPEG2 W720 H480 F30000:1001 It A32:27 '
        #    b'C420mpeg2 XYSCSS=420MPEG2\n'
        #    )
        vtemp = io.BytesIO()
        atemp = io.BytesIO()
        cat = Cat(((54, 0, .1),), video=vtemp, audio=atemp)
        with self.assertRaises(FileNotFoundError):
            cat = Cat(((56, 0, .1),), video=temp)
        vtemp = io.BytesIO()
        atemp = io.BytesIO()
        with self.assertRaises(FileNotFoundError):
            cat = Cat(((56, 0, .1),), video=vtemp, audio=atemp)
        vtemp = io.BytesIO()
        atemp = io.BytesIO()
        p = subprocess.Popen(
            [
                "ffplay",
                "-autoexit",
                "-f", "yuv4mpegpipe",
                "pipe:",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
            )
        cat = Cat(
            ((54, 0, 1), (54, 4, 1), (54, 2, 1)),
            video=p.stdin, audio=atemp
            )
        #Shot._pipe_to_player(cat.video, "Concatenation test")
