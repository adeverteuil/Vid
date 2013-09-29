.. -*- coding: utf-8 -*-

===
Vid
===

:Author: Alexandre de Verteuil
:Contact: claudelepoisson@gmail.com
:Date: 2013-09-13

Vid is a CLI video editor written in Python which uses ffmpeg in the
background. Because editing video in a terminal is bad-ass.

.. contents::

Overview
--------

The name was chosen to be typed quickly on the command line.

Goals
~~~~~

* Terminal interaction;
* As few dependencies_ as possible;
* Basic editing capabilities (concatenation, titles, music);
* Editing fast using a text editor;
* Learn about ffmpeg, codecs and formats;
* Advocate free (as in free speech) codecs and software.

.. _dependencies: Requirements_

Features
~~~~~~~~

* Projects are edited in YAML_ syntax with your editor of choice;
* Use the ``vid`` command to preview movie shots and write output to disk;
* Encode in Ogg/Theora/Vorbis or WebM/VP8/Vorbis;
* Mix in music;
* Preset FFMpeg filters to add text and rolling credits;
* No intermediary files; all processing is done in memory though streams, buffers and pipes.

.. _YAML: http://en.wikipedia.org/wiki/Yaml

Examples
~~~~~~~~

Some movies created with Vid are posted on `my blog`_.

.. _`my blog`: http://alexandre.deverteuil.net/blogue

Requirements
------------

* Python 3.x
* PyYAML 3.10
* FFMpeg

Setting the file name pattern
-----------------------------

Vid uses integers to find source video files. You should tell it where
to look by setting the file name pattern. The default pattern may be
overridden at these places, which are listed in descending priority
order:

* As the "pattern" key of a shot description in the "movie"
  section of the .yaml file;
* With the -p command line option;
* As the "pattern" variable of the "globals" section of the .yaml file;
* In a file named ".vid_pattern" in the current working directory;
* As the "VID_PATTERN" environment variable;
* The default.

The pattern is a `Python format string`_ which may include a ``{number}``
replacement field, shell globing characters ``*``, ``?`` and character ranges
expressed with ``[]``.

.. _`Python format string`: http://docs.python.org/3/library/string.html#format-string-syntax

The default is::

    footage/*/M2U{number:05d}.mpg

It matches my workflow and my camcorder's output file naming scheme.

* It does not start with "/", thus the path is relative to the current working directory.
* Look in subdirectories of the "``footage``" directory ("``footage/*/``").
* The filenames start with "``M2U``", followed by a zero-padded 5 digit
  number (format specified as "``:``" then "``05d``"), then the "``.mpg``"
  extension.

Workflow
--------

Here is my typical project directory structure.

::

    project A
    ├── movie.yaml
    └── footage
        ├── 2013-09-12
        │   ├── M2U00021.mpg
        │   └── M2U00022.mpg
        └── 2013-09-13
            └── M2U00023.mpg

Get started by typing ``vid new > movie.yaml``. This will write a YAML
template to ``movie.yaml`` with useful comments which should allow you to
start editing right away.

Here is what a simple movie.yaml may look like::

    movie:
        - [21, 4, 3]
        - [21, 10]
        - [23]

That's it! running ``vid yaml movie.yaml -o movie.ogv`` will concatenate
three sequences and write an Ogg/Theora/Vorbis encoded file to
movie.ogv. The first sequence ``[21, 4, 3]`` will take audio and video from
M2U00021.mpg at timestamp 00:00:04 for a duration of 3 seconds. The
second sequence will take video/audio from the same file starting at
timestamp 00:00:10 until the end of the file. The third sequence is the
entire M2U00023.mpg file.

Contact information
-------------------

:website: http://alexandre.deverteuil.net/
:email: claudelepoisson@gmail.com
:GitHub: https://github.com/adeverteuil/Vid

Copying
-------

Copyright © 2013  Alexandre de Verteuil

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public
License along with this program (see LICENSE.txt).  If not, see
<http://www.gnu.org/licenses/>.
