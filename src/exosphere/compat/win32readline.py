# -*- coding: UTF-8 -*-
# This file has been modified from the original pyreadline3 package as a
# compatibility shim for the Python readline module on Windows systems.
#
# It provides a reasonably consistent 'readline' interface for rlcompleter
# to allow for the REPL component of exosphere to use readline features
# off pyreadline3, without requiring library support for click_shell or similar.

# pyreadline3 is released under a BSD-type license.
#
# Copyright (c) 2020 Bassem Girgis <brgirgis@gmail.com>.
# Copyright (c) 2006-2020 Jorgen Stenarson <jorgen.stenarson@bostream.nu>.
# Copyright (c) 2003-2006 Gary Bishop
# Copyright (c) 2003-2006 Jack Trainor
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# a. Redistributions of source code must retain the above copyright notice,
#      this list of conditions and the following disclaimer.
#
# b. Redistributions in binary form must reproduce the above copyright
#      notice, this list of conditions and the following disclaimer in the
#      documentation and/or other materials provided with the distribution.
#
# c. Neither the name of the copyright holders nor the names of any
#      contributors to this software may be used to endorse or promote products
#      derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE REGENTS OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
# OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH
# DAMAGE.

import sys
from typing import TYPE_CHECKING

if sys.platform == "win32" or TYPE_CHECKING:
    from pyreadline3.rlmain import Readline  # type: ignore[import]

__all__ = [
    "parse_and_bind",
    "get_line_buffer",
    "insert_text",
    "clear_history",
    "read_init_file",
    "read_history_file",
    "write_history_file",
    "get_current_history_length",
    "get_history_length",
    "get_history_item",
    "set_history_length",
    "set_startup_hook",
    "set_pre_input_hook",
    "set_completer",
    "get_completer",
    "get_begidx",
    "get_endidx",
    "set_completer_delims",
    "get_completer_delims",
    "add_history",
    "callback_handler_install",
    "callback_handler_remove",
    "callback_read_char",
    "redisplay",
]  # Some other objects are added below


# create a Readline object to contain the state
rl = Readline()

if rl.disable_readline:

    def dummy(completer=""):
        pass

    for funk in __all__:
        globals()[funk] = dummy
else:

    def GetOutputFile():
        """Return the console object used by readline so that it can be
        used for printing in color."""
        return rl.console

    __all__.append("GetOutputFile")

    import pyreadline3.console as console  # type: ignore[import]

    # make these available so this looks like the python readline module
    read_init_file = rl.read_init_file
    parse_and_bind = rl.parse_and_bind
    clear_history = rl.clear_history
    add_history = rl.add_history
    insert_text = rl.insert_text

    write_history_file = rl.write_history_file
    read_history_file = rl.read_history_file

    get_completer_delims = rl.get_completer_delims
    get_current_history_length = rl.get_current_history_length
    get_history_length = rl.get_history_length
    get_history_item = rl.get_history_item
    get_line_buffer = rl.get_line_buffer
    set_completer = rl.set_completer
    get_completer = rl.get_completer
    get_begidx = rl.get_begidx
    get_endidx = rl.get_endidx

    set_completer_delims = rl.set_completer_delims
    set_history_length = rl.set_history_length
    set_pre_input_hook = rl.set_pre_input_hook
    set_startup_hook = rl.set_startup_hook

    callback_handler_install = rl.callback_handler_install
    callback_handler_remove = rl.callback_handler_remove
    callback_read_char = rl.callback_read_char

    redisplay = rl.redisplay

    console.install_readline(rl.readline)

__all__.append("rl")
__doc__ = "Importing this module enables command line editing using pyreadline3 for Windows systems"
# type: ignore
