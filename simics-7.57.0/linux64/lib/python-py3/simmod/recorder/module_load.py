# © 2010 Intel Corporation
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
    filename_t,
    new_command,
    new_info_command,
    new_status_command,
    )
from simics import *

#
# -------------------- info, status --------------------
#

def get_info(obj):
    return []

new_info_command("recorder", get_info)

def get_status(obj):
    if obj.recording:
        rec = "yes (file: %s)" % obj.out_file
    else:
        rec = "no"
    if obj.playback:
        play = "yes (file: %s)" % obj.in_file
    else:
        play = "no"
    return [(None,
             [("Recording", rec),
              ("Playing back", play)])]

new_status_command("recorder", get_status)

#
# -------------------- playback-start --------------------
#

def playback_start_cmd(obj, filename):
    try:
        obj.in_file = filename
        obj.playback = True
        print("Playback from input file %s" % filename)
    except Exception as msg:
        raise CliError("Error starting playback: %s" % msg)

new_command("playback-start", playback_start_cmd,
            [arg(filename_t(exist = 1), "input-file")],
            type  = ["Recording"],
            short = "play back recorded asynchronous input",
            cls = "recorder",
            see_also = ["<recorder>.playback-stop"],
            doc = """
Starts playback of a recording from specified file <arg>input-file</arg>.
The input events in the file that is to be played back must have been recorded
using a machine configuration identical to the current one. It is highly
recommended that console input is blocked during play back, or the
session may lose its synchronization.
""")

#
# -------------------- playback-stop --------------------
#

def playback_stop_cmd(obj):
    try:
        obj.playback = False
    except Exception as msg:
        raise CliError("%s" % msg)


new_command("playback-stop", playback_stop_cmd,
            [],
            type  = ["Recording"],
            short = "stop playback",
            cls = "recorder",
            see_also = ["<recorder>.playback-start"],
            doc = """
Stop the playback of asynchronous data from a file. Once playback has been
stopped in cannot be restarted.
""")

#
# -------------------- recorder-start --------------------
#

def recorder_start_cmd(obj, filename):
    try:
        obj.out_file = filename
        obj.recording = True
        print("Recording to output file %s" % filename)
    except Exception as msg:
        raise CliError("Error starting recording: %s" % msg)

new_command("recorder-start", recorder_start_cmd,
            [arg(filename_t(exist = 0), "output-file")],
            type  = ["Recording"],
            short = "record asynchronous input to file",
            cls = "recorder",
            see_also = ["start-recording", "<recorder>.recorder-stop"],
            doc = """
Record asynchronous input to specified file <arg>output-file</arg>. The
input is recorded fom all modules that are recording aware, typically consoles
and other connections to the real world, and that use this recorder, typically
there is one recorder per cell.

After the recording is started input events will be written to
<arg>output-file</arg> until <cmd class="recorder">recorder-stop</cmd>.

This is a command for a single recorder. To record input for the
entire simulation use <cmd>start-recording</cmd> instead. You can not have
more than one recording running at the same time. This includes recordings
started by <cmd class="recorder">recorder-start</cmd> and recordings
started with <cmd>start-recording</cmd>.
""")

#
# -------------------- recorder-stop --------------------
#

def recorder_stop_cmd(obj):
    try:
        obj.recording = False
    except Exception as msg:
        raise CliError("%s" % msg)

new_command("recorder-stop", recorder_stop_cmd,
            [],
            type  = ["Recording"],
            short = "stop recorder",
            cls = "recorder",
            see_also = ["<recorder>.recorder-start", "stop-recording"],
            doc = """
Stop the recording of asynchronous input.

This turns off the recording for this recorder. This affects both recordings
started with <cmd class="recorder">recorder-start</cmd> and recordings started
with <cmd>start-recording</cmd>. You should not use this command
together with <cmd>start-recording</cmd>.
""")
