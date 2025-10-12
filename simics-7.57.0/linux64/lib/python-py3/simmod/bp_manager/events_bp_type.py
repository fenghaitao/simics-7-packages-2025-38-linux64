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

class Breakpoint:
    __slots__ = ('ev_type', 'queue_obj', 'event_obj', 'name',
                 'event_class', 'description', 'once',
                 'last_event_obj', 'last_event_class',
                 'last_description', 'last_value')

    def __init__(self, ev_type, queue_obj, event_obj, event_class,
                 description, once):
        self.ev_type = ev_type
        self.queue_obj = queue_obj
        self.event_obj = event_obj
        self.name = event_obj.name if event_obj else None
        self.event_class = event_class
        self.description = description
        self.once = once
        self.last_event_obj = None
        self.last_event_class = None
        self.last_description = None
        self.last_value = None

    def __str__(self):
        return f"{self.ev_type} event"

    def desc(self):
        def optional(text, value):
            return text + " " + (value if value != None else "(any)")
        return (f"{self} with "
                + optional("event object", self.name) + ", "
                + optional("event class", self.event_class) + ", "
                + optional("description", self.description)
                + " on clock " + (f"{self.queue_obj.name}"))

    def msg(self):
        def getname(obj):
            return obj.name if obj else None
        return (f'object={getname(self.last_event_obj)}, '
                + f'eventclass="{self.last_event_class}", '
                + f'description="{self.last_description}", '
                + f'value={self.last_value}')

class EventBreakpoint:
    def _common_doc(self):
        return f"""on a clock object. The object needs to implement
    the <iface>{self.ev_type}_event_instrumentation</iface> interface
    for this to work.

    To narrow down the events to match you can give the properties
    <arg>event-class</arg> to match the name of the event class,
    and/or <arg>event-object</arg> to match the object in the event,
    and/or <arg>description</arg> to match the description of the
    event. If a property is not given it will match any value.  """

    def _break_doc(self):
        return "Adds an event breakpoint " + self._common_doc()
    def _until_doc(self):
        return "Runs until an event triggers " + self._common_doc()
    def _wait_for_doc(self):
        return "Waits for an event to trigger " + self._common_doc()
    def _trace_doc(self):
        return "Traces events posted " + self._common_doc()

    def __init__(self):
        self.bp_data = {} # bp_id : Breakpoint
        self.next_id = 1
        self.handles = {} # queue_obj : instrumentation handle

    def _finalize(self):
        conf.bp.iface.breakpoint_type.register_type(
            f"{self.ev_type}-event",
            self.obj,
            [[["obj_t", "event object", "conf_object"],
                   "event-object", "?", None, None, "", None],
             ["str_t", "event-class", "?", None, None, "", None],
             ["str_t", "description", "?", None, None, "", None]],
            None,
            f'{self.ev_type}_event_instrumentation',
            [f"set {self.ev_type} event break",
             self._break_doc(),
             f"run until specified {self.ev_type} event occurs",
             self._until_doc(),
             f"wait for specified {self.ev_type} event",
             self._wait_for_doc(),
             f"enable tracing of {self.ev_type} events",
             self._trace_doc()],
            True, False, False)

    @staticmethod
    def event_instrumentation_cb(conn, queue_obj, ev_obj,
                                 ticks, ev_class, ev_desc, val, self):
        def match(wildcard, value):
            if wildcard == None:
                return True
            return wildcard == value

        for bp_id in dict(self.bp_data):
            bp = self.bp_data[bp_id]
            if bp.queue_obj != queue_obj:
                continue
            if (match(bp.event_obj, ev_obj)
                and match(bp.event_class, ev_class)
                and match(bp.description, ev_desc)):
                bp.last_event_obj = ev_obj
                bp.last_event_class = ev_class
                bp.last_description = ev_desc
                bp.last_value = val
                conf.bp.iface.breakpoint_type.trigger(
                    self.obj, bp_id, bp.queue_obj,
                    self.trace_msg(bp_id))

    def _delete_bp(self, _, bm_id):
        self.remove_bp(conf.bp.iface.breakpoint_type.get_break_id(
            bm_id))

    def _describe_bp(self, bp_id):
        bp = self.bp_data[bp_id]
        return bp.desc()

    def _get_props(self, _, bm_id):
        bp_id = conf.bp.iface.breakpoint_type.get_break_id(bm_id)
        bp = self.bp_data[bp_id]
        return {"temporary": bp.once,
                "planted": True,
                "object": bp.queue_obj.name if bp.queue_obj else None,
                "description": self._describe_bp(bp_id)}

    def _create_bp(self, interface, method,
                   queue_obj, ev_obj, ev_class, description, once):
        bp_id = self.next_id
        self.next_id += 1

        # install callback for events if not already installed for this
        # queue_obj object
        if queue_obj not in self.handles:
            iface = getattr(queue_obj.iface, interface)
            register = getattr(iface, method)
            self.handles[queue_obj] = register(
                self.obj, self.event_instrumentation_cb, self)

        self.bp_data[bp_id] = Breakpoint(self.ev_type, queue_obj,
                                         ev_obj, ev_class, description,
                                         once)
        return bp_id

    def _queue_objs_with_breakpoints(self):
        cs = set({})
        for bp in self.bp_data.values():
            cs.add(bp.queue_obj)
        return cs

    def _remove_bp(self, interface, method, bp_id):
        queue_obj = self.bp_data[bp_id].queue_obj
        del self.bp_data[bp_id]
        # remove event callback if last breakpoint on clock is removed
        if queue_obj not in self._queue_objs_with_breakpoints():
            handle = self.handles[queue_obj]
            del self.handles[queue_obj]
            iface = getattr(queue_obj.iface, interface)
            remove = getattr(iface, method)
            remove(handle)

class CycleEventBreakpoints(EventBreakpoint):
    TYPE_DESC = "cycle event breakpoints"
    cls = simics.confclass("bp-manager.cycle_event", short_doc=TYPE_DESC,
                           doc=TYPE_DESC, pseudo=True)
    ev_type = "cycle"

    @cls.objects_finalized
    def objects_finalized(self):
        self._finalize()

    @cls.iface.breakpoint_type_provider.register_bp
    def register_bp(self, bp_id):
        bpm_iface = conf.bp.iface.breakpoint_registration
        return bpm_iface.register_breakpoint(
            self._delete_bp, None, self._get_props, None, None, None,
            None, None, None, None)

    @cls.iface.breakpoint_type_provider.add_bp
    def add_bp(self, _, args):
        (queue_obj, evobj, evclass, desc, once) = args
        return self._create_bp("cycle_event_instrumentation",
                               "register_cycle_event_cb",
                               queue_obj, evobj, evclass, desc, once)

    @cls.iface.breakpoint_type_provider.remove_bp
    def remove_bp(self, bp_id):
        self._remove_bp("cycle_event_instrumentation",
                        "remove_cycle_event_cb", bp_id)

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

class StepEventBreakpoints(EventBreakpoint):
    TYPE_DESC = "step event breakpoints"
    cls = simics.confclass("bp-manager.step_event", short_doc=TYPE_DESC,
                           doc=TYPE_DESC, pseudo=True)
    ev_type = "step"

    @cls.objects_finalized
    def objects_finalized(self):
        self._finalize()

    @cls.iface.breakpoint_type_provider.register_bp
    def register_bp(self, bp_id):
        bpm_iface = conf.bp.iface.breakpoint_registration
        return bpm_iface.register_breakpoint(
            self._delete_bp, None, self._get_props, None, None, None,
            None, None, None, None)

    @cls.iface.breakpoint_type_provider.add_bp
    def add_bp(self, _, args):
        (queue_obj, evobj, evclass, desc, once) = args
        return self._create_bp("step_event_instrumentation",
                               "register_step_event_cb",
                               queue_obj, evobj, evclass, desc, once)

    @cls.iface.breakpoint_type_provider.remove_bp
    def remove_bp(self, bp_id):
        self._remove_bp("step_event_instrumentation",
                        "remove_step_event_cb", bp_id)

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

def register_event_breakpoints(bpm_class):
    simics.SIM_register_port(bpm_class, "cycle_event",
                             CycleEventBreakpoints.cls.classname,
                             CycleEventBreakpoints.TYPE_DESC)
    simics.SIM_register_port(bpm_class, "step_event",
                             StepEventBreakpoints.cls.classname,
                             StepEventBreakpoints.TYPE_DESC)
