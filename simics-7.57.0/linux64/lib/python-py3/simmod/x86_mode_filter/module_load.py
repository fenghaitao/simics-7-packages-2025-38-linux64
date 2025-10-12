# © 2017 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.


import simics
import pyobj
from . import modes
import cli

# Get hold of the current execution mode for a processor
def _current_mode(cpu):
    mode = cpu.iface.x86_reg_access.get_exec_mode()
    if mode == simics.X86_Exec_Mode_Real:
        return "RealMode32" if cpu.cs[1] else "RealMode16"
    elif mode == simics.X86_Exec_Mode_V86:
        return "Virtual86"
    elif mode == simics.X86_Exec_Mode_Prot:
        return "ProtectedMode32" if cpu.cs[1] else "ProtectedMode16"
    elif mode == simics.X86_Exec_Mode_Compat:
        return "CompatibilityMode32" if cpu.cs[1] else "CompatibilityMode16"
    elif mode == simics.X86_Exec_Mode_64:
        return "ProtectedMode64"
    else:
        assert(0)

class x86_mode_filter(pyobj.ConfObject):
    __slots__ = ("_destinations", "_slaves", "_modes", "_source_id", "_handles")

    __doc__ = """Objects of this class are used to filter an instrumentation
    tool's data collection according to x86 execution modes."""

    _class_desc = "filter for exec modes"

    def _pre_delete(self):
        # Enable all slave-connections, remove callbacks and free the slaves!
        l = list(self._slaves.items())
        for cpu, slaves in l:
            for s in slaves.copy():
                self.instrumentation_filter_master.remove_slave(s, cpu)
        super()._pre_delete()

    def _initialize(self):
        super()._initialize()
        self._slaves = {}       # {cpu : set(slave_objects) }
        self._handles = []      # [(cpu, mode callback_handle)]
        self._modes = set()     # modes enabled


    def drive_connections(self, mode, cpu):
        if not cpu in self._slaves:
            return   # We are not monitoring this cpu

        slaves = self._slaves[cpu]
        if mode in self._modes:
            for s in slaves:
                iface = s.iface.instrumentation_filter_slave
                iface.enable(self._source_id)
        else:
            for s in slaves:
                iface = s.iface.instrumentation_filter_slave
                iface.disable(self._source_id)

    def x86_mode_switch_cb(self, obj, cpu, mode_val, user_data):
        current_mode = modes.x86_modes[mode_val]
        self.drive_connections(current_mode, cpu)

    def update(self):
        for cpu in self._slaves:
            cm = _current_mode(cpu)
            self.drive_connections(cm, cpu)

    def add_mode(self, mode):
        self._modes.add(mode)
        self.update()

    def remove_mode(self, mode):
        self._modes.remove(mode)
        self.update()

    class status(pyobj.Attribute):
        """A pseudo attribute"""
        attrattr = simics.Sim_Attr_Pseudo
        attrtype = "[[s[[ss]]]]"
        def getter(self):
            return [(self.top.obj.name,
                     [("Monitoring modes", ", ".join(self._top._modes))])]

    class modes(pyobj.Attribute):
        """Get modes"""
        attrattr = simics.Sim_Attr_Pseudo
        attrtype = "[s*]"
        def getter(self):
            return list(self._top._modes)
        def setter(self, val):
            self._top._modes = set()
            for mode in val:
                self._top._modes.add(mode)
            self._top.update()

    class instrumentation_filter_master(pyobj.Interface):
        def set_source_id(self, id):
            self._top._source_id = id

        def short_filter_config(self):
            return ", ".join(self._top._modes)

        def add_slave(self, slave_obj, cpu):
            if not hasattr(cpu.iface, "x86_reg_access"):
                simics.SIM_log_error(self._top.obj, 0,
                                     "Object does not support"
                                     " x86_reg_access iface")
                return False

            # Add callback for x86 mode switch
            h = cpu.iface.x86_instrumentation_subscribe.register_mode_switch_cb(
                self._top.obj, self._top.x86_mode_switch_cb, None)
            self._top._handles.append((cpu, h))

            slaves = self._top._slaves.get(cpu, set())
            slaves.add(slave_obj)
            self._top._slaves[cpu] = slaves

            # Update the state depending on the mode this CPU is in now
            mode = _current_mode(cpu)
            self._top.drive_connections(mode, cpu)
            return True

        def remove_slave(self, slave_obj, cpu):
            # Make sure we are not blocking in the slave when we drop this.
            slave_obj.iface.instrumentation_filter_slave.enable(
                self._top._source_id)
            def pop_handle(lst, cpu):
                for i, (c, h) in enumerate(lst):
                    if c == cpu:
                        del lst[i]
                        return h
                assert 0

            # remove callback on cpu
            h = pop_handle(self._top._handles, cpu)
            cpu.iface.cpu_instrumentation_subscribe.remove_callback(h)

            # Update internal state on which slaves that exists
            s = self._top._slaves[cpu]
            s.remove(slave_obj)
            if s:
                self._top._slaves[cpu] = s
            else:
                del self._top._slaves[cpu]

# The available x86_modes as a list of strings
x86_modes = list(modes.x86_modes.values())



def mode_expander(comp, obj):
    return cli.get_completions(comp, x86_modes)

def existing_mode_expander(comp, obj):
    return cli.get_completions(comp, obj.modes)

def add_mode_cmd(obj, mode):
    if mode in obj.modes:
        raise cli.CliError("Error: mode %s is already tracked" % mode)
    filt = simics.SIM_object_data(obj)
    filt.add_mode(mode)

cli.new_command("add-mode", add_mode_cmd,
            args = [cli.arg(cli.string_set_t(x86_modes), "mode",
                        expander = mode_expander)],
            cls = "x86_mode_filter",
            type = ["Instrumentation"],
            short = "add a mode to the filter",
            see_also = ["new-x86-mode-filter",
                        "<x86_mode_filter>.remove-mode",
                        "<x86_mode_filter>.delete"],
            doc = """
            Adds a processor <arg>mode</arg> that will pass through
            the filter. Available modes are: RealMode16, RealMode32,
            Virtual86, ProtectedMode16, ProtectedMode32,
            ProtectedMode64, CompatibilityMode16, or
            CompatibilityMode32. Several modes can be combined by using
            this command several times.""")

def remove_mode_cmd(obj, mode):
    if mode not in obj.modes:
        raise cli.CliError("Error: mode %s not tracked" % mode)
    filt = simics.SIM_object_data(obj)
    filt.remove_mode(mode)

cli.new_command("remove-mode", remove_mode_cmd,
            args = [cli.arg(cli.str_t, "mode", expander = existing_mode_expander)],
            cls = "x86_mode_filter",
            type = ["Instrumentation"],
            short = "remove a mode from the filter",
            see_also = ["new-x86-mode-filter",
                        "<x86_mode_filter>.add-mode",
                        "<x86_mode_filter>.delete"],
            doc = """
            Remove the <arg>mode</arg> from the filter.
            """)

def delete_cmd(obj):
    import instrumentation
    instrumentation.delete_filter(obj)
    simics.SIM_delete_object(obj)

cli.new_command("delete", delete_cmd,
            args = [],
            cls = "x86_mode_filter",
            type = ["Instrumentation"],
            short = "add a mode to the filter",
            see_also = ["new-x86-mode-filter",
                        "<x86_mode_filter>.add-mode",
                        "<x86_mode_filter>.remove-mode"],
            doc = """
            Delete the filter.
            """)
