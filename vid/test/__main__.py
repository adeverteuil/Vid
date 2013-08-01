"""Runs all unit tests.

From the project's base directory, execute:
    python -m bwusage.test
- or -
    python -m unittest discover.

The latter has verbosity set to '2'."""


import os
import unittest

suite = unittest.defaultTestLoader.discover('.')
unittest.TextTestRunner(verbosity=2).run(suite)
