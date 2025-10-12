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
    new_command,
    new_info_command,
    new_status_command,
)

def tsync_info(obj):
    return [ (None,
              [("Description", "Trace Synchronizer (Core2 hardware bug workaround)"),
               ("CPU",         "%s" % (obj.cpu.name)),
               ("Trace Length", "%d" % (obj.trace_length)),
               ("Trace Period", "%d" % (obj.trace_period)),
               ("Enabled",     "%s" % ("Yes" if obj.enabled else "No"))])]


def tsync_status(obj):
    v = [("Matches",     "%d" % (obj.matches)),
             ("Mismatches",  "%d" % (obj.mismatches)),
             ("Corrections", "%d" % (obj.corrections)),
             ("Recent Mismatches",  "%d" % (obj.recent_mismatches)),
             ("Enabled",     "%s" % ("Yes" if obj.enabled else "No"))]
    return [ (None, v) ]

def tsync_enable_cmd(obj):
    obj.enabled = 1

def tsync_disable_cmd(obj):
    obj.enabled = 0


new_info_command("trace-sync", tsync_info)
new_status_command("trace-sync", tsync_status)
new_command("enable", tsync_enable_cmd,
            type  = ["Tracing"],
            short = "enable core2 hardware bug workaround",
            cls = "trace-sync",
            doc = """
            Enables trace synchronization.<br/>
            This module provides a workaround for a hardware determinism problem
            present in certain Core2 Duo processors.
            """)

new_command("disable", tsync_disable_cmd,
            type  = ["Tracing"],
            short = "disable core2 hardware bug workaround",
            cls = "trace-sync",
            doc_with = "<trace-sync>.enable")
