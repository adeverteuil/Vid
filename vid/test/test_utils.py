# vim:cc=80:fdm=marker:fdl=0:fdc=3
#
# test_utils.py
# Copyright (C) 2013  Alexandre de Verteuil


import os.path
import unittest

from .. import Shot


class ShotTestCase(unittest.TestCase):

    def setUp(self):
        os.chdir(os.path.dirname(__file__))

    def test_init(self):
        shot = Shot(1)
        shot = Shot("1")
        self.assertRaises(
            ValueError,
            Shot,
            "a",
            )
        self.assertEqual(
            Shot(54).pathname,
            "A roll/testsequence/M2U00054.mpg",
            )
        self.assertEqual(
            Shot(55).pathname,
            "A roll/testsequence/M2U00055.mpg",
            )
        with self.assertRaises(FileNotFoundError):
            pathname = Shot(56).pathname
