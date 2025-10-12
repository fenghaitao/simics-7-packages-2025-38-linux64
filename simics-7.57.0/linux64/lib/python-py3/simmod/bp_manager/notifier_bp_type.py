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

common_doc = """
The <arg>name</arg> parameter specifies the notifier. If
<tt>-global</tt> is specified, then the notifier must be global,
otherwise the notifier must be registered on <arg>object</arg>.

If <arg>name</arg> is the name of a global notifier, then
<tt>-global</tt> is not needed. If <arg>name</arg> is the name of a
non-global notifier and <arg>object</arg> is not provided, then the
breakpoint is added on all objects that have this notifier registered.

For the global notifiers, see the documentation of the
<tt>global_notifier_type_t</tt> enum about which names should be used.

For the predefined non-global notifiers, see the documentation of the
<tt>notifier_type_t</tt> enum about which names should be used.
"""

break_doc = """
Enables breaking simulation on notifiers. When this is
enabled, every time the specified notifier is triggered a message is
printed and simulation is stopped.
""" + common_doc

wait_for_doc = """
Postpones execution of a script branch until a notifier triggers.
""" + common_doc

run_until_doc = """
Run the simulation until a notifier triggers.
""" + common_doc

trace_doc = """
Enables tracing of notifiers. When this is enabled, every
time the specified notifier is triggered a message is printed.
""" + common_doc

class Breakpoint:
    __slots__ = ('name', 'what', 'objs', 'handles', 'once', 'del_handles')
    def __init__(self, name, what, objs, handles, once, del_handles):
        self.name = name
        self.what = what
        self.objs = objs
        self.once = once
        self.handles = handles
        self.del_handles = del_handles

class NotifierBreakpoints:
    TYPE_DESC = "notifier trigger breakpoints"
    cls = simics.confclass("bp-manager.notify", doc=TYPE_DESC,
                           short_doc=TYPE_DESC, pseudo=True)

    # notifier ID -> name
    # name populated in objects_finalized
    NOTIFIER_BLOCK_LIST = {
        # This is used to clean up breakpoint data on delete,
        # hence cannot be used for regular breakpoints.
        simics.Sim_Notify_Object_Delete: "",
    }

    def __init__(self):
        self.bp_data = {}
        self.next_id = 1

    @cls.objects_finalized
    def objects_finalized(self):
        conf.bp.iface.breakpoint_type.register_type(
            "notifier", self.obj,
            [[[["obj_t", "notifier", "conf_object"], "flag_t"],
              ["object", "-global"], "?", None, None, "", [True, False]],
             ["str_t", "name", "1", None, None, "", True]],
            None, None,
            ["set notifier breakpoint", break_doc,
             "run until notifier triggers", run_until_doc,
             "wait for notifier to trigger", wait_for_doc,
             "enable tracing of notifier triggers", trace_doc], False, False,
            False)

        # Populate block list names
        block = {x[1]: x for x in conf.sim.notifier_list
                 if x[1] in self.NOTIFIER_BLOCK_LIST}
        for n in self.NOTIFIER_BLOCK_LIST:
            self.NOTIFIER_BLOCK_LIST[n] = block[n][0]

    # bp.delete callback
    def _delete_bp(self, _, bm_id):
        self.remove_bp(conf.bp.iface.breakpoint_type.get_break_id(bm_id))

    # callback on object delete
    def _delete_notifier_cb(self, subscriber, obj, bp_id):
        bp = self.bp_data[bp_id]
        if obj in bp.objs:
            idx = bp.objs.index(obj)
            bp.objs.pop(idx)
            bp.handles.pop(idx)
            bp.del_handles.pop(idx)

        if not bp.objs:
            bm_id = conf.bp.iface.breakpoint_type.get_manager_id(self.obj, bp_id)
            # this results in a call to remove_bp
            conf.bp.iface.breakpoint_registration.deleted(bm_id)

    def _describe_bp(self, bp_id):
        bp = self.bp_data[bp_id]
        names = ", ".join(o.name for o in bp.objs)
        return (f"Break on notifier '{bp.name}'"
                + (f" on {names}" if bp.objs else ""))

    def _get_props(self, _, bm_id):
        bp_id = conf.bp.iface.breakpoint_type.get_break_id(bm_id)
        bp = self.bp_data[bp_id]
        names = ", ".join(o.name for o in bp.objs)
        return {"temporary": bp.once,
                "planted": True,
                "object": names if bp.objs else None,
                "description": self._describe_bp(bp_id)}

    # List notifiers available on object, or all notifiers
    def _list_notifiers(self, obj):
        if obj:
            cls = simics.SIM_object_class(obj)
            return [x for x in conf.sim.notifier_list
                    if x[2] is None and x[1] not in self.NOTIFIER_BLOCK_LIST
                    and any(c[0] == cls.name for c in x[3])]
        else:
            return [x for x in conf.sim.notifier_list
                    if x[2] is None and x[1] not in self.NOTIFIER_BLOCK_LIST
                    and x[3]]

    def _list_global_notifiers(self):
        return [x for x in conf.sim.notifier_list if x[2] is not None]

    # Return notifier ID from name, given notifier list of the form
    # given by sim->notifier_list
    def _obtain_notifier_id(self, notifiers, name):
        notifier_names = [x[0] for x in notifiers]
        if name not in notifier_names:
            return 0
        else:
            idx = notifier_names.index(name)
            what = notifiers[idx][1]
            return what

    # Return all objects that has notifier registered
    def _notifier_objects(self, name):
        for x in conf.sim.notifier_list:
            if x[0] == name:
                return [o for c in x[3]
                        for o in simics.SIM_object_iterator_for_class(c[0])]
        return []

    def _create_bp(self, arg, name, once):
        # Object or -global may not be given
        if not arg or not isinstance(arg, list):
            global_id = self._obtain_notifier_id(
                self._list_global_notifiers(), name)
            non_global_id = self._obtain_notifier_id(
                self._list_notifiers(None), name)

            if global_id != 0:
                is_global = True
            elif non_global_id != 0:
                is_global = False
                objs = self._notifier_objects(name)
                if not objs:
                    print(f"Notifier '{name}' not registered on any objects",
                          file=sys.stderr)
                    return 0
            else:
                print(f"No such notifier '{name}'", file=sys.stderr)
                return 0
        else:
            assert arg[2] in {"-global", "object"}
            if arg[2] == "-global":
                is_global = True
                global_id = self._obtain_notifier_id(
                    self._list_global_notifiers(), name)
                if global_id == 0:
                    print(f"No such notifier '{name}'", file=sys.stderr)
                    return 0
            else:
                obj = arg[1]
                objs = [obj]
                assert isinstance(obj, simics.conf_object_t)
                is_global = False
                non_global_id = self._obtain_notifier_id(
                    self._list_notifiers(obj), name)
                if non_global_id == 0:
                    if name in self.NOTIFIER_BLOCK_LIST.values():
                        print(f"Cannot set breakpoints on notifier '{name}'",
                              file=sys.stderr)
                    else:
                        print(f"Object {obj.name} has no notifier '{name}'",
                              file=sys.stderr)
                    return 0

        if is_global:
            bp_id = self.next_id
            self.next_id += 1
            arg = (bp_id, name)
            handle = simics.SIM_add_global_notifier(
                global_id, self.obj, self._bp_global_notifier_cb, arg)
            what = global_id
            handles = [handle]
            objs = []
            del_handles = []
        else:
            handles = []
            del_handles = []
            what = non_global_id
            bp_id = self.next_id
            self.next_id += 1
            arg = (bp_id, name)
            for obj in objs:
                assert simics.SIM_has_notifier(obj, non_global_id)
                handle = simics.SIM_add_notifier(obj, non_global_id, self.obj,
                                                 self._bp_notifier_cb, arg)
                handles.append(handle)

                # Breakpoint should be removed when objects are deleted
                del_handle = simics.SIM_add_notifier(
                    obj, simics.Sim_Notify_Object_Delete,
                    self.obj, self._delete_notifier_cb, bp_id)
                del_handles.append(del_handle)

        self.bp_data[bp_id] = Breakpoint(name, what, objs, handles, once,
                                         del_handles)
        return bp_id

    # Object notifier callback
    def _bp_notifier_cb(self, subscriber, notifier, arg):
        (bp_id, name) = arg
        conf.bp.iface.breakpoint_type.trigger(
            self.obj, bp_id, notifier, self.trace_msg(bp_id))

    # Global notifier callback
    def _bp_global_notifier_cb(self, subscriber, arg):
        (bp_id, name) = arg
        conf.bp.iface.breakpoint_type.trigger(
            self.obj, bp_id, subscriber, self.trace_msg(bp_id))

    @cls.iface.breakpoint_type_provider.register_bp
    def register_bp(self, bp_id):
        bpm_iface = conf.bp.iface.breakpoint_registration
        return bpm_iface.register_breakpoint(
            self._delete_bp, None, self._get_props, None, None, None,
            None, None, None, None)

    @cls.iface.breakpoint_type_provider.add_bp
    def add_bp(self, _, args):
        (arg, name, once) = args
        return self._create_bp(arg, name, once)

    @cls.iface.breakpoint_type_provider.remove_bp
    def remove_bp(self, bp_id):
        bp = self.bp_data[bp_id]
        if bp.objs:
            # Object may be deleted
            for (o, h) in zip(bp.objs, bp.handles):
                if isinstance(o, simics.conf_object_t):
                    simics.SIM_delete_notifier(o, h)
        else:
            for h in bp.handles:
                simics.SIM_delete_global_notifier(h)
        del self.bp_data[bp_id]
        if bp.del_handles and bp.objs:
            for (o, h) in zip(bp.objs, bp.del_handles):
                if isinstance(o, simics.conf_object_t):
                    simics.SIM_delete_notifier(o, h)

    @cls.iface.breakpoint_type_provider.trace_msg
    def trace_msg(self, bp_id):
        bp = self.bp_data[bp_id]
        return (f"triggered notifier '{bp.name}'")

    @cls.iface.breakpoint_type_provider.break_msg
    def break_msg(self, bp_id):
        bp = self.bp_data[bp_id]
        names = ", ".join(o.name for o in bp.objs)
        return (f"Break on notifier '{bp.name}'"
                + (f" on {names}" if bp.objs else ""))

    @cls.iface.breakpoint_type_provider.wait_msg
    def wait_msg(self, bp_id):
        bp = self.bp_data[bp_id]
        names = ", ".join(o.name for o in bp.objs)
        return (f"Waiting for notifier '{bp.name}'"
                + (f" on {names}" if bp.objs else ""))

    def _expand_names(self, prev_args):
        if len(prev_args) <= 1 or prev_args[1] is None:
            return ([x[0] for x in self._list_notifiers(None)] +
                    [x[0] for x in self._list_global_notifiers()])

        arg = prev_args[1]
        assert arg[2] in {"-global", "object"}
        if arg[2] == "object":
            obj = arg[1]
            assert isinstance(obj, simics.conf_object_t)
            return [x[0] for x in self._list_notifiers(obj)]
        else:
            return [x[0] for x in self._list_global_notifiers()]

    def _expand_objects(self, prev_args):
        if len(prev_args) <= 1 or prev_args[2] is None:
            return [o.name for o in simics.SIM_object_iterator(None)]
        return [o.name for o in self._notifier_objects(prev_args[2])]

    @cls.iface.breakpoint_type_provider.values
    def values(self, param, prev_args):
        if param == 'name':
            return self._expand_names(prev_args)
        elif param == 'object':
            return self._expand_objects(prev_args)
        else:
            return []

def register_notifier_breakpoints(bpm_class):
    simics.SIM_register_port(bpm_class, "notifier",
                             NotifierBreakpoints.cls.classname,
                             NotifierBreakpoints.TYPE_DESC)
