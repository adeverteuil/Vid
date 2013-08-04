# vim:cc=80:fdm=marker:fdl=0:fdc=1
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
        shot.cut(6, 1)
        shot.play()
        #with self.assertRaises(subprocess.SubprocessError):
        #    shot.play("a")

    def test_cut(self):
        shot = Shot(54)

        cut = shot.cut(dur=5)
        self.assertNotIn('-ss', shot.input_args)
        self.assertNotIn('-ss', shot.output_args)
        self.assertEqual(shot.output_args['-t'], "5")

        cut = shot.cut(seek=5)
        self.assertNotIn('-ss', shot.input_args)
        self.assertEqual(shot.output_args['-ss'], "5")
        self.assertNotIn('-t', shot.output_args)

        cut = shot.cut(5, 6)
        self.assertNotIn('-ss', shot.input_args)
        self.assertEqual(shot.output_args['-ss'], "5")
        self.assertEqual(shot.output_args['-t'], "6")

        cut = shot.cut()
        self.assertNotIn('-ss', shot.input_args)
        self.assertNotIn('-ss', shot.output_args)
        self.assertNotIn('-t', shot.output_args)

        cut = shot.cut(45)
        self.assertEqual(shot.input_args['-ss'], "25")
        self.assertEqual(shot.output_args['-ss'], "20")
        self.assertNotIn('-t', shot.output_args)

    @unittest.skip("Rewriting code")
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
