# vim:cc=80:fdm=marker:fdl=0:fdc=1
#
# yaml.py
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


# Imports                                        {{{1
import os.path
import logging

import yaml


# Global variables                               {{{1
# This YAML template is used both as user documentation
# and as a starting point for making a new movie with Vid.
# The CLI will write this to stdout if requested.
YAML_TEMPLATE = """\
%YAML 1.2
# vim:sts=2:ts=2:sw=2
---
meta:  # Optional
  # Won't actually be used,
  # but may help you organize your files.
  title: The Title
  date: {date}
  author: {name}
globals:  # Optional
  # These keyword parameters will be passed
  # to every shots unless overridden in the
  # movie section.
  silent: false  # Set to "true" to make a silent movie.
                 # You can still mix music after.
  # This is the file path name pattern as a Python format string.
  # Edit it to suit your workflow.
  pattern: "{pattern}"
music:  # Optional
  # The music track for the movie.
  # Replace the next line with the filename.
  ~  # "~" is YAML syntax for "none".
movie:
  # A sequence of shots.
  # Each shot is described by a sequence of arguments
  # to be passed to the Shot constructor.
  #
  # Positional arguments must be given first,
  # followed by a mapping of keyword arguments.
  # Only the first positional argument is required.
  #
  # - [42, 4, 2]
  # - [ !!int id, !!int start, !!int duration,
  #     "filters": [
  #       [ !!str filtername,
  #         {{ !!str arg: value,
  #           !!str arg: value,
  #         }}
  #       ]
  #     ]
  #   ]
  # - - 42
  #   - 4
  #   - 2
  #   - filters:
  #       - - drawtext
  #         - x: 10
  #           y: 10
  #           text: My title
  # - - [42, 4, 2, {{filters: [[drawtext, {{x: 10, y: 10, text: My title}}]]}}]
multiplexer:
  filters:
    # A mapping of filters to give as the filter
    # keyword argument to the Multiplexer object.
    - - movingtext
      - t1: 1
        t2: 10
        fontsize: 19
        text: |
          This is an example of rolling credits
          starting at timestamp 1 and ending
          at timestamp 10.\
"""
#}}}


class YAMLReader():                              #{{{1

    """Reads YAML, checks the sanity of the data structure."""

    def __init__(self):
        self.data = None

    def _load(self, source):
        """Load YAML. No data validation is made at this point.

        Argument:
        source -- A YAML document as a string, a file pathname
                  or an open file object.
        """
        if isinstance(source, str) and os.path.isfile(source):
            # if source is a filename, read the corresponding file.
            with open(source) as file:
                data = yaml.load(file)
        else:
            # source may be str, bytes, or an open file in txt or bytes mode.
            data = yaml.load(source)
        return data

    def load(self, source):
        data = self._load(source)
        # Do checks.
        keys = self._check_root(data)
        sane_data = {}
        for key in keys:
            # Dynamically call check methods.
            sane_data[key] = getattr(self, "_check_"+key)(data[key])

        # All checks passed, set self.data.
        self.data = sane_data
        return self.data

    def _check_root(self, data):
        if not isinstance(data, dict):
            raise TypeError("The YAML document must be a mapping collection.")
        keys = set(data.keys())
        required_keys = {
            'movie',
            }
        optional_keys = {
            'multiplexer',
            'music',
            'meta',
            'globals',
            }
        allowed_keys = required_keys | optional_keys
        if not keys <= allowed_keys:
            unknown = keys - allowed_keys
            raise KeyError(
                "The following keys are not allowed: {}".format(unknown)
                )
        if not required_keys <= keys:
            missing = required_keys - keys
            raise KeyError(
                "The following keys are missing: {}".format(missing)
                )
        # Remove optional keys where value is None.
        # YAML example: "multiplexer: ~"
        for k in optional_keys & keys:
            if data[k] is None:
                keys.remove(k)
        return keys

    def _check_movie(self, data):
        """Check and canonicalize movie data.

        """
        if not isinstance(data, list):
            raise TypeError("The \"movie\" key must contain a list!")
        if len(data) == 0:
            raise ValueError("Movie has no shots in it!")
        shots = []
        index = 0
        for shot in data:
            index += 1
            where = ['movie', "shot #{}".format(index)]
            shots.append(self._check_shot(shot, where))
        return shots

    def _check_shot(self, data, where):
        """Check and canonicalize shot data.

        Movie data is passed as arguments to the Shot() constructor.

        Examples of valid shots in the movie mapping:
        - 42
        - [42]
        - [42, 4]
        - [42, 4, 2]
        - [42, 4, 2, {filters: […]}]

        Returns:
        A list of 1 to 3 ints plus a possibly empty dict.
        """
        error_msg = (
            "Invalid shot specification: {}\n"
            "Element {}.\n".format(data, self._format_where(where))
            )
        if not isinstance(data, (int, list)):
            reason = "Shot specification must be a list or an integer."
            raise TypeError(error_msg+reason)
        if isinstance(data, int):
            data = [data]
        if len(data) == 0:
            reason = "Shot specification is empty."
            raise ValueError(error_msg+reason)
        if isinstance(data[-1], dict):
            kwargs = data.pop()
            if 'filters' in kwargs:
                filters = []
                for f in kwargs['filters']:
                    filters.append(
                        self._check_filter(f, where)
                        )
                kwargs.update({'filters': filters})
        else:
            kwargs = {}
        if not 1 <= len(data) <= 3:
            reason = "Shot specification must provide 1 to 3 integers."
            raise ValueError(error_msg+reason)
        data.append(kwargs)
        return data

    def _check_multiplexer(self, data):
        """Check and canonicalize multiplexer data.

        For now, only the filters key is supported.
        """
        if data is None:
            return
        valid_keys = {'filters'}
        if not set(data) <= set(valid_keys):
            invalid_keys = set(data) - set(valid_keys)
            if len(invalid_keys) == 1:
                pluralize = "Key {} is invalid.".format(invalid_keys)
            else:
                pluralize = "Keys {} are invalid.".format(invalid_keys)
            raise KeyError(
                "Valid keys in multiplexer are: {}.\n".format(set(valid_keys))
                + pluralize
                )
        if 'filters' in data:
            if not isinstance(data['filters'], list):
                raise ValueError("Multiplexer filters must be a list.")
            sane_filters = []
            for filter in data['filters']:
                sane_filters.append(
                    self._check_filter(filter, ["multiplexer"])
                    )
            data['filters'] = sane_filters
        return data

    def _check_music(self, data):
        """Check and canonicalize music data.

        At this time, only a file name is accepted.
        """
        if data is None:
            return
        if not os.path.isfile(data):
            raise FileNotFoundError("Music file {} not found.".format(data))
        return data

    def _check_meta(self, data):
        """Meta is not used. Return data unchanged."""
        return data

    def _check_globals(self, data):
        """Check and canonicalize global kwargs.

        kwargs must be a subset of those accepted by the Shot constructor.
        globals is optional, therefore None is acceptable.
        """
        if data is None:
            return
        valid_keys = {
            'silent': bool,
            'filters': list,
            'pattern': str,
            }
        if not isinstance(data, dict):
            raise TypeError(
                "Globals must be a mapping. "
                "Valid keys are: {}".format(valid_keys)
                )
        if not set(data) <= set(valid_keys):
            invalid_keys = set(data) - set(valid_keys)
            if len(invalid_keys) == 1:
                pluralize = "Key {} is invalid.".format(invalid_keys)
            else:
                pluralize = "Keys {} are invalid.".format(invalid_keys)
            raise KeyError(
                "Valid keys in globals are: {}.\n".format(set(valid_keys))
                + pluralize
                )
        if 'filters' in data:
            if not isinstance(data['filters'], list):
                raise TypeError("Global filters must be a list.")
            sane_filters = []
            for filter in data['filters']:
                sane_filters.append(self._check_filter(filter, ["globals"]))
            data['filters'] = sane_filters
        if 'silent' in data and not isinstance(data['silent'], bool):
            raise TypeError("\"silent\" value in \"globals\" must be boolean.")
        if 'pattern' in data and not isinstance(data['pattern'], str):
            raise TypeError("\"pattern\" value in \"globals\" must be string.")
        return data

    def _check_filter(self, data, where):
        """Check and canonicalize filter specification.

        Arguments:
        data -- The filter specification to validate.
        where -- The location, increases error message value for the user.
                 It is a list of strings.

        Returns:
        [filtername, filterargs]
        where filtername is str and filterargs is dict.

        Here are valid data examples:
        - filtername  # A simple string.
        - [filtername]  # A list of 1 element, the filter name as str.
        - [filtername, {}]
        - [filtername, None]
        - [filtername, {key: value, …}]
            # where keys are str and values are str, int or float.
        """
        error_msg = (
            "Invalid filter: {}\n"
            "Specified in {}.\n".format(data, self._format_where(where))
            )
        if isinstance(data, str):
            # Data is simply a filter name.
            return [data, {}]
        if not isinstance(data, list) or len(data) > 2:
            reason = "Filter is not a list of maximum 2 items."
            raise ValueError(error_msg+reason)
        filtername = data[0]
        if not isinstance(filtername, str):
            reason = "Filter name is not a string."
            raise TypeError(error_msg+reason)
        if len(data) == 1:
            filterargs = {}
        elif len(data) == 2:
            filterargs = data[1]
            if filterargs is None:
                filterargs = {}
            elif not isinstance(filterargs, dict):
                reason = "Filter arguments is not a mapping."
                raise TypeError(error_msg+reason)
            for k, v in filterargs.items():
                if not isinstance(k, str):
                    reason = "Filter argument keys must be strings."
                    raise TypeError(error_msg+reason)
                if not isinstance(v, (str, int, float)):
                    reason = "Filter argument values must be strings, "
                    reason += "integers or floats."
                    raise TypeError(error_msg+reason)
        return [filtername, filterargs]

    def _format_where(self, where):
        return " > ".join(where)
