# © 2014 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


from cli import (
    CliError,
    arg,
    command_return,
    flag_t,
    new_command,
    str_t,
)
from simics import *

def get_magic_pipe():
    all_objs = list(SIM_object_iterator_for_class("magic_pipe"))
    if not all_objs:
        return None
    return all_objs[0]  # There can be only one

def ok_msg(name, created):
    if not created:
        return "Magic Pipe '%s' is already started." % name
    return "'%s' is created and enabled." % name

def new_magic_pipe_cmd(name, arch32):
    created = False
    pipe = get_magic_pipe()
    if not pipe:
        if not name:
            name = "magic_pipe"
        try:
            pipe = SIM_create_object("magic_pipe", name, [["arch32", arch32]])
        except SimExc_General as e:
            raise CliError(str(e))
        created = True
    elif name and pipe.name != name:
        raise CliError("A magic pipe called '%s' already exists and it cannot"
                       " be renamed." % pipe.name)
    return command_return(value=pipe,
                          message=ok_msg(pipe.name, created))

new_command("start-magic-pipe", new_magic_pipe_cmd,
            [arg(str_t, "name", "?", ""),
             arg(flag_t, "-arch32")],
            type = ["Matic"],
            short = "create and enable a Magic communication pipe",
            doc = """
    Create and enable a Simics Magic communication pipe for <i>Magic</i>. Only
    <i>one</i> magic pipe can exist in the simulation.

    The <arg>name</arg> argument is optional and defaults to
    'magic_pipe'.

    The <tt>-arch32</tt> flag is optional and defaults to false. It is useful
    in the case of 32-bit userspace applications running on 64-bit architecture.
    This flag affects the entire simulation.

    <b>See also:</b> The <nref label="__rm_class_magic_pipe">
    magic_pipe</nref> class.""")
