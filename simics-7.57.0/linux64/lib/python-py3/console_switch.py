# © 2025 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

import collections
import os
import sys
import simics
import conf
import cli

con_preview_name = "console-switch"
cli.add_tech_preview(con_preview_name)

cur_io_fd: int|None = None
cur_con_fd: int|None = None
IO_FD = collections.namedtuple('FD', ['obj', 'stdin', 'stdout'])
io_fds: list[IO_FD] = []

__all__ = [
    "switch_io_fd",
    "add_io_fd",
    "get_cur_con",
    "remove_io_fd",
    "set_cur_con",
]

def find_io_fd(obj):
    assert obj is not None
    idx = [i for i in range(len(io_fds)) if io_fds[i].obj == obj]
    return idx[0] if len(idx) == 1 else None

def get_cur_con():
    return io_fds[cur_con_fd].obj if cur_con_fd is not None else None

def set_cur_con(obj):
    global cur_con_fd
    if obj is not None:
        idx = find_io_fd(obj)
        if idx is not None:
            cur_con_fd = idx
            return cur_con_fd
    else:
        cur_con_fd = None
    return None

def add_io_fd(obj, stdin, stdout):
    io_fds.append(IO_FD(obj, stdin, stdout))
    # TODO Maybe not always set last added as current?
    set_cur_con(obj)

def remove_io_fd(obj):
    global cur_con_fd
    idx = find_io_fd(obj)
    assert idx is not None
    if cur_io_fd == idx:
        switch_io_fd()
    if cur_con_fd == idx:
        cur_con_fd = None
    io_fds.pop(idx)

def io_fd_read(fd):
    # read fd and print to stdout
    s = os.read(fd, 1024)
    if s:
        # Use sys.__stdout__ to avoid Simics "output handlers"
        sys.__stdout__.buffer.write(s)
        sys.__stdout__.flush()

def io_fd_write(fd):
    # read stdin and print to fd
    s = os.read(0, 1)
    if s:
        # Ctrl+g
        if s[0] == 7:
            switch_io_fd()
        os.write(fd, s)

def switch_io_fd():
    import command_line
    global cur_io_fd
    if not cli.tech_preview_enabled(con_preview_name):
        return

    # No target consoles?
    if not io_fds:
        return

    # No selected target console?
    if cur_con_fd is None:
        return

    if cur_io_fd is None:
        # Switch from CLI to target console

        # Turn off CLI terminal frontend
        conf.sim.cmdline.term.object_data.enable_output = False

        # Reset screen to current console contents
        sys.__stdout__.buffer.write(
            bytes(io_fds[cur_con_fd].obj.screen_reset_data))
        sys.__stdout__.flush()

        # Redirect stdin to PTY
        simics.SIM_notify_on_descriptor(0, simics.Sim_NM_Read, 0, io_fd_write,
                                        io_fds[cur_con_fd].stdout)
        # Redirect PTY to stdout
        simics.SIM_notify_on_descriptor(io_fds[cur_con_fd].stdin,
                                        simics.Sim_NM_Read, 0, io_fd_read,
                                        io_fds[cur_con_fd].stdin)
        cur_io_fd = cur_con_fd
    else:
        # Switch from target console to CLI

        # Turn off current I/O redirection
        simics.SIM_notify_on_descriptor(io_fds[cur_con_fd].stdin,
                                        simics.Sim_NM_Read, 0, None, None)
        # Turn on CLI terminal frontend
        conf.sim.cmdline.term.object_data.enable_output = True
        conf.sim.cmdline.object_data.start_input(conf.sim.cmdline)
        command_line.command_line_reset_io(cli.get_primary_cmdline().get_id())
        cur_io_fd = None
