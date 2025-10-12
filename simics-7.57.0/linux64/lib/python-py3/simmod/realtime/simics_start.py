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


import cli
import simics

# Return the first object which implements the cycle interface.
# This works fine in most circumstances when all clocks are relative
# in sync (for this feature). For systems with more decoupled clocks,
# the user will need to select the clock he wants realtime-mode on.
def pick_cycle_object():
    clocks = list(simics.SIM_object_iterator_for_interface(['cycle']))
    if not clocks:
        return None
    clocks = sorted(clocks)
    return clocks[0]  # Take the first clock

# The enable/disable-realtime mode commands operates on a specific
# realtime object which is created the first time enable-real-time-mode is
# used. Return this object.
def get_existing_realtime_object():
    objs = list(simics.SIM_object_iterator_for_class('realtime'))
    if not objs:
        return None
    return objs[0]   # Return the first one (should be only one)

# Create/reuse an realtime object when we have a clock to use.
def create_rt_object(clock):
    rt = get_existing_realtime_object()
    if rt:
        if clock and rt.clock_object != clock:
            raise cli.CliError("Cannot change clock")
        return rt
    clk = clock if clock else pick_cycle_object()
    if not clk:
        return None             # No clock yet.
    rt = simics.SIM_create_object('realtime', 'realtime',
                           [['clock_object', clk]])
    return rt


# This is just a temporary place-holder for the arguments until
# the realtime object has been created and configured.
class RealTimeMode:
    def __init__(self, speed=None, check_interval=None, drift_comp=None,
                 clock = None):
        if speed is not None and speed <= 0.0:
            raise cli.CliError("The speed argument must be > 0.0")
        if drift_comp is not None and drift_comp < 0.0:
            raise cli.CliError("The drift-compensate argument must be >= 0.0")
        self.speed = speed
        self.check_interval = check_interval
        self.drift_comp = drift_comp
        self.clock = clock    # User chosen clock
        self.rt_obj = create_rt_object(self.clock)

    def is_enabled(self):
        return self.rt_obj.enabled if self.rt_obj else False

    # Copy user settings to realtime object
    def configure(self, enable):
        rt = create_rt_object(self.clock)
        if not rt:
            return
        self.rt_obj = rt
        rt.enabled = enable
        if self.speed is not None:
            rt.speed = self.speed / 100.0
        if self.check_interval is not None:
            rt.check_interval = self.check_interval
        if self.drift_comp is not None:
            rt.drift_compensate = self.drift_comp

class RealTimeModeCommands:
    def __init__(self):
        self.hap_type = "Core_Configuration_Loaded"
        self.rtm_object = None
        self.hap_id = None

        cli.new_command('enable-real-time-mode', self.enable_cmd,
                    [cli.arg(cli.float_t, 'speed', '?', None),
                     cli.arg(cli.range_t(1, 0xffffffff, "positive integer"),
                         'check_interval', '?', None),
                     cli.arg(cli.float_t, 'drift-compensate', '?', None),
                     cli.arg(cli.obj_t('clock', 'cycle'), 'clock', "?", None)],
                    type = ['Execution', 'Performance'],
                    short = 'enable real-time behavior',
                    doc = """
In some cases simulated time may run faster than real time; this can
happen if the OS is in a tight idle loop or an instruction halts
execution waiting for an interrupt, or if the host machine is simply
sufficiently fast. This can cause problems for programs that interact
with the real world (for example the user), since time-outs may expire
really fast.

A <obj>realtime</obj> object will, when enabled, periodically check
the simulation speed and wait for a while if it is too high.
<arg>speed</arg> specifies how fast simulated time is allowed to run,
in percent of real time; default is 100. <arg>check_interval</arg>
specifies how often the check should take place, in milliseconds of
simulated time; default is 1000. Higher values give better
performance; lower values reduce the maximum difference between real
and simulated time. Setting this to less than
<cmd>set-time-quantum</cmd> has no effect.

The <arg>speed</arg> argument says how fast the simulation
<em>should</em> run, but the actual speed will always deviate a little
from that value even if the host is fast enough. To keep these errors
from accumulating, the simulation speed has to be adjusted;
<arg>drift-compensate</arg> regulates how much it may be adjusted. If
set to (for example) 0.25, simulation speed may be increased or
decreased by up to 25% if necessary to make up for any accumulated
drift with respect to real time. If set to zero (the default), the
simulation speed may not be changed at all from its set value.

The <arg>clock</arg> will control which clock is used for real-time
comparison. A configuration may have many clocks/processors. Virtual
time is based on a Simics clock and by default the first clock found
is used to control real-time mode. However, some use cases may allow
clocks to drift apart significantly, which may affect real-time
mode. In such a case, it may be useful to use the <arg>clock</arg>
argument. Notice that the clock can not be changed after the real-time
command has been invoked.

Control this feature by the <cmd>enable-real-time-mode</cmd> and
<cmd>disable-real-time-mode</cmd> commands. The <cmd>real-time-mode</cmd>
command will query whether real-time is enabled or not.

It is possible to run the <cmd>enable-real-time-mode</cmd> command before any
cycle object exists in the configuration. In this case creation of the
<obj>realtime</obj> object will be postponed until a cycle object has been
created. Run <cmd>disable-real-time-mode</cmd> to inhibit postponed mode.
""")

        cli.new_command('disable-real-time-mode', self.disable_cmd,
                    [],
                    type = ['Execution', 'Performance'],
                    short = 'disable real-time behavior',
                    doc_with = 'enable-real-time-mode')

        cli.new_command('real-time-mode', self.query_realtime_mode,
                    [],
                    type = ['Execution', 'Performance'],
                    short = 'query for real-time mode',
                    doc_with = 'enable-real-time-mode')
    # end of __init__

    def is_postponed(self):
        return bool(self.rtm_object)

    def postpone_realtime_enabling(self, rt):
        self.rtm_object = rt
        self.hap_id = simics.SIM_hap_add_callback(self.hap_type, self.hap_cb, None)

    def stop_postponed_enabling(self):
        simics.SIM_hap_delete_callback_id(self.hap_type, self.hap_id)
        self.hap_id = None
        self.rtm_object = None

    # Core_Configuration_Loaded hap callback
    def hap_cb(self, data, trigger):
        if pick_cycle_object():
            # Found a clock!
            rt = self.rtm_object
            self.stop_postponed_enabling()
            self.enable_disable(rt, True)
            print("Real-time mode enabled (was postponed).")

    def enable_disable(self, rt, enable):
        msg = "Real-time mode %s" % ["disabled","enabled"][enable]
        if rt.is_enabled() == enable:
            msg += " already"
        else:
            rt.configure(enable)
        msg += "."
        self.rtm_object = None
        return cli.command_return(msg)

    def enable_cmd(self, speed, check_interval, drift_comp, clock):
        if self.is_postponed():
            return cli.command_return("Real-time mode is postponed already.")

        # Store the parameters in a temporary object, reused only if
        # no clock exists yet.
        rt = RealTimeMode(speed, check_interval, drift_comp, clock)
        if rt.rt_obj:
            return self.enable_disable(rt, True)

        self.postpone_realtime_enabling(rt)
        return cli.command_return("Postponed enable-real-time-mode.")

    def disable_cmd(self):
        if self.is_postponed():
            self.stop_postponed_enabling()
            return cli.command_return("Postponed enable-real-time-mode inhibited.")
        else:
            rt = RealTimeMode() # Dummy object...
            return self.enable_disable(rt, False)

    def query_realtime_mode(self):
        if self.is_postponed():
            e = msg = "Real-time mode is postponed."
        else:
            e = any(rt.enabled
                    for rt in simics.SIM_object_iterator_for_class('realtime'))
            msg = ("Not enabled.", "Enabled.")[e]
        return cli.command_return(value=e, message=msg)

enabler = RealTimeModeCommands()
