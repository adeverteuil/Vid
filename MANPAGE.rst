.. -*- coding: utf-8 -*-

===
VID
===

NAME
====

Vid - a CLI video editor

SYNOPSIS
========

briefly describes the command or function's interface.  For commands,
this shows the syntax of the command and its arguments (including
options); bold‐ face is used for as-is text and italics are used
to indicate replaceable arguments.  Brackets ([]) surround optional
arguments, vertical bars (|) sepa‐ rate choices, and ellipses (...)
can be repeated.  For functions, it shows any required data declarations
or #include directives, followed by the func‐ tion declaration.

DESCRIPTION
===========

gives an explanation of what the program, function, or format does.
Discuss how it interacts with files and standard input, and what it
produces on standard output or standard error.  Omit internals and
implementation details unless they're critical for understanding the
interface.  Describe the usual case; for information on command-line
options of a program use the OPTIONS section.

When describing new behavior or new flags for a system call or library
function, be careful to note the kernel or C library version that
introduced the change.  The preferred method of noting this information
for flags is as part of a .TP list, in the following form (here, for a
new system call flag):

        XYZ_FLAG (since Linux 3.7)
                       Description of flag...

Including version information is especially useful to users who are
constrained to using older kernel or C library versions (which is
typical in embed‐ ded systems, for example).

OPTIONS
=======

describes the command-line options accepted by a program and how they
change its behavior.  This section should appear only for Section 1 and
8 manual pages.

ENVIRONMENT
===========

lists all environment variables that affect the program or function and
how they affect it.

FILES
=====

lists the files the program or function uses, such as configuration
files, startup files, and files the program directly operates on.  Give
the full pathname of these files, and use the installation process to
modify the directory part to match user preferences.  For many programs,
the default instal‐ lation location is in /usr/local, so your base
manual page should use /usr/local as the base.

BUGS
====

lists limitations, known defects or inconveniences, and other
questionable activities.

EXAMPLE
=======

provides one or more examples describing how this function, file or
command is used.  For details on writing example programs, see Example
Programs below.

AUTHORS
=======

lists authors of the documentation or program.  Use of an AUTHORS
section is strongly discouraged.  Generally, it is better not to clutter
every page with a list of (over time potentially numerous) authors; if
you write or significantly amend a page, add a copyright notice as a
comment in the source file.  If you are the author of a device driver
and want to include an address for reporting bugs, place this under the
BUGS section.

SEE ALSO
========

provides a comma-separated list of related man pages, ordered by section
number and then alphabetically by name, possibly followed by other
related pages or documents.  Do not terminate this with a period.

Where the SEE ALSO list contains many long manual page names, to improve
the visual result of the output, it may be useful to employ the .ad l
(don't right justify) and .nh (don't hyphenate) directives.  Hyphenation
of individual page names can be prevented by preceding words with the
string "\%".
