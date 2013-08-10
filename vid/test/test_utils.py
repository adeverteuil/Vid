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
header = (b'YUV4MPEG2 W720 H480 F30000:1001 '
          b'It A32:27 C420mpeg2 XYSCSS=420MPEG2\n')


class ShotTestCase(unittest.TestCase):

    def setUp(self):
        os.chdir(workdir)

    def test_shot_init(self):
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
            "<Shot(54), seek=0, dur=None>",
            )

    @unittest.skip("rewriting code")
    def test_cut(self):
        shot = Shot(54)

        cut = shot.cut(dur=5)
        self.assertEqual(shot.seek, 0)
        self.assertEqual(shot.dur, 5)

        cut = shot.cut(seek=5)
        self.assertEqual(shot.seek, 5)
        self.assertEqual(shot.dur, None)

        cut = shot.cut(5, 6)
        self.assertEqual(shot.seek, 5)
        self.assertEqual(shot.dur, 6)

        cut = shot.cut()
        self.assertEqual(shot.seek, 0)
        self.assertEqual(shot.dur, None)

        cut = shot.cut(45)
        self.assertEqual(shot.seek, 45)
        self.assertEqual(shot.dur, None)

    def test_shot_remove_header(self):
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
        self.assertFalse(t.is_alive())

    def test_shot_demux(self):
        shot = Shot(54)
        shot.cut(5, 1)
        shot.demux(audio=False)
        self.assertEqual(
            shot.v_stream.readline(),
            header
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
