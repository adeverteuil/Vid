# vim:cc=80:fdm=marker:fdl=0:fdc=1
#
# test_utils.py
# Copyright (C) 2013  Alexandre de Verteuil


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
