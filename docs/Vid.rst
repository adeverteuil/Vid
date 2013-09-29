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

``vid`` ``play`` [``-h``] [``-o`` *OUTPUT*] *file_number* [*seek*] [*duration*]

``vid`` ``yaml`` [``-h``] *yaml_file* [``-b``] [``-s``] [``-o`` *OUTPUT* [``-o`` *OUTPUT*] ...]

``vid`` ``new`` [``-h``]

DESCRIPTION
===========

Vid is a CLI video editor written in Python which uses ffmpeg in the background. Because editing video in a terminal is bad-ass.

.. TODO
..
    The following is a reference for the author and will be removed.

..  gives an explanation of what the program, function, or format does.
    Discuss how it interacts with files and standard input, and what it
    produces on standard output or standard error.  Omit internals and
    implementation details unless they're critical for understanding the
    interface.  Describe the usual case; for information on command-line
    options of a program use the OPTIONS section.

..  When describing new behavior or new flags for a system call or library
    function, be careful to note the kernel or C library version that
    introduced the change.  The preferred method of noting this information
    for flags is as part of a .TP list, in the following form (here, for a
    new system call flag):

..
        XYZ_FLAG (since Linux 3.7)
                       Description of flag...
..
    Including version information is especially useful to users who are
    constrained to using older kernel or C library versions (which is
    typical in embed‐ ded systems, for example).

OPTIONS
=======

The **vid** command expects a subcommand. Options available depends on the subcommand given on the command line.

.. TODO
..
    describes the command-line options accepted by a program and how they
    change its behavior.  This section should appear only for Section 1 and
    8 manual pages.

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

--showinfo, -s   Show timecode information on the output video.

--bell, -b       Produce an audible beep when encoding is finished. This can be
                 useful when encoding takes several minutes.

--output file, -o file
                 File name to write to. May be given many times. The file
                 extension determines the video format and codecs. As of now,
                 these presets are hard-coded in the program, which is not the
                 right thing to do. The accepted extensions are avi, ogv, and webm.

new
---

Writes a YAML template to stdout. You may want to redirect output to a file name. For example::

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

Vid makes movies by reading a text file in YAML syntax and constructing
its internal objects from it. The YAML document must have a mapping at
its root. The accepted keys are listed below. Each values must follow
expected specifications which are also described.

meta
    Optional. Won't actually be used, but may be in a future version of
    Vid. For now, it may help you organize your files. The value of this key
    is not checked for sanity but the future-proof recommendation is to make it
    a mapping which keys are a subset of:

    :title: a string
    :date: a date, yyyy-mm-dd
    :author: a string

globals
    Optional. These keyword parameters will be passed to every shots in the
    movie unless overridden in a shot description in the movie section. The
    accepted keys are:

    :silent: boolean; if ``true``, you get a silent movie (except for the music).
    :filters: list; the filters list format is described in the movie section.
    :pattern: string; one way to set the file name pattern.
              See the PATTERN section for details.

music
    Optional. A string. The file name of your movie's music track. The file must exist.

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
    start to the end of file are used. The last item may be a mapping of
    the following keys:

    filters
        list. Here are valid syntax examples::

            - filtername       # A simple string.
            - [filtername]     # A list of 1 element, the filter name as str.
            - [filtername, {}]
            - [filtername, ~]  # ~ is null in YAML.
            - [filtername, {key: value, …}]
                # where keys are strings and
                # values are strings, integers or floating point numbers.
                # Values are properly escaped before being passed to ffmpeg.
                # You only need to do YAML syntax escaping.
        see ``man 1 ffmpeg-filters`` for details about ffmpeg filters.
        you can use any of them in vid. Vid also has preset filters hard-coded
        in the program.

.. TODO
   This is not finished.

    silent
        boolean. Overrides the same key in the globals section.
    pattern
        string. the highest priority setting for the file path pattern.

multiplexer
    Optional. Options to pass to the multiplexer that will output the final
    movie. Currently, the only accepted key is ``filters`` in the same way
    as shots in the movie section.

..
    lists the files the program or function uses, such as configuration
    files, startup files, and files the program directly operates on.  Give
    the full pathname of these files, and use the installation process to
    modify the directory part to match user preferences.  For many programs,
    the default instal‐ lation location is in /usr/local, so your base
    manual page should use /usr/local as the base.

BUGS
====

.. TODO talk about how 100 ffmpeg subprocesses are spawned if the yaml
   file lists 50 clips
..
    lists limitations, known defects or inconveniences, and other
    questionable activities.

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
