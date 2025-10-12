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
import cli
import conf
import simics

def num_str(num):
    if isinstance(num, int):
        return cli.number_str(num)
    else:
        return str(num)

class Breakpoint:
    __slots__ = ('kind', 'clk', 'at', 'once')
    def __init__(self, kind, clk, at, once):
        self.kind = kind
        self.clk = clk
        self.at = at
        self.once = once

    def at_s(self):
        return num_str(self.at)

class ClockBreakpoints:
    def __init__(self):
        self.bp_data = {}
        self.next_id = 1

        self.snapshot_did_load_cb = simics.SIM_add_global_notifier(
            simics.Sim_Global_Notify_After_Snapshot_Restore,
            None, self._snapshot_did_load, None)

    def _now(self, kind, clk):
        if kind == 'time':
            return simics.SIM_time(clk)
        elif kind == 'step':
            return simics.SIM_step_count(clk)
        elif kind == 'cycle':
            return simics.SIM_cycle_count(clk)
        else:
            assert(0)

    def _default_clk(self, kind):
        if kind in {'time', 'cycle'}:
            return cli.current_cycle_obj_null()
        elif kind == 'step':
            return cli.current_step_obj_null()
        else:
            assert(0)

    def _repost_time_bp(self, bp_id):
        bp = self.bp_data[bp_id]
        now = self._now(bp.kind, bp.clk)
        if bp.at < now:
            return False
        if bp.kind == 'time':
            simics.SIM_event_post_time(bp.clk, self.break_event, self.obj,
                                       bp.at - now, bp_id)
        elif bp.kind == 'step':
            simics.SIM_event_post_step(bp.clk, self.break_event, self.obj,
                                       bp.at - now, bp_id)
        elif bp.kind == 'cycle':
            simics.SIM_event_post_cycle(bp.clk, self.break_event, self.obj,
                                        bp.at - now, bp_id)
        return True

    def _repost_all_time_bps(self):
        # repost time breakpoints since they are removed when triggered while
        # replaying and that can happen several times while reversing
        for bp_id in self.bp_data:
            self._repost_time_bp(bp_id)

    def _snapshot_did_load(self, obj, data):
        self._repost_all_time_bps()

    def _bp_cb(self, obj, bp_id):
        bp = self.bp_data[bp_id]
        cli.set_current_frontend_object(bp.clk, True)
        conf.bp.iface.breakpoint_type.trigger(
            obj, bp_id, obj, self._trace_msg(bp_id))

    def _install_bp(self, args, now):
        bp_id = self.next_id
        self.next_id += 1

        self.bp_data[bp_id] = Breakpoint(*args)
        bp = self.bp_data[bp_id]
        if bp.at >= now:
            try:
                if not self._repost_time_bp(bp_id):
                    return 0
            except simics.SimExc_General:
                self._uninstall_bp(bp_id)
                return 0
        else:
            print(f"Cannot set {bp.kind} breakpoint at {bp.at_s()}"
                  f" which is in the past < {num_str(now)}",
                  file=sys.stderr)
            self._uninstall_bp(bp_id)
            return 0
        return bp_id

    def _cancel_event(self, bp_id, cancel_id):
        return 1 if bp_id == cancel_id else 0

    def _uninstall_bp(self, bp_id):
        bp = self.bp_data[bp_id]
        # Object may have been deleted
        if isinstance(bp.clk, simics.conf_object_t):
            if bp.kind == 'time':
                simics.SIM_event_cancel_time(bp.clk, self.break_event, self.obj,
                                             self._cancel_event, bp_id)
            elif bp.kind == 'step':
                simics.SIM_event_cancel_step(bp.clk, self.break_event, self.obj,
                                             self._cancel_event, bp_id)
            elif bp.kind == 'cycle':
                simics.SIM_event_cancel_time(bp.clk, self.break_event, self.obj,
                                             self._cancel_event, bp_id)
        del self.bp_data[bp_id]

    def _delete_bp(self, _, bm_id):
        self._uninstall_bp(conf.bp.iface.breakpoint_type.get_break_id(bm_id))

    def _describe_event(self, _, bp_id):
        bp = self.bp_data[bp_id]
        return f"Break event on {bp.clk.name} at {bp.kind} {bp.at_s()}"

    def _describe_break(self, bp_id):
        bp = self.bp_data[bp_id]
        return f"Clock {bp.clk.name} break at {bp.kind} {bp.at_s()}"

    def _get_props(self, _, bm_id):
        bp_id = conf.bp.iface.breakpoint_type.get_break_id(bm_id)
        bp = self.bp_data[bp_id]
        return {"temporary": bp.once,
                "planted": True,
                "object": bp.clk.name,
                "description": self._describe_break(bp_id)}

    def _create_bp(self, kind, clk, at, absolute, once):
        if clk is None:
            clk = self._default_clk(kind)
        if clk is None:
            return 0
        now = self._now(kind, clk)
        abs_time = at if absolute else at + now
        return self._install_bp((kind, clk, abs_time, once), now)

    def _trace_msg(self, bp_id):
        bp = self.bp_data[bp_id]
        return f"{bp.clk.name} reached {bp.kind} {bp.at_s()}"

    def _break_msg(self, bp_id):
        bp = self.bp_data[bp_id]
        return f"{bp.clk.name} will break at {bp.kind} {bp.at_s()}"

    def _wait_msg(self, bp_id):
        bp = self.bp_data[bp_id]
        return f"{bp.clk.name} waiting for {bp.kind} {bp.at_s()}"

time_break_doc = """
Sets a breakpoint that will trigger when the processor
has executed the specified number of <arg>seconds</arg>, from
the time the command was issued. If <tt>-absolute</tt> is specified,
the number of seconds is counted from the start of the simulation
instead.

If no processor is specified, the currently selected frontend
processor is used."""

time_run_until_doc = """
Run the simulation until the processor has
executed <arg>seconds</arg> number of seconds. If <tt>-absolute</tt> is
specified, the simulation will run until the processor
reaches the specified time in the simulation.

If no processor is specified, the currently selected frontend
processor is used."""

time_wait_for_doc = """
Postpones execution of a script branch until the processor has
executed <arg>seconds</arg> number of seconds. If <tt>-absolute</tt> is
specified, the branch will instead be suspended until the processor
reaches the specified time in the simulation.

If no processor is specified, the currently selected frontend
processor is used."""

time_trace_doc = """
Enable tracing for when the processor reaches the point in time
that is <arg>seconds</arg> number of seconds ahead of the time when
the command is issued. If <tt>-absolute</tt> is specified, the time
that is traced is instead the specified number of seconds from the
start of the simulation.

If no processor is specified, the currently selected frontend
processor is used."""

class TimeBreakpoints(ClockBreakpoints):
    TYPE_DESC = "virtual time breakpoints"
    cls = simics.confclass("bp-manager.time", doc=TYPE_DESC,
                           short_doc=TYPE_DESC, pseudo=True)

    @cls.init
    def initialize(self):
        self.break_event = simics.SIM_register_event(
            "time-breakpoints", TimeBreakpoints.cls.classname,
            simics.Sim_EC_Notsaved, self._bp_cb,
            None, None, None, self._describe_event)

    @cls.objects_finalized
    def objects_finalized(self):
        conf.bp.iface.breakpoint_type.register_type(
            "time", self.obj,
            [["float_t", "seconds", '1', None, None, "", None],
             ["flag_t", "-absolute", '1', None, None, "", None]],
            None, 'cycle', ["set time breakpoint", time_break_doc,
                            "run until specified time", time_run_until_doc,
                            "wait for specified time", time_wait_for_doc,
                            "enable tracing of time points", time_trace_doc],
            False, True, False)

    @cls.iface.breakpoint_type_provider.register_bp
    def register_bp(self, bp_id):
        bpm_iface = conf.bp.iface.breakpoint_registration
        return bpm_iface.register_breakpoint(
            self._delete_bp, None, self._get_props, None, None, None,
            None, None, None, None)

    @cls.iface.breakpoint_type_provider.add_bp
    def add_bp(self, _, args):
        (clk, seconds, absolute, once) = args
        return self._create_bp('time', clk, seconds, absolute, once)

    @cls.iface.breakpoint_type_provider.remove_bp
    def remove_bp(self, bp_id):
        self._uninstall_bp(bp_id)

    @cls.iface.breakpoint_type_provider.trace_msg
    def trace_msg(self, bp_id):
        return self._trace_msg(bp_id)

    @cls.iface.breakpoint_type_provider.break_msg
    def break_msg(self, bm_id):
        return self._break_msg(bm_id)

    @cls.iface.breakpoint_type_provider.wait_msg
    def wait_msg(self, bp_id):
        return self._wait_msg(bp_id)

cycle_break_doc = """
Sets a breakpoint that will trigger when the processor's
cycle counter has reached the <arg>cycle</arg> number of cycles from
the time the command was issued. If <tt>-absolute</tt> is specified,
the number of cycles is counted from the start of the simulation
instead.

If no processor is specified, the currently selected frontend
processor is used."""

cycle_run_until_doc = """
Run the simulation until the processor has
executed <arg>cycle</arg> number of cycles. If <tt>-absolute</tt> is
specified, the simulation will instead run until the processor
reaches the specified cycle in the simulation.

If no processor is specified, the currently selected frontend
processor is used."""

cycle_wait_for_doc = """
Postpones execution of a script branch until the processor has
executed <arg>cycle</arg> number of cycles. If <tt>-absolute</tt> is
specified, the branch will instead be suspended until the processor
reaches the specified cycle in the simulation.

If no processor is specified, the currently selected frontend
processor is used."""

cycle_trace_doc = """
Enable tracing for when the processor's cycle counter reaches the
<arg>cycle</arg> number of cycles from the time the command was
issued. If <tt>-absolute</tt> is specified, the number of cycles is
counted from the start of the simulation instead.

If no processor is specified, the currently selected frontend
processor is used."""

class CycleBreakpoints(ClockBreakpoints):
    TYPE_DESC = "cycle queue breakpoints"
    cls = simics.confclass("bp-manager.cycle", doc=TYPE_DESC,
                           short_doc=TYPE_DESC, pseudo=True)

    @cls.init
    def initialize(self):
        self.break_event = simics.SIM_register_event(
            "cycle-breakpoints", CycleBreakpoints.cls.classname,
            simics.Sim_EC_Notsaved, self._bp_cb,
            None, None, None, self._describe_event)

    @cls.objects_finalized
    def objects_finalized(self):
        conf.bp.iface.breakpoint_type.register_type(
            "cycle", self.obj,
            [["int_t", "cycle", '1', None, None, "", None],
             ["flag_t", "-absolute", '1', None, None, "", None]],
            None, 'cycle', ["set cycle breakpoint", cycle_break_doc,
                            "run until specified cycle", cycle_run_until_doc,
                            "wait for specified cycle", cycle_wait_for_doc,
                            "enable tracing of cycle points", cycle_trace_doc],
            False, True, False)

    @cls.iface.breakpoint_type_provider.register_bp
    def register_bp(self, bp_id):
        bpm_iface = conf.bp.iface.breakpoint_registration
        return bpm_iface.register_breakpoint(
            self._delete_bp, None, self._get_props, None, None, None,
            None, None, None, None)

    @cls.iface.breakpoint_type_provider.add_bp
    def add_bp(self, _, args):
        (clk, cycles, absolute, once) = args
        return self._create_bp('cycle', clk, cycles, absolute, once)

    @cls.iface.breakpoint_type_provider.remove_bp
    def remove_bp(self, bp_id):
        self._uninstall_bp(bp_id)

    @cls.iface.breakpoint_type_provider.trace_msg
    def trace_msg(self, bp_id):
        return self._trace_msg(bp_id)

    @cls.iface.breakpoint_type_provider.break_msg
    def break_msg(self, bm_id):
        return self._break_msg(bm_id)

    @cls.iface.breakpoint_type_provider.wait_msg
    def wait_msg(self, bp_id):
        return self._wait_msg(bp_id)

step_break_doc = """
Sets a breakpoint that will trigger when the processor's
step counter has reached the <arg>step</arg> number of steps from the
time the command was issued. If <tt>-absolute</tt> is specified, the
number of steps is counted from the start of the simulation instead.

If no processor is specified, the currently selected frontend
processor is used."""

step_run_until_doc = """
Run the simulation until the processor has
executed <arg>step</arg> number of steps. If <tt>-absolute</tt> is
specified, the simulation will instead run until the processor
reaches the specified step in the simulation.

If no processor is specified, the currently selected frontend
processor is used."""

step_wait_for_doc = """
Postpones execution of a script branch until the processor has
executed <arg>step</arg> number of steps. If <tt>-absolute</tt> is
specified, the branch will instead be suspended until the processor
reaches the specified step in the simulation.

If no processor is specified, the currently selected frontend
processor is used."""

step_trace_doc = """
Enable tracing for when the processor's step counter reaches the
<arg>step</arg> number of step from the time the command was
issued. If <tt>-absolute</tt> is specified, the number of step is
counted from the start of the simulation instead.

If no processor is specified, the currently selected frontend
processor is used."""

class StepBreakpoints(ClockBreakpoints):
    TYPE_DESC = "step queue breakpoints"
    cls = simics.confclass("bp-manager.step", doc=TYPE_DESC,
                           short_doc=TYPE_DESC, pseudo=True)

    @cls.init
    def initialize(self):
        self.break_event = simics.SIM_register_event(
            "step-breakpoints", StepBreakpoints.cls.classname,
            simics.Sim_EC_Notsaved, self._bp_cb,
            None, None, None, self._describe_event)

    @cls.objects_finalized
    def objects_finalized(self):
        conf.bp.iface.breakpoint_type.register_type(
            "step", self.obj,
            [["int_t", "step", '1', None, None, "", None],
             ["flag_t", "-absolute", '1', None, None, "", None]],
            None, 'step', ["set step breakpoint", step_break_doc,
                           "run until specified step", step_run_until_doc,
                           "wait for specified step", step_wait_for_doc,
                           "enable tracing of step points", step_trace_doc],
            False, True, False)

    @cls.iface.breakpoint_type_provider.register_bp
    def register_bp(self, bp_id):
        bpm_iface = conf.bp.iface.breakpoint_registration
        return bpm_iface.register_breakpoint(
            self._delete_bp, None, self._get_props, None, None, None,
            None, None, None, None)

    @cls.iface.breakpoint_type_provider.add_bp
    def add_bp(self, _, args):
        (clk, step, absolute, once) = args
        return self._create_bp('step', clk, step, absolute, once)

    @cls.iface.breakpoint_type_provider.remove_bp
    def remove_bp(self, bp_id):
        self._uninstall_bp(bp_id)

    @cls.iface.breakpoint_type_provider.trace_msg
    def trace_msg(self, bp_id):
        return self._trace_msg(bp_id)

    @cls.iface.breakpoint_type_provider.break_msg
    def break_msg(self, bm_id):
        return self._break_msg(bm_id)

    @cls.iface.breakpoint_type_provider.wait_msg
    def wait_msg(self, bp_id):
        return self._wait_msg(bp_id)

def register_clock_breakpoints(bpm_class):
    simics.SIM_register_port(bpm_class, "time",
                             TimeBreakpoints.cls.classname,
                             TimeBreakpoints.TYPE_DESC)
    simics.SIM_register_port(bpm_class, "cycle",
                             CycleBreakpoints.cls.classname,
                             CycleBreakpoints.TYPE_DESC)
    simics.SIM_register_port(bpm_class, "step",
                             StepBreakpoints.cls.classname,
                             StepBreakpoints.TYPE_DESC)
