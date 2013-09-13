# vim:cc=80:fdm=marker:fdl=0:fdc=1
#
# test_yaml.py
# Copyright © 2013  Alexandre de Verteuil        {{{1
#
# This file is part of Vid.
#
# Vid is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# Vid is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#}}}


import io
import os.path
import logging
import unittest
import tempfile

from .. import *


class YAMLTestCase(unittest.TestCase):

    def test_yamlreader(self):
        logger = logging.getLogger(__name__+".test_yamlreader")
        logger.debug("Testing YAMLReader")
        reader = YAMLReader()
        with self.assertRaises(TypeError):
            # Missing arguments.
            data = reader._load()
        # Read YAML from string, file object, and file name.
        with tempfile.TemporaryDirectory() as d:
            string = "- a\n- b"
            fileobj = io.StringIO(string)
            filename = os.path.join(d, "tmpfile")
            with open(filename, "w") as f:
                f.write(string)
            for y in [string, fileobj, filename]:
                data = YAMLReader()._load(y)
                self.assertEqual(data, ["a", "b"])

        # Check a valid document.
        doc = (
            "movie: [1, 2, 3]\nmultiplexer: ~"
            )
        reader = YAMLReader()
        reader.load(doc)
