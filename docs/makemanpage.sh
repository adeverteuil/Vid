#!/usr/bin/bash

[ -d man1 ] || mkdir man1
rst2man --strip-comments Vid.rst man1/vid.1; man -M ./ vid
