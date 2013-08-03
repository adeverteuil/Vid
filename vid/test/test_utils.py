# vim:cc=80:fdm=marker:fdl=0:fdc=3
#
# test_utils.py
# Copyright (C) 2013  Alexandre de Verteuil


import io
import os.path
import unittest
import subprocess

from .. import Shot


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
        cut = shot.cut(dur=0.1, audio=False)
        self.assertIsInstance(
            cut,
            io.BufferedIOBase,
            msg="Returned object: {}".format(type(cut))
            )
        while cut.read():
            # Just pump the stdout from ffmpeg.
            continue
        self.assertEqual(shot.process.wait(), 0)

    def test_cat(self):
        pass
        # This is a stub.
