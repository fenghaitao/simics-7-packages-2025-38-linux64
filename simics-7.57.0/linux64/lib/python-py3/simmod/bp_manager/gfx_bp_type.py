# © 2020 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

import sys
import conf
import simics

common_doc = """
A graphical breakpoint matches when its image appears
on the screen, in the same location as when it was saved. The
breakpoint must have been created using the Simics GUI or the command
<cmd class="graphcon">save-break-xy</cmd>. The screen is checked for
matches every <arg>interval</arg> seconds of host time, or in virtual
on the clock associated to the console, if the attribute
<tt>refresh_in_virtual_time</tt> is set on the console."""

break_doc = """
Set Simics to break simulation when the graphical breakpoint
defined by <arg>filename</arg> matches.
""" + common_doc

wait_for_doc = """
Postpones execution of a script branch until the graphical
breakpoint defined by <arg>filename</arg> matches.
""" + common_doc

run_until_doc = """
Run the simulation until the graphical breakpoint defined by
<arg>filename</arg> matches.
""" + common_doc

trace_doc = """
Enable tracing of matches of the graphical breakpoint defined by
<arg>filename</arg>.
""" + common_doc

class Breakpoint:
    __slots__ = ('con', 'con_id', 'filename', 'once')
    def __init__(self, con, con_id, filename, once):
        self.con = con
        self.con_id = con_id
        self.filename = filename
        self.once = once

class ConGfxBreakpoints:
    TYPE_DESC = "graphics console output breakpoints"
    cls = simics.confclass("bp-manager.con-gfx", doc=TYPE_DESC,
                           short_doc=TYPE_DESC, pseudo=True)

    def __init__(self):
        self.bp_data = {}
        self.next_id = 1

    @cls.objects_finalized
    def objects_finalized(self):
        conf.bp.iface.breakpoint_type.register_type(
            "gfx", self.obj,
            [[["filename_t", False, True, False, False, False],
              "filename", "1", None, None, "", None],
             ["float_t", "interval", "1", None, None, "", None]],
            None, 'gfx_break',
            ["set graphical breakpoint", break_doc,
             "run until graphical break matches", run_until_doc,
             "wait for graphical match", wait_for_doc,
             "enable tracing of graphical matches", trace_doc], True, False,
            False)

    def _delete_bp(self, _, bm_id):
        self.remove_bp(conf.bp.iface.breakpoint_type.get_break_id(bm_id))

    def _describe_bp(self, bp_id):
        bp = self.bp_data[bp_id]
        return f"Console '{bp.con.name}' graphical break on '{bp.filename}'"

    def _get_props(self, _, bm_id):
        bp_id = conf.bp.iface.breakpoint_type.get_break_id(bm_id)
        bp = self.bp_data[bp_id]
        return {"temporary": bp.once,
                "planted": True,
                "object": bp.con.name,
                "description": self._describe_bp(bp_id)}

    def _create_bp(self, con, filename, interval, once, cb):
        bp_id = self.next_id
        self.next_id += 1

        if interval <= 0:
            print("interval argument must be positive", file=sys.stderr)
            return 0

        # We don't expose the breakpoint "name", use empty string
        con_id = con.iface.gfx_break.add(filename, "", once, interval,
                                         cb, bp_id)
        self.bp_data[bp_id] = Breakpoint(con, con_id, filename, once)
        return bp_id

    def _bp_cb(self, con, con_id, bp_id):
        conf.bp.iface.breakpoint_type.trigger(self.obj, bp_id, con,
                                              self.trace_msg(bp_id))
        return 1

    @cls.iface.breakpoint_type_provider.register_bp
    def register_bp(self, bp_id):
        bpm_iface = conf.bp.iface.breakpoint_registration
        return bpm_iface.register_breakpoint(
            self._delete_bp, None, self._get_props, None, None, None,
            None, None, None, None)

    @cls.iface.breakpoint_type_provider.add_bp
    def add_bp(self, _, args):
        (con, filename, interval, once) = args
        return self._create_bp(con, filename, interval, once, self._bp_cb)

    @cls.iface.breakpoint_type_provider.remove_bp
    def remove_bp(self, bp_id):
        bp = self.bp_data[bp_id]
        if isinstance(bp.con, simics.conf_object_t):
            bp.con.iface.gfx_break.remove(bp.con_id)
        del self.bp_data[bp_id]

    @cls.iface.breakpoint_type_provider.trace_msg
    def trace_msg(self, bp_id):
        bp = self.bp_data[bp_id]
        return f"{bp.con.name} graphically matched '{bp.filename}'"

    @cls.iface.breakpoint_type_provider.break_msg
    def break_msg(self, bp_id):
        bp = self.bp_data[bp_id]
        return f"{bp.con.name} will break on graphical match of '{bp.filename}'"

    @cls.iface.breakpoint_type_provider.wait_msg
    def wait_msg(self, bp_id):
        bp = self.bp_data[bp_id]
        return f"{bp.con.name} waiting on graphical match of '{bp.filename}'"

def register_gfx_breakpoints(bpm_class):
    simics.SIM_register_port(bpm_class, "gfx",
                             ConGfxBreakpoints.cls.classname,
                             ConGfxBreakpoints.TYPE_DESC)
