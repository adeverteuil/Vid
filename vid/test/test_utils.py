# vim:cc=80:fdm=marker:fdl=0:fdc=1
#
# test_utils.py
# Copyright (C) 2013  Alexandre de Verteuil


import io
import shutil
import os.path
import unittest
import threading
import subprocess

from .. import *


workdir = os.path.abspath(os.path.dirname(__file__))


class ShotTestCase(unittest.TestCase):

    def setUp(self):
        os.chdir(workdir)

    def test_shot_init(self):
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

    @unittest.skip("rewriting code")
    def test_play(self):
        shot = Shot(54)
        #shot.play()
        shot.cut(6, 1)
        shot.play()
        #with self.assertRaises(subprocess.SubprocessError):
        #    shot.play("a")

    def test_shot_repr(self):
        self.assertEqual(
            repr(Shot(54)),
            "<_io.FileIO name='A roll/testsequence/M2U00054.mpg' mode='rb'>"
            )

    def test_shot_read(self):
        shot = Shot(54)
        self.assertIsInstance(
            shot.read(4),
            bytes,
            )
        shot.close()

    @unittest.skip("rewriting code")
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

    def test_shot_demux(self):
        pipe_r, pipe_w = os.pipe()
        print("Pipes {} and {}.".format(pipe_r, pipe_w))
        with open(pipe_w, "wb") as pipe_w:
            with Shot(54) as shot, \
            open(pipe_r, "rb") as f:
                shot.demux(video=pipe_w)
                self.assertEqual(
                    f.readline(),
                    b'YUV4MPEG2 W720 H480 F30000:1001 '
                    b'It A32:27 C420mpeg2 XYSCSS=420MPEG2\n'
                    )
                self.assertEqual(
                    f.readline(),
                    b'FRAME\n',
                    )
        pipe_r, pipe_w = os.pipe()
        print("Pipes {} and {}.".format(pipe_r, pipe_w))
        #with open(pipe_w, "wb") as pipe_w:
        with Shot(54) as shot, \
        open(pipe_r, "rb") as f:
            shot.demux(video=pipe_w, remove_header=True)
            self.assertEqual(
                f.readline(),
                b'FRAME\n',
                )
            with open("testfile", "wb") as dn:
                dn.write(
                    b'YUV4MPEG2 W720 H480 F30000:1001 '
                    b'It A32:27 C420mpeg2 XYSCSS=420MPEG2\n'
                    )
                dn.write(b'FRAME\n')
                shutil.copyfileobj(f, dn)

    @unittest.skip("rewriting code")
    def test_cat(self):
        # Test the _cat private method.
        fifos = [
            "vid_clip_0_v", "vid_clip_1_v",
            "vid_clip_0_a", "vid_clip_1_a",
            "vid_cat_v", "vid_cat_a",
            ]
        for fifo in fifos:
            try:
                os.mkfifo(fifo)
            except FileExistsError:
                pass
        shot1 = Shot(54)
        shot1.cut(6, 5)
        shot2 = Shot(54)
        shot2.cut(3, 5)
        shot1.process(video=fifos[0])
        shot2.process(video=fifos[1], remove_header=True)
        shot1.process(audio=fifos[2])
        shot2.process(audio=fifos[3])
        cat = Cat()
        cat._cat(fifos[0:2], os.devnull)  # Concatenate video.
        cat._cat(fifos[2:4], os.devnull)  # Concatenate audio.

        # Test the merge process.
        shot1.process(video=fifos[0])
        shot1.process(audio=fifos[1])
        cat._merge_streams(fifos[0], fifos[1], os.devnull)

        # Test _cat and _merge_streams together.
        shot1.process(video=fifos[0])
        shot2.process(video=fifos[1], remove_header=True)
        shot1.process(audio=fifos[2])
        shot2.process(audio=fifos[3])
        cat = Cat()
        thread_v = threading.Thread(  # Concatenate video.
            target=cat._cat,
            args=(fifos[0:2], fifos[4]),
            )
        thread_v.start()
        thread_a = threading.Thread(  # Concatenate audio.
            target=cat._cat,
            args=(fifos[2:4], fifos[5]),
            )
        thread_a.start()
        cat._merge_streams(fifos[4], fifos[5], os.devnull)

        # Test the whole process.
        # One clip.
        cat = Cat()
        shot = Shot(54)
        shot.cut(0, 1)
        cat.append(shot)
        self.assertEqual(
            cat.sequence,
            [shot]
            )
        shot2 = Shot(54)
        shot2.cut(5, 0.2)
        cat.append(shot2)
        self.assertEqual(
            cat.sequence,
            [shot, shot2]
            )
        shot3 = Shot(54)
        shot3.cut(4, .1)
        cat.append(shot3)
        self.assertEqual(
            cat.sequence,
            [shot, shot2, shot3]
            )
        cat.process(os.devnull)
