.. -*- coding: utf-8 -*-

===
Vid
===

------------------
A CLI video editor
------------------

.. For an example man page created with reStructuredText, see:
   http://docutils.sourceforge.net/sandbox/manpage-writer/rst2man.txt

:Date: 2013-09-28
:Manual section: 1

SYNOPSIS
========

``vid`` ``-h``

``vid`` ``play`` [``-h``] *file_number* [*seek*] [*duration*]
[``-o`` *OUTPUT* [``-o`` *OUTPUT*] ...]

``vid`` ``yaml`` [``-h``] *yaml_file* [``-b``] [``-s``]
[``-o`` *OUTPUT* [``-o`` *OUTPUT*] ...]

``vid`` ``new`` [``-h``]

DESCRIPTION
===========

Vid is a CLI video editor written in Python which uses ffmpeg in the
background. Because editing video in a terminal is bad-ass.

.. Todo
   This needs expansion.

OPTIONS
=======

The **vid** command expects a subcommand. Options available depends on
the subcommand given on the command line.

General options
---------------

--help, -h     Print usage text. May be used after a subcommand for a
               specific usage for this subcommand.

play
----

This subcommand requires a *file_number* argument. It will find the
required file by putting the file_number in the *pattern* (see PATTERN below)
and will play it with ffplay.

--output file, -o file    Write to *file* instead of piping to ffplay. The
                          file format is controlled the same way as with
                          the yaml subcommand (see below).

yaml
----

This subcommand requires a *yaml_file* argument. See the FILES section
below for a detailed description of this file's format.

--showinfo, -s   Show timecode information on the output video. For more
                 information, see ``movingtext`` in PRESET FILTERS.

--bell, -b       Produce an audible beep when encoding is finished.
                 This can be useful when encoding takes several minutes.

--output file, -o file
                 File name to write to. May be given many times. The
                 file extension determines the video format and
                 codecs. As of now, these presets are hard-coded in
                 the program, which is not the right thing to do. The
                 accepted extensions are avi, ogv, and webm.

new
---

Writes a YAML template to stdout. You may want to redirect output to a
file name. For example::

    $ vid new > movie.yaml

The template contains comments that will hopefully get you started
quickly. Consult the FILES section for a detailed description of the
YAML syntax specific to Vid.

ENVIRONMENT
===========

..
    lists all environment variables that affect the program or function and
    how they affect it.

FILES
=====

..
    lists the files the program or function uses, such as configuration
    files, startup files, and files the program directly operates on.  Give
    the full pathname of these files, and use the installation process to
    modify the directory part to match user preferences.  For many programs,
    the default instal‐ lation location is in /usr/local, so your base
    manual page should use /usr/local as the base.

Vid makes movies by reading a text file in YAML syntax and constructing
its internal objects from it. The YAML document must have a mapping at
its root. The accepted keys are listed below. Each values must follow
expected specifications which are also described.

meta
    Optional. Won't actually be used, but may be in a future version of
    Vid. For now, it may help you organize your files. The value of this key
    is not checked for sanity but the future-proof recommendation is to make it
    a mapping which keys are a subset of:

    :title:  a string
    :date:   a date, yyyy-mm-dd
    :author: a string

globals
    Optional. These keyword parameters will be passed to every shots in the
    movie unless overridden in a shot description in the movie section. The
    accepted keys are:

    :silent:  boolean; if ``true``, you get a silent movie (except for the music).
    :filters: list; the filters list format is described in the movie section.
    :pattern: string; one way to set the file name pattern.
              See the PATTERN section for details.

music
    Optional. A string. The file name of your movie's music track. The
    file must exist.

movie
    Required. A list of shots to concatenate.
    Examples of valid shot descriptions::

      - 42
      - [42]
      - [42, 4]
      - [42, 4, 2]
      - [42, 4, 2, {...}]

    If the item is an integer, it is taken as the number of the footage
    and the entire clip is used.

    If the item is a list, the first item must be an integer interpreted
    as the footage number. The if the second item is present and is a
    number (integer or float), it is used as the start position of the
    cut. The default is 0. If the third item is present and is a number,
    it is used as the duration of the cut. Otherwise, the frames from
    start to the end of file are used.

    The last item may be a mapping of the following keys:

    filters
        list. Here are valid syntax examples::

            - filtername       # A simple string.
            - [filtername]     # A list of 1 element, the filter name as str.
            - [filtername, {}]
            - [filtername, ~]  # ~ is null in YAML.
            - [filtername, {key: value, …}]
                # where keys are strings and values are strings,
                # integers or floating point numbers. Vid takes care of
                # properly escaping values passed to ffmpeg. Thus you
                # only need to worry about YAML syntax escaping.

        See ``man 1 ffmpeg-filters`` for details about ffmpeg filters.
        You can use any of them in vid. Vid also has preset filters hard-coded
        in the program. See PRESET FILTERS.

        Filters that do not take arguments, or those for which the
        defaults are fine for your needs, may be specified in one of the
        first 4 forms in the example above.

    silent
        boolean. Overrides the same key in the globals section.
    pattern
        string. the highest priority setting for the file path pattern.

multiplexer
    Optional. Options to pass to the multiplexer that affects the final
    movie. Currently, the only accepted key is ``filters`` described
    in the movie section.

PRESET FILTERS
==============

drawtext
--------

Vid overrides FFMpeg's defaults for the drawtext filter. The following parameters'
default values are modified:

:fontfile:  "/usr/share/fonts/TTF/ttf-inconsolata.otf". It is hard-coded in the
            program. This is wrong and should be changed in the future. The author
            finds this font pretty but it will be ignored if this file is not
            found on the user's system.
:fontcolor: "white"
:fontsize:  25
:boxcolor:  "0x000000aa". i.e. black with transparency. Note that it is
            not enabled unless the ``box`` argument is explicitely set to 1.

showdata
--------

When the ``-s`` option is passed to the ``yaml`` subcommand, or when the
``play`` command is used, this filter is added to all shots and to the
multiplexer.

It is also possible to add this filter in the YAML file, though it is
not the usual workflow

This filter does not take any arguments.

This filter is a preset for two sets of two drawtext filters:

1. Timecode and other data. There is a bottom left text and a top right text.

   The bottom left text shows information about the current shot in the movie:
   the source timecode in seconds, the frame number, and the file name.

   The top right text shows information about the output stream: the timecode
   in seconds and, when available, the total length.

2. A cursor (a chevron ">") indicating the current position in the
   sream. The cursor moves from the left border to the right border. There
   is one at the top of the frame and one at the bottom.

   The top cursor indicates the position in the output stream. It is
   very useful in ffplay because a mouse click in the frame seeks to the
   percentage in the file corresponding to the fraction of the width,
   and without this cursor, it's impossible to see what the current
   position is.

   The bottom cursor indicates the source position from each of the shots
   in the movie.

movingtext
----------

This is a preset for the drawtext filter which adds parameters to make drawing of
gliding text easy.

The new parameters and their default values are:

:x1: 20
:y1: "h"
:t1: 0
:x2: 20
:y2: "-text_h"
:t2: 3
:text: "undefined text"

These define a (x, y) position in 2D at timecodes t1 and t2. By default, text
crosses the frame from bottom to top from timecode 0 to 3 seconds.

The ``x`` and ``y`` parameters passed to the drawtext filter in FFMpeg
are the two-point form of the linear equation with the variables
substituted with the values defined above. It is also possible to assign
a constant to ``x`` and ``y``, in which case ``x1``, ``x2`` and ``y1``,
``y2`` will be ignored.

.. note::
   When the ``movingtext`` preset is used on a shot, timecodes are relative to
   the beginning of the original file, not the seek position of the cut. This is
   not a problem when ``movingtext`` is used in the ``multiplexer`` section.

   For example, if a shot is defined as such::

     - [42, 107, 40,
         {filters:
           [
             [movingtext, {t1: 0, t2: 10, text: Hi!}]
       ]}]

   ...the text would never be seen because the cut starts at timecode
   107 but the text exits the frame at timecode 10. The user should have
   assigned the values 107 and 117 to ``t1`` and ``t2`` respectively.

BUGS
====

.. TODO talk about how 100 ffmpeg subprocesses are spawned if the yaml
   file lists 50 clips
..
    lists limitations, known defects or inconveniences, and other
    questionable activities.
..
    Talk about the hard-coded values that should be configurable.

EXAMPLE
=======

..
    provides one or more examples describing how this function, file or
    command is used.  For details on writing example programs, see Example
    Programs below.

SEE ALSO
========

For examples of videos created with Vid, visit the author's blog at
<http://alexandre.deverteuil.net/blogue>.

The source code is available on GitHub at <http://github.com/adeverteuil/Vid>.

..
    provides a comma-separated list of related man pages, ordered by section
    number and then alphabetically by name, possibly followed by other
    related pages or documents.  Do not terminate this with a period.

..
    Where the SEE ALSO list contains many long manual page names, to improve
    the visual result of the output, it may be useful to employ the .ad l
    (don't right justify) and .nh (don't hyphenate) directives.  Hyphenation
    of individual page names can be prevented by preceding words with the
    string "\%".

TODO
====
    * Talk about the *pattern*.
    * Talk about the timecode with **play** and **yaml -s**.
    * Talk about the workflow.
