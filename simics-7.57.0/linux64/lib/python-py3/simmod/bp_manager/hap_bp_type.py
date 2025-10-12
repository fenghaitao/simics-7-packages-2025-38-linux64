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
import cli
from script_branch import transform_hap_arg

common_doc = """
The optional argument <arg>object</arg> limits the considered hap occurrences
to a specific object, and <arg>index</arg> can be used for indexed haps.

The <arg>name</arg> parameter specifies the hap. If the <tt>-all</tt> flag is
specified, all haps will be used.

When a hap triggers, the frontend object is changed to the object that
triggered the hap, unless <tt>-s</tt> is specified.
"""

break_doc = """
Enables breaking simulation on haps. When this is
enabled, every time the specified hap is triggered a message is
printed and simulation is stopped.
""" + common_doc

wait_for_doc = """
Postpones execution of a script branch until a hap occurs.
""" + common_doc

run_until_doc = """
Run the simulation until a hap occurs.
""" + common_doc

trace_doc = """
Enables tracing of haps. When this is enabled, every
time the specified hap is triggered a message is printed.
""" + common_doc

class LastHapInfo:
    # NB: the generic_transaction_t argument is only valid in the hap callback.
    # So the LastHapInfo stores extracted data, not generic_transaction_t ref.
    __slots__ = ('trace_msg', 'break_data')
    def __init__(self, name, obj, hap_args):
        def _format_trace_arg(val):
            if isinstance(val, simics.generic_transaction_t):
                return '<generic_transaction_t>'
            else:
                return cli.format_attribute(val)

        self.trace_msg = (
            f"{name} {' '.join(_format_trace_arg(a) for a in hap_args)}")
        self.break_data = [obj] + [transform_hap_arg(a) for a in hap_args]

class Breakpoint:
    __slots__ = ('hap_data', 'last_hap', 'obj', 'idx',
                 'once', 'notifier_handle', 'no_frontend_obj')
    def __init__(self, hap_data, obj, idx, once, notifier_handle,
                 no_frontend_obj):
        self.hap_data = hap_data
        self.obj = obj
        self.idx = idx
        self.once = once
        self.notifier_handle = notifier_handle
        self.no_frontend_obj = no_frontend_obj
        self.last_hap = None

class HapBreakpoints:
    TYPE_DESC = "hap occurrence breakpoints"
    cls = simics.confclass("bp-manager.hap", doc=TYPE_DESC,
                           short_doc=TYPE_DESC, pseudo=True)

    HAP_BLOCK_LIST = {
        # cannot wait on hap, see old wait-for-hap
        'Core_At_Exit',
    }

    def __init__(self):
        self.bp_data = {}
        self.next_id = 1

    @cls.objects_finalized
    def objects_finalized(self):
        conf.bp.iface.breakpoint_type.register_type(
            "hap", self.obj,
            [[["str_t", "flag_t"], ["name", "-all"],
              "1", None, None, "", [True, None]],
             [["obj_t", "hap object", "conf_object"],
              "object", "?", None, None, "", None],
             ["uint_t", "index", "?", -1, None, "", None],
             ["flag_t", "-s", "1", None, None, "", None]],
            None, None,
            ["set hap breakpoint", break_doc,
             "run until hap triggers", run_until_doc,
             "wait for hap to trigger", wait_for_doc,
             "enable tracing of hap triggers", trace_doc], False, False, False)

    def _delete_bp(self, _, bm_id):
        self.remove_bp(conf.bp.iface.breakpoint_type.get_break_id(bm_id))

    def _remove_bp(self, bp_id):
        bm_id = conf.bp.iface.breakpoint_type.get_manager_id(self.obj, bp_id)
        conf.bp.iface.breakpoint_registration.deleted(bm_id)

    def _delete_notifier_cb(self, subscriber, obj, bp_id):
        self._remove_bp(bp_id)

    def _describe_bp(self, bp_id):
        bp = self.bp_data[bp_id]
        return ("Break on " + ("all haps" if len(bp.hap_data) > 1
                                else f"hap {list(bp.hap_data.keys())[0][1]}")
                + (f" on {bp.obj.name}" if bp.obj else "")
                + (f" index {bp.idx}" if bp.idx != -1 else ""))

    def _get_props(self, _, bm_id):
        bp_id = conf.bp.iface.breakpoint_type.get_break_id(bm_id)
        bp = self.bp_data[bp_id]
        return {"temporary": bp.once,
                "planted": True,
                "object": bp.obj.name if bp.obj else None,
                "description": self._describe_bp(bp_id)}

    def _list_haps(self):
        return list({x[0] for x in conf.sim.hap_list}
                     - self.HAP_BLOCK_LIST)

    def _create_bp(self, arg, obj, idx, once, internal_ok, no_frontend_obj, cb):
        assert arg[0] in {"str_t", "flag_t"}

        haps = []
        if arg[0] == "str_t":
            name = arg[1]

            # Verify that name is a hap
            try:
                _ = simics.SIM_hap_get_number(name)
            except simics.SimExc_Lookup as ex:
                print(ex, file=sys.stderr)
                return 0

            # Not allowed to track all haps
            if (name in self.HAP_BLOCK_LIST
                or (not internal_ok and name.startswith("Internal_"))):
                print(f"Cannot use hap {name} for breakpoints",
                      file=sys.stderr)
                return 0

            haps.append(name)
        else:
            # Remove haps whose callbacks can be triggered before or after our
            # data structure is consistent
            all_haps = set(self._list_haps())
            haps = list(all_haps - {
                'Core_Hap_Callback_Installed',
                'Core_Hap_Callback_Removed',
                'Core_Log_Message',
                'Core_Log_Message_Filtered',
                'Core_Log_Message_Extended',
                'Core_Simulation_Mode_Change',
            })

        bp_id = self.next_id
        self.next_id += 1

        # Save all hap parameters to make sure Python GC will not free them
        hap_data = {}
        if obj:
            if idx != -1:
                for name in haps:
                    arg = (bp_id, name)
                    hap_id = simics.SIM_hap_add_callback_obj_index(
                        name, obj, 0, cb, arg, idx)
                    hap_data[arg] = hap_id
            else:
                for name in haps:
                    arg = (bp_id, name)
                    hap_id = simics.SIM_hap_add_callback_obj(
                        name, obj, 0, cb, arg)
                    hap_data[arg] = hap_id
        else:
            if idx != -1:
                for name in haps:
                    arg = (bp_id, name)
                    hap_id = simics.SIM_hap_add_callback_index(
                        name, cb, arg, idx)
                    hap_data[arg] = hap_id
            else:
                for name in haps:
                    arg = (bp_id, name)
                    hap_id = simics.SIM_hap_add_callback(name, cb, arg)
                    hap_data[arg] = hap_id

        # Breakpoint should be removed when object is deleted
        if obj:
            notifier_handle = simics.SIM_add_notifier(
                obj, simics.Sim_Notify_Object_Delete,
                self.obj, self._delete_notifier_cb, bp_id)
        else:
            notifier_handle = None

        self.bp_data[bp_id] = Breakpoint(hap_data, obj, idx,
                                         once, notifier_handle,
                                         no_frontend_obj)
        return bp_id

    def _is_cpu_or_clock(self, obj):
        return (hasattr(obj.iface, simics.CYCLE_INTERFACE)
                or hasattr(obj.iface, simics.PROCESSOR_INFO_INTERFACE)
                or hasattr(obj.iface, simics.STEP_INTERFACE))

    def _bp_cb(self, arg, obj, *args):
        (bp_id, name) = arg
        # Breakpoint may have been deleted, but not hap callback yet
        if bp_id in self.bp_data:
            bp = self.bp_data[bp_id]
            # Last triggered hap
            bp.last_hap = LastHapInfo(name, obj, args)
            if not bp.no_frontend_obj and obj and self._is_cpu_or_clock(obj):
                cli.set_current_frontend_object(obj, True)
            conf.bp.iface.breakpoint_type.trigger(self.obj, bp_id,
                                                  obj, self.trace_msg(bp_id))

    @cls.iface.breakpoint_type_provider.register_bp
    def register_bp(self, bp_id):
        bpm_iface = conf.bp.iface.breakpoint_registration
        return bpm_iface.register_breakpoint(
            self._delete_bp, None, self._get_props, None, None, None,
            None, None, None, None)

    @cls.iface.breakpoint_type_provider.add_bp
    def add_bp(self, flags, args):
        (arg, obj, idx, no_frontend_obj, once) = args
        return self._create_bp(arg, obj, idx, once,
                               flags != simics.Breakpoint_Type_Trace,
                               no_frontend_obj,
                               self._bp_cb)

    @cls.iface.breakpoint_type_provider.remove_bp
    def remove_bp(self, bp_id):
        bp = self.bp_data[bp_id]
        if bp.obj:
            # Object may be deleted
            if isinstance(bp.obj, simics.conf_object_t):
                for (arg, hap_id) in bp.hap_data.items():
                    simics.SIM_hap_delete_callback_obj_id(arg[1],
                                                          bp.obj, hap_id)
        else:
            for (arg, hap_id) in bp.hap_data.items():
                simics.SIM_run_alone(
                    lambda x: simics.SIM_hap_delete_callback_id(x[0], x[1]),
                    (arg[1], hap_id))
        del self.bp_data[bp_id]
        if bp.notifier_handle and isinstance(bp.obj, simics.conf_object_t):
            simics.SIM_delete_notifier(bp.obj, bp.notifier_handle)

    @cls.iface.breakpoint_type_provider.trace_msg
    def trace_msg(self, bp_id):
        bp = self.bp_data[bp_id]
        return bp.last_hap.trace_msg if bp.last_hap else ""

    @cls.iface.breakpoint_type_provider.break_msg
    def break_msg(self, bp_id):
        bp = self.bp_data[bp_id]
        return ("Break on " + ("all haps" if len(bp.hap_data) > 1
                                else f"hap {list(bp.hap_data.keys())[0][1]}")
                + (f" on {bp.obj.name}" if bp.obj else "")
                + (f" index {bp.idx}" if bp.idx != -1 else ""))

    @cls.iface.breakpoint_type_provider.wait_msg
    def wait_msg(self, bp_id):
        bp = self.bp_data[bp_id]
        return ("Waiting for " + ("any hap" if len(bp.hap_data) > 1
                                   else f"hap {list(bp.hap_data.keys())[0][1]}")
                + (f" on {bp.obj.name}" if bp.obj else "")
                + (f" index {bp.idx}" if bp.idx != -1 else ""))

    @cls.iface.breakpoint_type_provider.values
    def values(self, arg, prev_args):
        return self._list_haps()

    @cls.iface.breakpoint_type_provider.break_data
    def break_data(self, bp_id):
        bp = self.bp_data[bp_id]
        return bp.last_hap.break_data if bp.last_hap else None

def register_hap_breakpoints(bpm_class):
    simics.SIM_register_port(bpm_class, "hap",
                             HapBreakpoints.cls.classname,
                             HapBreakpoints.TYPE_DESC)
