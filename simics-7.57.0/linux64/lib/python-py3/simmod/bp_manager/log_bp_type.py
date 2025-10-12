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
import re
import conf
import simics
from sim_commands import log_types, get_cycle_object_for_timestamps

break_doc = """
Enables breaking simulation on logs. When enabled the simulation will stop
every time it hits a certain log. If no argument is given, breaking on all
logs is enabled.

The <arg>object</arg> argument specifies the object to enable breaking on logs
for.

The <arg>type</arg> argument specifies the log-type to enable breaking for.

The <arg>substr</arg> argument can be used to only break on logs which
contain this string. Together with the <tt>-regexp</tt> flag the string is
interpreted as a regular expression, as defined by the <em>re</em> module in
Python."""

run_until_doc = """
Run the simulation until a specified log message is emitted. The
<arg>type</arg>, and <arg>substr</arg> arguments can be used to run
until log messages matching certain conditions are emitted. The
<arg>object</arg> argument of the command can be used to only consider
log messages on a certain object. The <arg>substr</arg> argument is a
string to look for. It is interpreted as a regular expression, as
defined by the <tt>re</tt> module in Python, if the <tt>-regexp</tt> flag
is specified.

When used in an expression, the commands returns a list with the following
information: [&lt;clock-object>, &lt;seconds>, &lt;cycles>, &lt;log-level>,
&lt;log-type>, &lt;log-group>, &lt;object>, &lt;message>]. The first three
entries form a time stamp for when the log entry was generated.

Note that the log level must be set high enough for the message to be generated
or it will not be found."""

wait_for_doc = """
Postpones execution of a script branch until a specified log message is
emitted. The <arg>type</arg>, and <arg>substr</arg> arguments can be used to
wait for log messages matching certain conditions. The <arg>object</arg>
argument of the command can be used to wait for a log message
on a certain object. The <arg>substr</arg>
argument is a string to wait for. It is interpreted as a regular expression, as
defined by the <tt>re</tt> module in Python, if the <tt>-regexp</tt> flag is
specified.

When used in an expression, the commands returns a list with the following
information: [&lt;clock-object>, &lt;seconds>, &lt;cycles>, &lt;log-level>,
&lt;log-type>, &lt;log-group>, &lt;object>, &lt;message>]. The first three
entries form a time stamp for when the log entry was generated.

Note that the log level must be set high enough for the message to be generated
or it cannot be waited on."""

trace_doc = """
Enable tracing of log messages matching the conditions specified by
the <arg>type</arg> and <arg>substr</arg> arguments. The
<arg>object</arg> argument of the command can be used to only trace
log messages on a certain object. The <arg>substr</arg> argument is a
string to match messages against. It is interpreted as a regular expression, as
defined by the <tt>re</tt> module in Python, if the <tt>-regexp</tt> flag
is specified.

Note that the log level must be set high enough for the message to be generated
or it will not be found."""

class Breakpoint:
    __slots__ = ('hap_ids', 'hap_objects', 'matcher', 'obj', 'log_type',
                 'log_type_name', 'log_str', 'once', 'notifier_handle', 'wdata')
    def __init__(self, hap_ids, hap_objects, matcher, obj,
                 log_type, log_type_name,
                 log_str, once, notifier_handle):
        self.hap_ids = hap_ids
        self.hap_objects = hap_objects
        self.matcher = matcher
        self.obj = obj
        self.log_type = log_type
        self.log_type_name = log_type_name
        self.log_str = log_str
        self.once = once
        self.notifier_handle = notifier_handle
        self.wdata = None

class LogBreakpoints:
    TYPE_DESC = "log message breakpoints"
    cls = simics.confclass("bp-manager.log", doc=TYPE_DESC,
                           short_doc=TYPE_DESC, pseudo=True)

    def __init__(self):
        self.bp_data = {}
        self.next_id = 1
        # Invert log_types dict
        self.log_type_names = {v: k for k, v in log_types.items()}

    @cls.objects_finalized
    def objects_finalized(self):
        conf.bp.iface.breakpoint_type.register_type(
            "log", self.obj,
            [[["obj_t", "log object", "conf_object"],
              "object", "?", None, None, "", None],
             ["flag_t", "-regexp", "1", None, None, "", None],
             ["str_t", "substr", "?", "", None, "", None],
             [["string_set_t", [list(x) for x in log_types.items()], None],
              "type", "?", None, None, "", None]],
            None, None, ["set break on log output", break_doc,
                         "run until log output appears", run_until_doc,
                         "wait until log output appears", wait_for_doc,
                         "enable tracing of log messages", trace_doc],
            False, False, True)

    def _delete_bp(self, _, bm_id):
        self.remove_bp(conf.bp.iface.breakpoint_type.get_break_id(bm_id))

    def _unregister_bp(self, bp_id):
        bm_id = conf.bp.iface.breakpoint_type.get_manager_id(self.obj, bp_id)
        conf.bp.iface.breakpoint_registration.deleted(bm_id)

    def _delete_notifier_cb(self, subscriber, obj, bp_id):
        self._unregister_bp(bp_id)

    def _describe_bp(self, bp_id):
        bp = self.bp_data[bp_id]
        if bp.log_str:
            return (f"Break on {bp.log_type_name} log messages"
                    + f" matching '{bp.log_str}'"
                    + (f" from {bp.obj.name} hierarchy" if bp.obj else ""))
        else:
            return (f"Break on {bp.log_type_name} log messages"
                    + (f" from {bp.obj.name} hierarchy" if bp.obj else ""))

    def _get_props(self, _, bm_id):
        bp_id = conf.bp.iface.breakpoint_type.get_break_id(bm_id)
        bp = self.bp_data[bp_id]
        return {"enabled": True,
                "temporary": bp.once,
                "planted": True,
                "ignore count": 0,
                "object": bp.obj.name if bp.obj else None,
                "description": self._describe_bp(bp_id)}

    def _bp_cb(self, bp_id, trigger_obj, msg_type, msg, log_level, log_group):
        # Ignore log messages from bp-manager objects (used for tracing)
        if (trigger_obj and
            (trigger_obj == conf.bp
             or simics.SIM_port_object_parent(trigger_obj) == conf.bp)):
            return

        # Breakpoint removed with SIM_run_alone
        if bp_id not in self.bp_data:
            return

        bp = self.bp_data[bp_id]
        match = bp.matcher(msg)
        if (match and (bp.log_type is None or bp.log_type == msg_type)
            and (not bp.hap_objects or trigger_obj in bp.hap_objects)):
            wdata = []
            cobj = get_cycle_object_for_timestamps()
            if cobj:
                wdata += [cobj, cobj.iface.cycle.get_time(),
                          cobj.iface.cycle.get_cycle_count()]
            else:
                wdata += [None] * 3
            wdata += [log_level, msg_type, log_group, trigger_obj, msg]
            bp.wdata = wdata
            conf.bp.iface.breakpoint_type.trigger(
                self.obj, bp_id, trigger_obj, self.trace_msg(bp_id))

    def _remove_haps(self, bp_id):
        bp = self.bp_data[bp_id]
        if bp.hap_objects:
            for (h, o) in zip(bp.hap_ids, bp.hap_objects):
                simics.SIM_hap_delete_callback_obj_id(
                    "Core_Log_Message_Filtered", o, h)
        else:
            simics.SIM_run_alone(
                lambda h: simics.SIM_hap_delete_callback_id(
                    "Core_Log_Message_Filtered", h), bp.hap_ids[0])
            bp.hap_ids = []
        if bp.notifier_handle:
            simics.SIM_delete_notifier(bp.obj, bp.notifier_handle)

    def _create_bp(self, obj, log_type, log_str, is_regex, recursive, once):
        bp_id = self.next_id
        self.next_id += 1

        if obj:
            if recursive:
                objs = [obj] + [o for o in simics.SIM_object_iterator(obj)]
                hap_objects = [o for o in objs
                               if hasattr(o.iface, "log_object")]
            else:
                cname = obj.classname
                hap_objects = [obj] + [
                    simics.SIM_get_object("%s.%s" % (obj.name, portname))
                    for (portname, cls) in simics.VT_get_port_classes(
                            cname).items()
                    if simics.SIM_c_get_class_interface(cls, 'log_object')]

            hap_ids = [
                simics.SIM_hap_add_callback_obj(
                    "Core_Log_Message_Filtered", o, 0, self._bp_cb, bp_id)
                for o in hap_objects]
        else:
            hap_objects = []
            hap_ids = [simics.SIM_hap_add_callback("Core_Log_Message_Filtered",
                                                   self._bp_cb, bp_id)]

        if is_regex:
            regex = re.compile(log_str)
            matcher = lambda s: regex.search(s) is not None
        else:
            matcher = lambda s: log_str in s

        if obj:
            notifier_handle = simics.SIM_add_notifier(
                obj, simics.Sim_Notify_Object_Delete,
                self.obj, self._delete_notifier_cb, bp_id)
        else:
            notifier_handle = None

        log_type_name = ("<all>" if log_type is None
                         else self.log_type_names[log_type])
        self.bp_data[bp_id] = Breakpoint(hap_ids, hap_objects, matcher, obj,
                                         log_type, log_type_name,
                                         log_str, once, notifier_handle)
        return bp_id

    @cls.iface.breakpoint_type_provider.register_bp
    def register_bp(self, bp_id):
        bpm_iface = conf.bp.iface.breakpoint_registration
        return bpm_iface.register_breakpoint(
            self._delete_bp, None, self._get_props, None, None, None,
            None, None, None, None)

    @cls.iface.breakpoint_type_provider.add_bp
    def add_bp(self, _, args):
        (obj, is_regex, log_str, log_type, recursive, once) = args
        return self._create_bp(obj, log_type, log_str, is_regex,
                               recursive, once)

    @cls.iface.breakpoint_type_provider.remove_bp
    def remove_bp(self, bp_id):
        self._remove_haps(bp_id)
        del self.bp_data[bp_id]

    @cls.iface.breakpoint_type_provider.trace_msg
    def trace_msg(self, bp_id):
        bp = self.bp_data[bp_id]
        if bp.log_str:
            return (f"log message of type {bp.log_type_name}"
                    f" matching '{bp.log_str}'")
        else:
            return f"log message of type {bp.log_type_name}"

    @cls.iface.breakpoint_type_provider.break_msg
    def break_msg(self, bp_id):
        bp = self.bp_data[bp_id]
        if bp.log_str:
            return (f"Break on '{bp.log_type_name}' log messages"
                    + f" matching '{bp.log_str}'"
                    + (f" from {bp.obj.name} hierarchy" if bp.obj else ""))
        else:
            return (f"Break on '{bp.log_type_name}' log messages"
                    + (f" from {bp.obj.name} hierarchy" if bp.obj else ""))

    @cls.iface.breakpoint_type_provider.wait_msg
    def wait_msg(self, bp_id):
        bp = self.bp_data[bp_id]
        if bp.log_str:
            return (f"Waiting on '{bp.log_type_name}' log messages"
                    + f" matching '{bp.log_str}'"
                    + (f" from {bp.obj.name} hierarchy" if bp.obj else ""))
        else:
            return (f"Waiting on '{bp.log_type_name}' log messages"
                    + (f" from {bp.obj.name} hierarchy" if bp.obj else ""))

    @cls.iface.breakpoint_type_provider.break_data
    def break_data(self, bp_id):
        return self.bp_data[bp_id].wdata

    @cls.iface.breakpoint_type_provider.trace
    def trace(self, msg):
        args = (1, self.obj, 0, msg)
        # Log trace is triggered from a hap callback from the logging code
        # To avoid recursive logging (which is ignored), we must delay a bit
        simics.SIM_run_alone(lambda args: simics.SIM_log_info(*args), args)

def register_log_breakpoints(bpm_class):
    simics.SIM_register_port(bpm_class, "log",
                             LogBreakpoints.cls.classname,
                             LogBreakpoints.TYPE_DESC)
