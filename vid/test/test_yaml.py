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
import yaml
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
        doc = "movie:\n  - [1, 2, 3]\nmultiplexer: ~"
        reader = YAMLReader()
        self.assertEqual(
            reader.load(doc),
            {'movie': [[1, 2, 3, {}]]},
            )

        # Check invalid document.
        doc = "multiplexer: ~"
        with self.assertRaises(KeyError):
            reader.load(doc)

    def test_yamlreader_methods(self):
        logger = logging.getLogger(__name__+".test_yamlreader_methods")
        logger.debug("Testing YAMLReader methods")
        reader = YAMLReader()

        # Testing _load().
        # Will test valid and invalid string, pathname and open file.
        doc = "{movie: [[1, 2, 3]]}"
        self.assertEqual(
            reader._load(doc),
            {'movie': [[1, 2, 3]]}
            )
        with self.assertRaises(yaml.YAMLError):
            reader._load("asf: - [1] - [1]")
        with tempfile.NamedTemporaryFile("w+t") as f:
            self.assertEqual(
                reader._load(f.name),
                None
                )
            f.write("- a\n- b")
            f.seek(0)
            self.assertEqual(
                reader._load(f.name),
                ["a", "b"]
                )
            # Append invalid syntax.
            f.write(": - c")
            f.seek(0)
            with self.assertRaises(yaml.YAMLError):
                reader._load(f.name)
            f.seek(0)
            f.write("- a\n- b\n- c")
            f.truncate()
            f.seek(0)
            self.assertEqual(
                reader._load(f),
                ["a", "b", "c"]
                )

            # Keep _check_root() and load() for the end.
            # Test _check_filter()
            good_filters = [
                "a_string",
                ["a_string_in_a_list"],
                ["a_string_and_empty_kwargs", {}],
                ["a_string_and_None", None],
                ["a_string_and_kwargs", {'key1': "value1", 'key2': 2}],
                ]
            for f in good_filters:
                data = reader._check_filter(f, ["test"])
                # Check canonical form.
                self.assertIsInstance(data, list)
                self.assertIsInstance(data[0], str)
                self.assertIsInstance(data[1], dict)
            with self.assertRaisesRegex(ValueError, "not a list.*2 items"):
                reader._check_filter(None, ["test"])
            with self.assertRaisesRegex(TypeError, "name is not a string"):
                reader._check_filter([(1, 2)], ["test"])
            with self.assertRaisesRegex(TypeError, "Filter.*not a mapping"):
                reader._check_filter(["filter", ("x", "y")], ["test"])
            with self.assertRaisesRegex(TypeError, "keys must be strings"):
                reader._check_filter(["f", {1: "y"}], ["test"])
            with self.assertRaisesRegex(TypeError, "values must be"):
                reader._check_filter(["f", {"x": None}], ["test"])

            # Test _check_globals()
            # None is acceptable.
            self.assertIsNone(reader._check_globals(None))
            with self.assertRaises(TypeError):
                reader._check_globals("String is not a valid type")
            with self.assertRaises(KeyError):
                reader._check_globals({'foo': "Not a Shot constructor kwarg."})
            with self.assertRaises(TypeError):
                reader._check_globals({'filters': "string instead of list"})
            with self.assertRaises(TypeError):
                reader._check_globals({'silent': "string instead of bool"})
            with self.assertRaises(TypeError):
                reader._check_globals({'pattern': True}) # instead of string
            self.assertEqual(
                reader._check_globals(
                    {'pattern': "test", 'silent': False, 'filters': ["test"]}
                    ),
                {'pattern': "test", 'silent': False, 'filters': [["test", {}]]}
                )

            # Test _check_music()
            # Nons is acceptable
            self.assertIsNone(reader._check_music(None))
            with self.assertRaises(FileNotFoundError):
                reader._check_music("foo")
            with tempfile.NamedTemporaryFile() as t:
                self.assertEqual(
                    reader._check_music(t.name),
                    t.name
                    )
            with self.assertRaises(TypeError):
                reader._check_music(["foo"])
