# © 2021 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import cli
import conf
import simics

common_doc = """
If the <arg>number</arg> parameter is specified, only magic
instructions with that argument value are considered. The possible
argument values depends on the processor type. To consider all magic
instructions, the <tt>-all</tt> flag can be used. The default is to
consider magic instructions with argument 0.

If no processor object is specified, magic instructions from all
processors are considered.

See further about magic breakpoints in <cite>Simics User's Guide</cite>.
"""

break_doc = """
Enables breaking the simulation on magic instructions.
""" + common_doc

run_until_doc = """
Run the simulation until the specified magic instruction occurs.
""" + common_doc

wait_for_doc = """
Postpones execution of a script branch until the specified
magic instruction occurs.
""" + common_doc

trace_doc = """
Enables tracing of magic instruction. When this
is enabled, every time the specified magic instruction occurs
during simulation, a message is printed.
""" + common_doc

class Breakpoint:
    __slots__ = ('cpu', 'hap_id', 'magic_nr', 'once', 'last_cpu', 'last_nr')
    def __init__(self, cpu, hap_id, magic_nr, once):
        self.cpu = cpu
        self.hap_id = hap_id
        self.magic_nr = magic_nr
        self.once = once
        self.last_cpu = None
        self.last_nr = None

    def __str__(self):
        return "magic instruction "

    def desc(self):
        return (f"{self}" + (f"({self.magic_nr})"
                             if self.magic_nr != -1 else "(any)")
                + " on " + (f"{self.cpu.name}"
                            if self.cpu else "any processor"))

    def msg(self):
        return f"{self}({self.last_nr})"

class MagicBreakpoints:
    TYPE_DESC = "magic breakpoints"
    HAP_NAME = "Core_Magic_Instruction"
    cls = simics.confclass("bp-manager.magic", doc=TYPE_DESC,
                           short_doc=TYPE_DESC, pseudo=True)

    def __init__(self):
        self.bp_data = {}
        self.next_id = 1

    @cls.objects_finalized
    def objects_finalized(self):
        conf.bp.iface.breakpoint_type.register_type(
            "magic", self.obj,
            [[["uint_t", "flag_t"], ["number", "-all"],
              '?', None, None, "", [None, None]]],
            None, 'processor_internal', [
                "set magic instruction break", break_doc,
                "run until specified magic instruction occurs", run_until_doc,
                "wait for specified magic instruction", wait_for_doc,
                "enable tracing of magic instructions", trace_doc],
            False, False, False)

    def _delete_bp(self, _, bm_id):
        self.remove_bp(conf.bp.iface.breakpoint_type.get_break_id(bm_id))

    def _describe_bp(self, bp_id):
        bp = self.bp_data[bp_id]
        return f"break on {bp.desc()}"

    def _get_props(self, _, bm_id):
        bp_id = conf.bp.iface.breakpoint_type.get_break_id(bm_id)
        bp = self.bp_data[bp_id]
        return {"temporary": bp.once,
                "planted": True,
                "object": bp.cpu.name if bp.cpu else None,
                "description": self._describe_bp(bp_id)}

    def _create_bp(self, cpu, arg, once):
        bp_id = self.next_id
        self.next_id += 1

        if arg:
            assert arg[0] in {"uint_t", "flag_t"}
            if arg[0] == "uint_t":
                magic_nr = arg[1]
            else:
                magic_nr = -1
        else:
            # Default is magic break on 0
            magic_nr = 0

        # Set breakpoint on all CPUs, unless one is specified
        # This is similar to the old enable-magic-breakpoint
        if magic_nr != -1:
            if cpu:
                hap_id = simics.SIM_hap_add_callback_obj_index(
                    self.HAP_NAME, cpu, 0, self._bp_cb, bp_id, magic_nr)
            else:
                hap_id = simics.SIM_hap_add_callback_index(
                    self.HAP_NAME, self._bp_cb, bp_id, magic_nr)
        else:
            if cpu:
                hap_id = simics.SIM_hap_add_callback_obj(
                    self.HAP_NAME, cpu, 0, self._bp_cb, bp_id)
            else:
                hap_id = simics.SIM_hap_add_callback(
                    self.HAP_NAME, self._bp_cb, bp_id)

        self.bp_data[bp_id] = Breakpoint(cpu, hap_id, magic_nr, once)
        return bp_id

    def _bp_cb(self, bp_id, cpu, magic_nr):
        bp = self.bp_data[bp_id]
        bp.last_cpu = cpu
        bp.last_nr = magic_nr
        conf.bp.iface.breakpoint_type.trigger(self.obj, bp_id, bp.cpu,
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
        (cpu, arg, once) = args
        return self._create_bp(cpu, arg, once)

    @cls.iface.breakpoint_type_provider.remove_bp
    def remove_bp(self, bp_id):
        bp = self.bp_data[bp_id]
        if bp.cpu:
            simics.SIM_hap_delete_callback_obj_id(self.HAP_NAME, bp.cpu,
                                                  bp.hap_id)
        else:
            simics.SIM_hap_delete_callback_id(self.HAP_NAME, bp.hap_id)
        del self.bp_data[bp_id]

    @cls.iface.breakpoint_type_provider.trace_msg
    def trace_msg(self, bp_id):
        bp = self.bp_data[bp_id]
        return f"{bp.msg()}"

    @cls.iface.breakpoint_type_provider.break_msg
    def break_msg(self, bp_id):
        bp = self.bp_data[bp_id]
        return f"Will break on {bp.desc()}"

    @cls.iface.breakpoint_type_provider.wait_msg
    def wait_msg(self, bp_id):
        bp = self.bp_data[bp_id]
        return f"Waiting on {bp.desc()}"

def register_magic_breakpoints(bpm_class):
    simics.SIM_register_port(bpm_class, "magic",
                             MagicBreakpoints.cls.classname,
                             MagicBreakpoints.TYPE_DESC)
