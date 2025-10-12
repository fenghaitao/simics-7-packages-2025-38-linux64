# © 2011 Intel Corporation
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
import table
import cmputil
from functools import reduce

# fisketur[wildcard-imports]
from cli import *
from simics import *
from component_utils import (
    trigger_hier_change,
    expand_component_object,
    ComponentGraph,
    ComponentGraphCache,
    convert_direction,
    get_component,
    get_connector_by_name,
    get_connectors,
    object_exists,
    print_connector,
    set_writing_template,
    is_component_hardware,
    class_has_iface,
    inhibit_hotplug_side_effects,
    ComponentError,
    is_cell_object_factory,
    get_all_cells,
)
from comp import (
    pre_obj,
    pre_obj_noprefix,
    get_pre_obj_object,
    set_pre_obj_object,
)

def _is_standalone_connector(cnt):
    return not hasattr(cnt, "owner")
def _connector_instantiated(cnt):
    return not hasattr(cnt, "owner") or cnt.owner.instantiated

def connect_error(src, dst = None, ex = ""):
    if dst:
        raise CliError("Cannot connect '%s' to '%s'. %s" % (src, dst, ex))
    else:
        raise CliError("Cannot connect '%s'. %s" % (src, ex))

def connection_direction_up(src, dst):
    return (src.iface.connector.direction() == Sim_Connector_Direction_Up
            or (src.iface.connector.direction() == Sim_Connector_Direction_Any
                and dst.iface.connector.direction() == Sim_Connector_Direction_Down))

# either src_cnt, dst_cnt, or both are unknown,
# find missing connector based on type
# return src and dst connector objects
def find_connectors(src_obj, dst_obj, src_cnt, dst_cnt, first):
    if src_cnt:
        src_cnt_obj = get_connector_by_name(src_obj, src_cnt)
        if not src_cnt_obj:
            connect_error(src_obj.name, dst_obj.name,
                          "Connector %s not found in %s." % (src_cnt, src_obj.name))
            return (None, None)
    if dst_cnt:
        dst_cnt_obj = get_connector_by_name(dst_obj, dst_cnt)
        if not dst_cnt_obj:
            connect_error(src_obj.name, dst_obj.name,
                          "Connector %s not found in %s." % (dst_cnt, dst_obj.name))
            return (None, None)

    def match_connectors(a, b):
        return [[o1, o2] for (o1, t1) in a for (o2, t2) in b if t1 == t2]

    def available_connectors(obj):
        def check(obj):
            if not obj.iface.connector.multi() and obj.iface.connector.destination():
                return False
            return True
        return [[o, o.iface.connector.type()] for o in get_connectors(obj) if check(o)]

    # possible contains possible connectors is a list of lists where the
    # inner list is a pair of connectors that can be connected
    if not src_cnt and not dst_cnt:
        # both connectors are unknown, find connectors of same type
        possible = match_connectors(available_connectors(src_obj),
                                    available_connectors(dst_obj))
        if not len(possible):
            connect_error(src_obj.name, dst_obj.name,
                          "No matching connectors found.")
            return (None, None)
        elif len(possible) > 1 and not first:
            connect_error(src_obj.name, dst_obj.name,
                          "More than one matching connector pair found.")
            return (None, None)
    else:
        # find missing connector either src or dst
        if src_cnt:
            possible = match_connectors([[src_cnt_obj, src_cnt_obj.iface.connector.type()]],
                                        available_connectors(dst_obj))
        else:
            possible = match_connectors(available_connectors(src_obj),
                                        [[dst_cnt_obj, dst_cnt_obj.iface.connector.type()]])
        if not len(possible):
            connect_error(src_obj.name, dst_obj.name,
                          "The %s and %s components does not have matching connector types." %
                          (dst_obj.name, src_obj.name))
            return (None, None)
        elif len(possible) > 1 and not first:
            connect_error(src_obj.name, dst_obj.name,
                          "More than one connector match in %s and %s." %
                          (dst_obj.name, src_obj.name))
            return (None, None)

    possible.sort()
    possible = possible[0:1]
    src_cnt_obj, dst_cnt_obj = possible[0]
    return (src_cnt_obj, dst_cnt_obj)

def connector_expander(string, obj):
    l = [c.connector_name for c in get_connectors(obj)]
    return get_completions(string, l)

# perform automatic queue changes after hotplug connection
# (both components are instantiated)
def hotplug_connect_propagate_queues(cg, c0, c1):
    (q0, q1) = (c0.queue, c1.queue)
    if q0 == q1 or (q0 is not None and q1 is not None):
        return
    queue = q0 if q0 else q1
    assert queue is not None
    queless = [c for c in cg.topological_sequence()
               if c.instantiated and not c.queue]
    for c in queless:
        c.queue = queue
        for o in c.iface.component.get_slot_objects():
            # Do not assign clocks to port objects (inherited by hierarchy)
            if isinstance(o, conf_object_t) and SIM_port_object_parent(o):
                continue
            if not o.queue:
                o.queue = queue
            # change recorder if the component change cell
            if hasattr(o, "recorder"):
                if (not o.recorder or not o.recorder.queue
                    or o.recorder.queue.cell != queue.cell):
                    from simmod.recorder.api import find_recorder
                    suitable_recorder = find_recorder(queue.cell)
                    o.recorder = suitable_recorder
                    assert o.recorder.queue.cell == o.queue.cell

# c1 was disconnected from c0 (c0 had a connector leading down to c1).
# Remove automatically assigned queues belonging to c0.
def hotplug_disconnect_queues(c1_cg, c0, c1):
    # do nothing if the components use different queues
    queue = c0.queue
    if queue != c1.queue or queue is None or queue.component is None:
        return
    seq = c1_cg.topological_sequence()
    # do nothing if the components are still connected (possibly indirectly)
    # or if the queue is "owned" by the c1 component
    if c0 in seq or queue.component in seq:
        return
    # remove all references to the queue from the non-defining component set
    for c in seq:
        if not c.instantiated or c.queue != queue:
            continue
        c.queue = None
        for o in c.iface.component.get_slot_objects():
            if o.queue == queue:
                o.queue = None

# Return the component tuple associated with the specified connection pair;
# the first  component in the tuple has the "down" connector.
def _connection_components(cnt0, cnt1):
    d0 = cnt0.iface.connector.direction()
    d1 = cnt1.iface.connector.direction()
    if d0 == Sim_Connector_Direction_Down or d1 == Sim_Connector_Direction_Up:
        return (cnt0.component, cnt1.component)
    else:
        return (cnt1.component, cnt0.component)

# two instantiated components have been connected
def hotplug_connect(cnt0, cnt1):
    if inhibit_hotplug_side_effects():
        return
    if _is_standalone_connector(cnt0) or _is_standalone_connector(cnt1):
        return
    (c0, c1) = _connection_components(cnt0, cnt1)
    # c0 has now a connection down to c1
    cg = ComponentGraph([c0, c1])
    hotplug_connect_propagate_queues(cg, c0, c1)
    if c0.top_component and not c1.top_component:
        assign_top_component(cg)
    trigger_hier_change_connection(cnt0, cnt1)

def hotplug_disconnect(cnt0, cnt1):
    if inhibit_hotplug_side_effects():
        return
    if _is_standalone_connector(cnt0) or _is_standalone_connector(cnt1):
        return
    (c0, c1) = _connection_components(cnt0, cnt1)
    c1_cg = ComponentGraph([c1])
    # c0 had a "down" connection to c1
    hotplug_disconnect_queues(c1_cg, c0, c1)
    if c0.top_component and c0.top_component == c1.top_component:
        remove_top_component(c1_cg, c0.top_component)
        assign_top_component(c1_cg)

def trigger_hier_change_connection(cnt0, cnt1):
    if _is_standalone_connector(cnt0) or _is_standalone_connector(cnt1):
        return
    top_objs = [cnt0.component.top_component]
    if cnt0.component.top_component != cnt1.component.top_component:
        top_objs += [cnt1.component.top_component]
    for top_obj in top_objs:
        trigger_hier_change(top_obj)

def connect_cmd(src_obj, src_cnt, dst_obj, dst_cnt, first = False):
    # This function may be called with "src_cnt, NULL, dst_cnt" in two cases:
    # <src_obj>.connect src_cnt dst_obj
    # <src_obj>.connect dst_obj dst_cnt
    #
    if dst_obj == None:
        if src_cnt == None:
            raise CliError("No destination component specified.")

        if get_connector_by_name(src_obj, src_cnt):
            if not dst_cnt:
                raise CliError("No destination component specified.")
            real_obj = dst_cnt
            dst_cnt = None
        else:
            real_obj = src_cnt
            src_cnt = None
        try:
            dst_obj = SIM_get_object(real_obj)
            SIM_get_interface(dst_obj, 'component')
        except:
            raise CliError("Unknown component '%s'" % real_obj)

    # src_cnt and dst_cnt are optional
    if src_cnt == None or dst_cnt == None:
        src_cnt_obj, dst_cnt_obj = find_connectors(src_obj, dst_obj,
                                                   src_cnt, dst_cnt, first)
        if not src_cnt_obj or not dst_cnt_obj:
            return
    else:
        src_cnt_obj = get_connector_by_name(src_obj, src_cnt)
        if not src_cnt_obj:
            connect_error(src_obj.name, dst_obj.name,
                          "Connector %r not found in %r." % (src_cnt, src_obj.name))
        dst_cnt_obj = get_connector_by_name(dst_obj, dst_cnt)
        if not dst_cnt_obj:
            connect_error(src_obj.name, dst_obj.name,
                          "Connector %r not found in %r." % (dst_cnt, dst_obj.name))

    connect_connectors_cmd(src_cnt_obj, dst_cnt_obj)

def delete_cmd(obj):
    # Do not allow links to be deleted while running since that will
    # mess up the simulation
    if SIM_simics_is_running():
        for o in obj.iface.component.get_slot_objects():
            if (not isinstance(o, pre_conf_object)
                and (hasattr(o, 'linkname') or hasattr(o.iface, 'link'))):
                raise CliError("Cannot delete link component while simulation"
                               " is running")

    name = obj.name
    if [c for c in get_connectors(obj) if c.iface.connector.destination()]:
        raise CliError("Cannot delete component with existing connections.")
    try:
        SIM_delete_object(obj)
    except Exception as ex:
        # should not happen unless component broken (do not use CliError)
        raise ComponentError('Failed deleting "%s" component: %s' % (name, ex))

def objects_implementing_iface(iface):
    return list(SIM_object_iterator_for_interface([iface]))

class _ConnectionFinalizer:
    def __init__(self):
        self.delayed = []
        self.handled_cnts = set()

    # Finalize connector leading down to the node (down == True)
    # or finalize connector leading up to a parent node (down == False).
    # Return true if any connection was finalized; otherwise false.
    def _finalize(self, cnts, down):
        finalized_any = False
        if down:
            d1 = Sim_Connector_Direction_Down
            d2 = Sim_Connector_Direction_Up
        else:
            d1 = Sim_Connector_Direction_Up
            d2 = Sim_Connector_Direction_Down
        for (s, d) in ((s, d) for s in cnts
                       for d in s.iface.connector.destination()):
            if down:
                (s, d) = (d, s)
            # this also handles Sim_Connector_Direction_Mixed
            if (s.iface.connector.direction() == d1
                or d.iface.connector.direction() == d2):
                finalized_any |= self._finalize_one(s, d)
        return finalized_any

    # return true if any connection was finalized; otherwise false
    # This function finalized the *source* connector.
    def _finalize_one(self, src_cnt, dst_cnt):
        if (src_cnt, dst_cnt) in self.handled_cnts:
            return False
        self.handled_cnts.add((src_cnt, dst_cnt))

        if not src_cnt.component:
            si = True  # a connector without a component must be a blueprint connector
        else:
            si = src_cnt.component.instantiated
        if not dst_cnt.component:
            di = True
        else:
            di = dst_cnt.component.instantiated
        if not si or not di:
            if di:
                # an instantiated component needs to be provided with
                # real objects, not pre-objects
                self.delayed.append(src_cnt)
                return False
            else:
                _instantiate_log("finalize connection: %s -> %s"
                                 % (src_cnt.name, dst_cnt.name))
                src_cnt.iface.connector.update()
                return True
        else:
            # Connections between two already instantiated components
            # har handled directly. Nothing to do here.
            pass

        return False

    # Users may want to add new destination in finalization stage.
    # So repeat this process until no connection is finalized
    def finalize(self, cgc, seq):
        while True:
            worked = False
            for o in seq:
                worked |= self._finalize(cgc.connectors(o), True)
            for o in reversed(seq):
                worked |= self._finalize(cgc.connectors(o), False)
            if not worked:
                break

    # finalize all delayed connections after all components have been
    # instantiated
    def finalize_delayed_connections(self):
        for c in self.delayed:
            c.iface.connector.update()


def verify_and_name_slot_objects(cmp_obj_list):
    """Go through all slots in all the components in cmp_obj_list and
    make sure the new objects in them have unique names, and that the
    classes they use are known. Return a dictionary mapping names to
    new objects."""
    objs = {}
    for cmp_obj in cmp_obj_list:
        for o in cmp_obj.iface.component.get_slot_objects():
            if isinstance(o, conf_object_t):
                # ignore conf-objects
                continue
            if o.name in objs and o == objs[o.name]:
                # object already in list
                continue
            if o.name in objs or object_exists(o.name):
                # a sequence number for the base-name has already been assigned
                # add this as _<number>
                o._rename(o.name + '_$')
                if o.name in objs or object_exists(o.name):
                    def context():
                        if o.component:
                            return "(in %s [class %s])" % (
                                o.component.name, o.component.classname)
                        else:
                            return ""
                    raise CliError("Failed giving duplicate object a unique"
                                   " name: %s %s" % (o.name, context()))

            objs[o.name] = o

    # make sure all modules are loaded (info in sim namespace)
    # and check that class exist at the same time
    for o in list(objs.values()):
        try:
            SIM_get_class(o.classname)
        except SimExc_General as e:
            if (hasattr(o, 'component') and hasattr(o, 'component_slot')
                and o.component and o.component_slot):
                raise CliError(
                    "Error creating object of class '%s' in slot '%s'"
                    " of component '%s': %s"
                    % (o.classname, o.component_slot, o.component.name, e))
            else:
                raise CliError("Error creating '%s' of class '%s': %s"
                               % (o.name, o.classname, e))
    return objs

def slot_pre_objects(cmp_obj_list):
    """Return a set of all slot objects that are not a conf_object_t."""
    return frozenset(o
                     for cmp_obj in cmp_obj_list
                     for o in cmp_obj.iface.component.get_slot_objects()
                     if not isinstance(o, conf_object_t))

def unused_slot(cp, slot):
    if not cp.iface.component.has_slot(slot):
        return slot
    for i in range(10000):
        new_slot = "%s%d" % (slot, i)
        if not cp.iface.component.has_slot(new_slot):
            return new_slot
    raise CliError("Failed to find an unused slot for %s in component %s"
                   % (slot, cp.name))

def take_over_external_object(cp, ext_obj, slot):
    if not cp.iface.component.add_slot(slot):
        raise CliError("Error adding slot %s to %s" % (slot, cp.name))
    cp.iface.component.set_slot_value(slot, ext_obj)

def find_or_create_default_cell():
    default_cells = [o for o in get_all_cells() if o.default_cell]
    if default_cells:
        return (default_cells[0], False)
    else:
        default_cell = pre_obj("default_cell$", "cell")
        default_cell.default_cell = True
        return (default_cell, True)

# return all queues in component
def queues_in_component(c):
    if c.instantiated:
        queues = [o for o in objects_implementing_iface('cycle')
                  if o.component == c]
    else:
        queues = [o for o in c.iface.component.get_slot_objects()
                   if class_has_iface(o.classname, 'cycle')]
    def sort_by_name(x):
        return x.component_slot if hasattr(x, "component_slot") else x.name
    return sorted(queues, key = sort_by_name)

# return all cells in component
def cells_in_component(c):
    if c.instantiated:
        cells = [o for o in SIM_object_iterator_for_class("cell")
                 if o.component == c]
    else:
        cells = [o for o in c.iface.component.get_slot_objects()
                 if o.classname == 'cell']
    def sort_by_name(x):
        return x.component_slot if hasattr(x, "component_slot") else x.name
    return sorted(cells, key = sort_by_name)

# return all recorders in component
def recorders_in_component(c):
    if c.instantiated:
        recorders = [o for o in SIM_object_iterator_for_class("recorder")
                     if o.component == c]
    else:
        recorders = [o for o in c.iface.component.get_slot_objects()
                     if o.classname == 'recorder']
    def sort_by_name(x):
        return x.component_slot if hasattr(x, "component_slot") else x.name
    return sorted(recorders, key = sort_by_name)


# get the queue in a way that works both for instantiated and
# non-instantiated components
def queue_of_comp(c):
    return c.queue if c.queue or c.instantiated else c.component_queue

class _QueueAssigner:
    def __init__(self, cg):
        self.cgc = cg.cache
        self.seq = cg.topological_sequence()
        self._worked = False
        self.queues = dict((c, queues_in_component(c)) for c in self.seq)
        self._created_objs = dict()
        self.default_cell = None

    # assign a queue to a component
    def _assign(self, c, queue):
        if c.instantiated:
            c.queue = queue
        else:
            c.component_queue = queue
        # setting the queue could fail silently if there is a custom getter
        # for the component_queue attribute which returns None
        self._worked = queue_of_comp(c) == queue

    # assign queues to pre-objects without an assigned queue
    def _set_pre_obj_queues(self, c):
        q = queue_of_comp(c)
        for o in c.iface.component.get_slot_objects():
            if hasattr(o, 'queue'):
                # Don't touch pre_conf objects that the user explicitly
                # has set to None or to a clock.
                pass
            elif class_has_iface(o.classname, 'cycle'):
                o.queue = o
            elif o.classname == 'cell':
                # skip cells
                pass
            elif not isinstance(o, conf_object_t):
                if q:
                    o.queue = q
            else:
                # do not touch conf objects since this will not work anyway
                pass

    # propagate queue upwards using object hierarchy
    def _propagate_hier_up(self, comp, queue):
        while comp.component and not queue_of_comp(comp.component):
            comp = comp.component
            self._assign(comp, queue)

    # propagate queue downwards using object hierarchy
    def _propagate_hier_down(self, comp, queue):
        downs = (c for c in self.cgc.down(comp)
                 if c.component == comp and not queue_of_comp(c))
        for c in downs:
            self._assign(c, queue)
            self._propagate_hier_down(c, queue)

    # propagate queue upwards using (true) up connectors and hierarchy
    def _propagate_conn_up(self, comp, queue):
        # mixed up connectors are not considered here
        ups = (c.component for c in self.cgc.connectors(comp)
               if c.iface.connector.direction() == Sim_Connector_Direction_Up
               if not queue_of_comp(c.component))
        for c in ups:
            self._assign(c, queue)
            self._propagate_hier_up(c, queue)
            self._propagate_hier_down(c, queue)
            self._propagate_conn_up(c, queue)

    # propagate queues upwards using all up connections and hierarchy
    def _propagate_up(self, comp, queue):
        ups = (c for c in self.cgc.up(comp) if not queue_of_comp(c))
        for c in ups:
            self._assign(c, queue)
            self._propagate_up(c, queue)

    # propagate queue downwards using (true) down connectors and hierarchy
    def _propagate_conn_down(self, comp, queue):
        downs = (c.component for c in self.cgc.connectors(comp)
                 if (c.iface.connector.direction()
                     == Sim_Connector_Direction_Down)
                 if not queue_of_comp(c.component))
        for c in downs:
            self._assign(c, queue)
            self._propagate_conn_down(c, queue)
            self._propagate_hier_up(c, queue)
            self._propagate_hier_down(c, queue)

    # propagate queue downwards using down connectors and hierarchy
    def _propagate_down(self, comp, queue):
        downs = (c for c in self.cgc.down(comp) if not queue_of_comp(c))
        for c in downs:
            self._assign(c, queue)
            self._propagate_down(c, queue)

    # assign fallback queue to disconnected objects without up connectors
    def _assign_default_queues(self):
        first_queues = (self.queues[c][0] for c in self.seq if self.queues[c])
        fallback_queue = next(first_queues, VT_first_clock())
        for c in self.seq:
            if not queue_of_comp(c):
                ups = [x for x in get_connectors(c)
                       if (x.iface.connector.direction()
                           == Sim_Connector_Direction_Up)]
                if not ups:
                    if not fallback_queue:
                        SIM_log_error(c, 0,
                                      "Could not find a suitable clock")
                    else:
                        self._assign(c, fallback_queue)

    # perform queue assignment
    def assign_queues(self):
        # assign queues to components which create queues
        for (c, q) in self.queues.items():
            if q and not queue_of_comp(c):
                self._assign(c, q[0])

        def propagate(up, propagate_callback):
            s = reversed(self.seq) if up else self.seq
            for c in s:
                q = queue_of_comp(c)
                if q:
                    propagate_callback(c, q)

        # the loop is needed to handle e.g. W-shaped configs
        self._worked = True
        while self._worked:
            self._worked = False
            propagate(True, self._propagate_hier_up)
            propagate(False, self._propagate_hier_down)
            propagate(False, self._propagate_conn_down)
            propagate(False, self._propagate_down)
            propagate(True, self._propagate_conn_up)
            propagate(True, self._propagate_up)

            if not self._worked:
                self._assign_default_queues()

        # set queues on pre objects
        for c in self.seq:
            if not c.instantiated:
                self._set_pre_obj_queues(c)

    def create_cells(self):
        for c in self.seq:
            if c.instantiated or not c.iface.component.create_cell():
                continue
            # create a machine object
            cell_slot = unused_slot(c, "cell")
            cell = pre_obj_noprefix(c.name + "." + cell_slot, "cell")
            domain = getattr(c, 'domain', None)
            if domain:
                cell.sync_domain = domain
            self._created_objs[cell.name] = cell
            take_over_external_object(c, cell, cell_slot)

        # and assign clocks to the cells
        self._assign_queues_to_cells()
        return []

    def _assign_queues_to_cells(self):
        cells = dict((c, cells_in_component(c)) for c in self.seq)
        def lookup_cell(comp):
            if cells[comp]:
                return cells[comp][0]
            for c in self.cgc.up(comp):
                cell = lookup_cell(c)
                if cell:
                    return cell
            # use default cell
            if self.default_cell:
                return self.default_cell
            (cell, is_new) = find_or_create_default_cell()
            self.default_cell = cell
            if is_new:
                self._created_objs[cell.name] = cell
            return cell

        # assign cells
        for (c, queues) in self.queues.items():
            if queues:
                cell = lookup_cell(c)
                for q in queues:
                    if isinstance(q, conf_object_t):
                        continue
                    if hasattr(q, "cell") and q.cell:
                        continue
                    q.cell = cell

    # Look for unset 'recorder' attributes in the pre-objects.
    # If no suitable recorder is found, a new pre-object is create
    def assign_recorders(self):
        cellmap = None  # will be populated only if needed
        for c in self.seq:
            if c.instantiated:
                continue

            missing = [o for o in c.iface.component.get_slot_objects()
                       if SIM_class_has_attribute(o.classname, "recorder")
                       if not hasattr(o, 'recorder')]

            if missing and cellmap is None:
                cellmap = dict()
                def get_recorder_cell(r):
                    if isinstance(r, conf_object_t):
                        # ignore (manually created) recorders without queue
                        return r.queue.cell if r.queue else None
                    return r.queue.cell
                for comp in self.seq:
                    for r in recorders_in_component(comp):
                        cellmap.setdefault(get_recorder_cell(r), r)

            for m in missing:
                self._set_recorder(m, cellmap)

    def _set_recorder(self, o, cellmap):
        from simmod.recorder.api import (get_one_recorder_from_cell,
                                         new_recorder_name)

        # Find the default cell if any. Do not depend on the queue to
        # have a cell, it can happen if the user has set queue to a
        # non-cycle object.
        if hasattr(o, "queue") and o.queue and hasattr(o.queue, "cell"):
            cell = o.queue.cell
        else:
            cell = None

        if cell:
            rec = cellmap.get(cell)
            if not rec:
                rec = get_one_recorder_from_cell(cell)
        else:
            # if the component is standalone without queue, just pick
            # a random recorder. It will be set to a recorder in the
            # correct cell, when the component is connected.
            recs = list(SIM_object_iterator_for_class('recorder'))
            rec = recs[0] if recs else None

        # if no suitable recorder was found, create a new one.
        # Create it on the top level of the namespace, since other objects may
        # refer to it too in the future and then we can't remove
        # it at the same time as the component.
        if not rec:
            rec = pre_obj(new_recorder_name(cell), "recorder")
            cellmap[cell] = rec
            if hasattr(o, "queue"):
                rec.queue = o.queue
            self._created_objs[rec.name] = rec

        # assign recorder
        o.recorder = rec

    def created_objects(self):
        return self._created_objs


is_instantiating = False

def instantiate_cmd(verbose, cmps):
    global is_instantiating
    if is_instantiating:
        # Allow since we've seen it at some user, but warn.
        print("ERROR: Recursive call to instantiate components not allowed!")
    is_instantiating = True
    try:
        return _instantiate_cmd(verbose, cmps)
    finally:
        is_instantiating = False

# assign top component field for all components
def assign_top_component(cg):
    for c in cg.topological_sequence():
        # already set?
        if c.top_component:
            continue
        r = cg.component_root(c)
        if r.top_level:
            c.top_component = r
            r.components += [c]

# remove top_component references to the specified top component
def remove_top_component(cg, top_component):
    for c in cg.topological_sequence():
        if c.top_component == top_component:
            c.top_component = None
            top_component.components.remove(c)


# look for unresolved object factories in the attribute and resolve them
def _resolve_attr_rec(attr, cell):
    if is_cell_object_factory(attr):
        (magic, obj, link_name, frequency, latency) = attr
        na = get_component(obj).resolve(cell, link_name, frequency, latency)
        return (na, [na])
    elif isinstance(attr, list):
        nlist = []
        nobjs = []
        for a in attr:
            (an, ao) = _resolve_attr_rec(a, cell)
            nlist.append(an)
            nobjs += ao
        return (nlist, nobjs)
    elif isinstance(attr, dict):
        ndict = {}
        nobjs = []
        for (a,b) in attr:
            an, ao = _resolve_attr_rec(a, cell)
            bn, bo = _resolve_attr_rec(b, cell)
            ndict[an] = bn
            nobjs += ao + bo
        return (ndict, nobjs)
    else:
        return (attr, [])

def resolve_factories_in_attribute(owner, attr_name):
    cell = owner.queue.cell if hasattr(owner.queue, 'cell') else None
    (attr, nobjs) = _resolve_attr_rec(getattr(owner, attr_name), cell)
    setattr(owner, attr_name, attr)
    return [n for n in nobjs if not isinstance(n, conf_object_t)]

def required_connectors_filled(cmp_obj):
    req_cnts = [c for c in get_connectors(cmp_obj)
                if c.iface.connector.required()]
    for r in req_cnts:
        if not r.iface.connector.destination():
            return False
    return True

def components_to_instantiate(cmps):
    cgc = ComponentGraphCache()
    for c in cmps:
        if not hasattr(c.iface, 'component'):
            raise CliError("'%s' is not a component." % c.name)
    if not cmps:
        # all uninstantiated components which can be instantiated
        cmps = [c for c in objects_implementing_iface('component')
                if not c.instantiated
                if cgc.ready(c)]
    return ComponentGraph(cmps, cgc)

def _instantiate_log(msg):
    SIM_log_info(4, conf.sim, 0, "instantiate command: %s" % msg)

def all_known_interfaces():
    return set.union(*(set(VT_get_interfaces(c))
                       for c in SIM_get_all_classes()))

def _instantiate_cmd(verbose, cmp_objs):
    # obtain the ComponentGraph object describing the graph to instantiate
    cg = components_to_instantiate(cmp_objs)
    cgc = cg.cache

    # nothing to do?
    seq = cg.topological_sequence()
    if not any(o for o in seq if not o.instantiated):
        return command_return(message = "No components to instantiate.")

    if cg.cycle_nodes():
        SIM_log_info(1, conf.sim, 0,
                     "connector cycle detected involving "
                     + " ".join(o.name for o in cg.cycle_nodes()))

    _instantiate_log("components found: %s" % list(cg.roots))

    # ensure that all required connections are present
    not_ready = next((o for o in seq if not cgc.ready(o)), None)
    if not_ready:
        raise CliError("The %s component has empty required connectors"
                       % not_ready.name)

    # set top_component for all components in the component graph
    assign_top_component(cg)

    # keep track of what happens to connections in the tree of components we
    # want to instantiate
    cf = _ConnectionFinalizer()
    cf.finalize(cgc, seq)

    all_uninstantiated = [o for o in seq if not o.instantiated]
    _instantiate_log("components to instantiate: %r" % all_uninstantiated)

    # check that all components permit the instantiation
    failing_comp = next((o for o in all_uninstantiated
                         if not o.iface.component.pre_instantiate()), None)
    if failing_comp:
        raise CliError("The %s component cannot be instantiated" %
                       failing_comp.name)

    # Calling verify_and_name_slot_objects has the side effect of loading
    # all classes so we can query Simics about those later.
    objs = verify_and_name_slot_objects(all_uninstantiated)

    qa = _QueueAssigner(cg)
    qa.assign_queues()

    # create cells
    qa.create_cells()

    # assign/create recorders
    qa.assign_recorders()

    # keep track of new pre-objects to be instantiated
    objs.update(qa.created_objects())

    #
    # Now that cells and queues are set, resolve all pending object factories
    #
    for c in all_uninstantiated:
        for (owner_name, attr) in sorted(set([(o, a) for (o, a) in c.pending_cell_object_factories])):
            owner = cmputil.cmp_get_indexed_slot(c, owner_name)
            new_objs = resolve_factories_in_attribute(owner, attr)
            for o in new_objs:
                if not o.name in objs:
                    SIM_get_class(o.classname)
                    objs[o.name] = o
        c.pending_cell_object_factories = []

    #
    # Set component and component_slot attribute
    #
    _instantiate_log("setting component and component_slot")
    if 'cycle' not in all_known_interfaces():
        raise CliError("No cycle queues defined, cannot set configuration.")

    try:
        _instantiate_log("create all objects")
        pre_objs = list(objs.values())
        if pre_objs:
            conf_objs = VT_add_objects(pre_objs)
            for i, o in enumerate(pre_objs):
                set_pre_obj_object(o, conf_objs[i])
    except Exception as ex:
        # If adding objs to the configuration fails, the components are buggy
        # and there is no use keeping them around.
        # should not happen unless component broken (do not use CliError)
        try:
            SIM_delete_objects(list(all_uninstantiated))
        finally:
            # make sure errors in SIM_delete_objects do not hide the original
            raise CliError('Failed setting configuration: %s' % ex)

    try:
        for cmp_obj in sorted(all_uninstantiated, key=lambda o: o.name):
            if not cmp_obj.queue and cmp_obj.component_queue:
                cmp_obj.queue = get_pre_obj_object(cmp_obj.component_queue)
            if verbose:
                print("Instantiating:", cmp_obj.name)

        # do final instantiation now when all pre_objs are converted,
        # this makes it possible for components to access slots in
        # other components from post_instantiate
        #
        # some stupid written components requires that the top component
        # is instantiated first, that is why we have to sort all components
        for cmp_obj in all_uninstantiated:
            if not cmp_obj.iface.component.post_instantiate:
                # should not happen unless component broken
                # (do not use CliError)
                raise ComponentError("The %s component did not implement the "
                                     "post_instantiate() method."
                                     % cmp_obj.name)
            # do component special instantiation
            cmp_obj.iface.component.post_instantiate()
            # mark component instantiated
            cmp_obj.instantiated = True
            # trigger hap

        # Find the top-component for all newly added components (the top may
        # not be included in "all". Also trigger hap for components without
        # any top-component
        all_tops = set((x.top_component for x in all_uninstantiated
                        if x.top_component))
        for comp in all_tops:
            # Only report top level components that are instantiated in this
            # call, not ones from earlier instantiations.
            if comp in all_uninstantiated:
                # For now the top-component class is how we track platform usage
                VT_add_telemetry_data("core.platform", "top_level_classes+",
                                      comp.classname)
                VT_add_telemetry_data_int("core.platform",
                                          "num-top-level-comp&", 1)
            trigger_hier_change(comp)
        no_tops = [x for x in all_uninstantiated if not x.top_component]
        if no_tops:
            trigger_hier_change(None)

    except Exception as ex:
        import traceback
        traceback.print_exc(file = sys.stdout)
        # should not happen unless component broken (do not use CliError)
        raise ComponentError("Unexpected error when instantiating component: "
                             "%s" % ex)

    # finalize now the delayed connections that we left for after instantiation
    cf.finalize_delayed_connections()

    VT_add_telemetry_data_int("core.platform", "num-components&",
                              len(all_uninstantiated))

    # Friendly warning about components not instantiated
    left = [x for x in objects_implementing_iface('component')
            if not x.instantiated]
    _instantiate_log("not instantiated components: %r" % left)
    if verbose:
        for l in left:
            print("Component not instantiated: %s" % l.name)

def component_list(component, comp_class, top_only, all_flag, recursive):
    cmps = visible_objects(iface = 'component', all = all_flag,
                           component = component, recursive = recursive)
    def filt(d, p): return dict((s, o) for (s, o) in d.items() if p(o))
    if top_only:
        cmps = filt(cmps, lambda o: o.top_level)
    if comp_class:
        cmps = filt(cmps, lambda o: o.classname == comp_class)
    return cmps

def list_components_cmd(component, comp_class, short, verbose, top_only,
                        all_flag, recursive):
    cmps = component_list(component, comp_class, top_only, all_flag, recursive)
    def components_cmd_string():
        if not cmps:
            return  'There are no%s components.' % (' such'
                                                    if component or comp_class
                                                    else '')
        data = []
        header = ["Component", "Class", "", ""]
        for slot, comp in cmps.items():
            inst = "not instantiated" if not comp.instantiated else ""
            if not verbose:
                data.append([slot, comp.classname, inst, ""])
                continue

            # The extra padding because table counts the invisible escape code
            # for bold in len(string) and adjust column widths based on that
            data.append(["%s" % slot, comp.classname, inst, ""])
            for cnt in sorted(get_connectors(comp)):
                cnt_name = " %s" % cnt.connector_name
                cnt_type = "%s" % cnt.iface.connector.type()
                cnt_dir  = "%s" % convert_direction(cnt.iface.connector.direction())
                cnt_dest = ""
                dst = cnt.iface.connector.destination()
                if dst:
                    for i in range(len(dst)):
                        cnt_dest += "%s:%s, " % (dst[i].component.name,
                                                 dst[i].connector_name)
                    cnt_dest = cnt_dest[:-2]  # erase trailing ", "

                data.append([cnt_name, cnt_type, cnt_dir, cnt_dest])

        props = [(Table_Key_Columns, [[(Column_Key_Name, n),
                                       (Column_Key_Alignment, "left"),
                                       (Column_Key_Hide_Homogeneous, "")]
                                      for n in header])]
        tbl = table.Table(props, data)
        border = conf.prefs.cli_table_border_style
        return tbl.to_string(border_style=border,
                             no_row_column=True,
                             rows_printed=0)

    return cli.command_verbose_return(
        message=components_cmd_string(),
        value=sorted(set(x for x in cmps.values())))

def get_object_cmd(comp, obj_name):
    try:
        return expand_component_object(comp, obj_name)
    except AttributeError:
        raise CliError("Component %s contains no '%s' object" % (comp.name,
                                                                 obj_name))
def object_list_expander(string, comp):
    return get_completions(string, list(comp.object_list.keys()))

new_command('get-component-object', get_object_cmd,
            [arg(str_t, 'object', expander = object_list_expander)],
            short = 'get named object from components',
            iface = 'component',
            type = ["Components"],
            doc = ('Get the configuration object with name <arg>object</arg> '
                   'from the component. This is similar to the . operator.'))

new_command('delete', delete_cmd,
            [],
            short = 'delete non-instantiated components',
            iface = 'component',
            type = ["Components"],
            doc = ('Delete the component. The component may '
                   'not be connected to any other component. Deleting a '
                   'non-instantiated component should work without any problem. '
                   'Deleting an instantiated component requires that all objects '
                   'in the component supports deletion.'))

def get_connector_list_cmd(obj, type, c, u, r, w):
    if c == u:
        con = None
    else:
        con = bool(c)

    def cnt_filter(cnt, t, c):
        return ((t == None or cnt.iface.connector.type() == t)
                and (c == None
                     or (c and cnt.iface.connector.destination())
                     or (not c and not cnt.iface.connector.destination())))

    def list_subcomponents(root_obj):
        itt = SIM_object_iterator(root_obj)

        connector_list = []

        for obj in itt:
            try:
                connectors = get_connectors(obj)
                for connector in connectors:
                    if cnt_filter(connector, type, con):
                        connector_list.append(connector.name)
            except:
                continue

        return connector_list

    def walk_connected_connectors(curr_obj, visited, connector_list):
        if id(curr_obj) in visited:
            return

        visited.add(id(curr_obj))

        connectors = get_connectors(curr_obj)
        for connector in connectors:
            if cnt_filter(connector, type, con):
                connector_list.append(connector.name)

            try:
                if connector.destination:
                    dest_obj = connector.destination[0].component
                    (visited, connector_list) = walk_connected_connectors(dest_obj,
                                                                          visited,
                                                                          connector_list)
            except:
                continue

        return (visited, connector_list)

    if r:
        return sorted(list_subcomponents(obj))
    elif w:
        connector_list = []
        (visited, connector_list) = walk_connected_connectors(obj, set(), connector_list)
        return sorted(connector_list)
    else:
        return sorted(c.connector_name for c in get_connectors(obj)
                      if cnt_filter(c, type, con))

def get_processor_list_cmd(obj):
    if not obj.top_level:
        raise CliError("%s is not a top-level component" % obj.name)
    return sorted(x.name for x in obj.cpu_list)

new_command('get-connector-list', get_connector_list_cmd,
            [arg(str_t, 'connector-type', '?', None),
             arg(flag_t, '-c'),
             arg(flag_t, '-u'),
             arg(flag_t, "-r"),
             arg(flag_t, "-w")],
            short = 'return list of connectors',
            iface = 'component',
            type = ["Components"],
            doc = ('Return a list of all connectors for the component. If '
                   '<arg>connector-type</arg> is given, only connectors '
                   'of that type are returned. The <tt>-c</tt> flag limits '
                   'the list to connected connectors and <tt>-u</tt> only '
                   'return unconnected ones. Use <tt>-w</tt> to walk through'
                   'connected components depth-first. You can also use '
                   '<tt>-r</tt> to recursively list all sub-component '
                   'connectors.'))

new_command('get-processor-list', get_processor_list_cmd,
            [],
            short = 'return list of processors',
            iface = 'component',
            type = ["Components"],
            doc = ('Return a list of all processors that are part of the '
                   'component hierarchy defined by this top-level component. '
                   'This command is only applicable to top-level components.'))

def get_connection_cmd(src_obj, src_cnt):
    cnt = get_connector_by_name(src_obj, src_cnt)
    if cnt:
        dst = cnt.iface.connector.destination()
        if len(dst) == 0:
            return []
        elif len(dst) == 1:
            return [dst[0].component.name, dst[0].connector_name]
        else:
            return [[c.component.name, c.connector_name] for c in dst]
    else:
        raise CliError("%s has no %s connector." % (src_obj.name, src_cnt))

new_command('get-connection', get_connection_cmd,
            [arg(str_t, 'connector', expander = connector_expander)],
            short = 'return connection information',
            iface = 'component',
            type = ["Components"],
            doc = ('Return information about the component connected to the '
                   'selected <arg>connector</arg>. The return value is '
                   'either an empty list, a list of two items, or a list of '
                   'a list of two items for multi connections. The list of '
                   'two items are the name of the other component and the '
                   'other connector.'))

def get_free_connectors(cnts, cnt_type, cnt_dir):
    return [c.name for c in cnts if (
        # find connections that support multi or are unconnected
        (c.iface.connector.multi() or not c.iface.connector.destination())
        and
        # find connectors that are not copied.
        (not hasattr(c, 'child') or not c.child)
        and
        # find connections of the same type
        (cnt_type == None or c.iface.connector.type() == cnt_type)
        and
        # find matching direction
        (convert_direction(c.iface.connector.direction()) in (cnt_dir, 'any'))
    )]

def get_available_connector_cmd(comp, cnt_type, cnt_dir):
    cnt_dirs = (cnt_dir,) if cnt_dir else ("down", "up")
    cnts = list(visible_objects('connector', False, comp, True).values())
    for direction in cnt_dirs:
        avail = cli.get_completions(
            comp.name, get_free_connectors(cnts, cnt_type, direction))
        if avail:
            return avail[0]
    return None

def available_connector_types_exp(string):
    types = set()
    for c in SIM_object_iterator_for_class('connector'):
        types.add(c.type)
    return cli.get_completions(string, list(types))

def direction_expander(string):
    return cli.get_completions(string, ['up', 'down'])

new_command('get-available-connector', get_available_connector_cmd,
            [arg(str_t, 'type', expander = available_connector_types_exp),
             arg(str_t, 'direction', '?', expander = direction_expander)],
            short = 'returns the name of a free connector',
            iface = 'component',
            type = ['Components'],
            see_also = ['connect', '<component>.connect-to'],
            doc = """
Return the name of a free connector of type <arg>type</arg> found within the
component and its children. The direction of the connector to search for can be
selected using <arg>direction</arg> ("up" or "down"). If no direction is
specified, the command will first search for down connectors and then up
connectors,  returning the first match. Connectors supporting any direction
will always match.

If no free connector is found, NIL is returned.

The following example connects a text console component to each serial
connector in a system represented by the <tt>board</tt> top-level
component:<br/>
<pre>
while (board.get-available-connector serial) {
    connect (board.get-available-connector serial) (
            (new-txt-console-comp).get-available-connector serial)
}
</pre>
""")

# select connectors with a specified direction over 'any' connectors to
# reduce the risk of ending up with an (illegal) any to any connection
def preferred_connector(cnt_list):
    # In a machine with both legacy PCI and PCI-E, a PCI-E device must not be
    # connected to a legacy PCI connector. However there is no good way to
    # determine the kind, since both have the type 'pci-bus'. As a workaround,
    # sort connectors with pcie_ in the name before ones with pci_. This works
    # on our QSP, X58 and MCH5100 systems. It will break once all PCI-E
    # connectors are occupied, if some other naming is used or if the system has
    # legacy PCI connectors only.
    cnt_list = sorted(cnt_list, key = lambda x: 'pcie_' not in x)
    for cnt in (SIM_get_object(x) for x in cnt_list):
        if cnt.direction != Sim_Connector_Direction_Any:
            return cnt
    # if only any connectors, just pick one
    return SIM_get_object(cnt_list[0]) if cnt_list else None

def connect_to_matching_cmd(src, dst, usr_cnt_type, direction):
    src_cnts = sorted(list(visible_objects('connector',
                                           False, src, True).values()))
    dst_cnts = sorted(list(visible_objects('connector',
                                           False, dst, True).values()))
    # Most common case is adding a component to an existing hierarchy, so look
    # for up connector first (in src component) unless the user has specified
    # a direction explicitly.
    dirs = (direction,) if direction else ('up', 'down')
    for dir in dirs:
        if usr_cnt_type:
            #cnt_type = usr_cnt_type
            types = [usr_cnt_type]
        else:
            # find type of connector to use based on direction and what is
            # available in the src component
            types = set([SIM_get_object(x).iface.connector.type()
                         for x in get_free_connectors(src_cnts, None, dir)])
            #if len(types) > 1:
            #    raise CliError('More than one connector type in %s: %s'
            #                   % (src.name, " ".join(types)))
            #elif len(types) == 0:
            #    # No free connectors, try other direction
            #    continue
            #cnt_type = types.pop()
        matches = {}
        for cnt_type in types:
            odir = 'down' if dir == 'up' else 'up'
            src_cnt = preferred_connector(cli.get_completions(
                src.name, get_free_connectors(src_cnts, cnt_type, dir)))
            dst_cnt = preferred_connector(cli.get_completions(
                dst.name, get_free_connectors(dst_cnts, cnt_type, odir)))
            # avoid any-to-any connections
            if (src_cnt and dst_cnt
                and (src_cnt.iface.connector.direction()
                     != dst_cnt.iface.connector.direction())):
                matches[cnt_type] = (src_cnt, dst_cnt)
        if len(matches) == 1:
            (_, (src_cnt, dst_cnt)) = matches.popitem()
            break
        elif len(matches) > 1:
            raise CliError('More than one connector type in %s: %s'
                           % (src.name, " ".join(matches)))
        else:
            src_cnt = dst_cnt = None
    if (src_cnt == None
        or dst_cnt == None
        or (src_cnt.iface.connector.direction()
            == dst_cnt.iface.connector.direction())):
        raise CliError("No matching connectors found in %s and %s" %
                       (src.name, dst.name))
    connect_connectors_cmd(src_cnt, dst_cnt)
    return command_return(message = "Connecting %s to %s" %
                          (src_cnt.name, dst_cnt.name))

def comp_expander(substr):
    return get_completions(
        substr, (x.name for x in objects_implementing_iface('component')))

new_command('connect-to', connect_to_matching_cmd,
            [arg(obj_t('component', 'component'), 'dst',
                 expander = comp_expander),
             arg(str_t, 'type', '?', None,
                 expander = available_connector_types_exp),
             arg(str_t, 'direction', '?', None,
                 expander = direction_expander)],
            short = 'connect component into an existing component hierarchy',
            iface = 'component',
            type = ['Components'],
            see_also = ['connect', '<component>.get-available-connector'],
            doc = """
Connect the component into an existing component hierarchy, represented by
<arg>dst</arg>. The command will search the hierarchy for connectors that match
the connectors of the source component. Since the main use of the command is to
extend hierarchies, connectors with the <em>up</em> direction in the source
component will be matched first.

If there are connectors of different types that match, the <arg>type</arg>
argument can select the one to use. Similarly it is possible to force the
command to only consider connectors in one direction by specifying
<arg>direction</arg>, that can be one of <tt>up</tt> and <tt>down</tt>.

The <cmd class="component">connect-to</cmd> command is useful when the exact
location of a connection in the system does not matter. The following is an
example of inserting a PCI-based Ethernet device into a simulated machine whose
top-level component is called <tt>board</tt>:<br/>
<pre>
$eth = (create-pci-i82543gc-comp mac_address = "10:20:30:40:50:60")
$eth.connect-to board
instantiate-components
</pre>
""")

# Return a template pre-conf object from an actual object (component
# or connector).
def template_of_object(obj):
    cls = obj.classname
    omitted_attrs = {"queue"}
    if SIM_class_has_attribute(cls, "nontemplate_attributes"):
        omitted_attrs |= set(SIM_get_class_attribute(cls,
                                                     "nontemplate_attributes"))
    p = pre_conf_object(obj.name, cls)
    for attr in VT_get_attributes(cls):
        if attr in omitted_attrs:
            continue
        aa = (SIM_get_attribute_attributes(obj.classname, attr)
              & Sim_Attr_Flag_Mask)
        if aa == Sim_Attr_Pseudo:
            continue
        setattr(p, attr, SIM_get_attribute(obj, attr))
    return p

def save_template(filename):
    print("Writing component template '%s'." % filename)
    set_writing_template(True)
    try:
        pobjs = {}
        for c in objects_implementing_iface("component"):
            if is_component_hardware(c):
                p = template_of_object(c)
                pobjs[p.name] = p
        for p in map(template_of_object,
                     objects_implementing_iface("connector")):
            p.old_destination = []
            pobjs[p.name] = p
        try:
            CORE_write_pre_conf_objects(filename, pobjs,
                                        Sim_Save_No_Gzip_Config)
        except Exception as e:
            raise CliError("Failed writing component template to file: %s."
                           % e)
    finally:
        set_writing_template(False)


new_command('save-component-template', save_template,
            [arg(filename_t(), 'file')],
            type  = ["Components", 'Configuration'],
            short = 'save a component configuration template',
            see_also = ['read-configuration', 'write-configuration',
                        'list-components'],
            doc = """
Save a configuration to <arg>file</arg> with only component objects and their
connection information. OS Awareness trackers are not included in this
list. This template corresponds to an empty machine configuration,
without any software setup. The saved component template can be loaded
into Simics using the <cmd>read-configuration</cmd> command, producing
a collection of non-instantiated components.
""")

new_command('instantiate-components', instantiate_cmd,
            [arg(flag_t, '-v'),
             arg(obj_t('component', 'component'), 'component', '*')],
            short = 'instantiate components',
            type = ["Components"],
            doc = """
Instantiate all non-instantiated top-level components, or just the given
<arg>component</arg> (one or more). In both cases also their sub-components
are instantiated.

With the <tt>-v</tt> flag names of the instantiated components are printed.

Instantiating components will discard any reverse execution history.""")

def save_instantiation_info(filename):
    import pprint
    comps = set(component_list(None, None, False, False, True).values())

    def update_set(a, b):
        a.update(b)
        return a
    subcomps = reduce(
        update_set,
        (iter(cmputil.flatten_slot_dictionary(x.static_slots).values())
         for x in comps
         if hasattr(x, 'static_slots')),
        set())

    f = file(filename, 'w')
    print('components = \\', file=f)
    print('set(', end=' ', file=f)
    pprint.pprint(sorted(x.classname for x in (comps - subcomps)), f, 2)
    print(')', file=f)
    f.close()

new_unsupported_command('save-instantiation-info', "internals",
                        save_instantiation_info, [arg(filename_t(), 'file')],
                        short = 'save instantiation info to file',
                        doc = '''
Save information about all created but non-instantiated components to
<arg>file</arg>.''')

def comp_class_expander(str):
    return get_completions(str, set(x.classname for x in
                                    objects_implementing_iface('component')))

component_list_doc_common = """
Print or lists components with their names, types, and connectors; and for
each connector, the destination component and connector.

With the <arg>class</arg> argument, you can restrict the listing to components
of a particular class.

By default, only the components in the current namespace are listed (see the
<cmd>change-namespace</cmd> command). If no current namespace has been
selected, only top-level components are shown. The <arg>component</arg>
argument can be used to override the current namespace.

With the <tt>-all</tt> flag, list all components, regardless of where they
live. With the <tt>-recursive</tt> flag, in addition to listing all components
that are in the selected namespace, also list all components in the namespaces
below it. With <tt>-t</tt>, list only top-level components."""

new_command('list-components', list_components_cmd,
            [arg(obj_t('component', 'component'), 'component', '?'),
             arg(str_t, 'class', '?', expander = comp_class_expander),
             arg(flag_t, '-s'), arg(flag_t, '-v'),
             arg(flag_t, '-t'), arg(flag_t, '-all'),
             arg(flag_t, '-recursive')],
            short = 'print components',
            type = ["Components"],
            doc = "%s%s" % (component_list_doc_common,
"""
The <tt>-s</tt> and <tt>-v</tt> flags select a briefer listing (default),
and a more verbose listing, respectively.

Example of default output. Columns are explained by the bottom row.
<pre>
board            chassis_qsp_x86
ethernet_switch0 ethernet_switch
slot             class name       not instantiated, if applicable
</pre>

Example of verbose output. Components are printed in bold and columns for the
connectors are explained by the bottom row:
<pre>
<b>board            chassis_qsp_x86</b>

<b>ethernet_switch0 ethernet_switch</b>
device0          ethernet-link    any         board.mb.sb:eth_slot
device1          ethernet-link    any         service_node_cmp0:connector_link0
connector        type             direction   destinations, if any
</pre>

The <cmd>list-components</cmd> command returns a list of components
when used in an expression."""))

def connect_connectors_cmd(cnt0, cnt1):

    if not cli.is_connector(cnt0):
        raise CliError("%r is not a connector" % cnt0)
    if not cli.is_connector(cnt1):
        raise CliError("%r is not a connector" % cnt1)

    # same connector
    if cnt0 == cnt1:
        raise CliError("not allowed to connect %s to itself" %
                       (print_connector(cnt0)))

    # check connector types
    if cnt0.iface.connector.type() != cnt1.iface.connector.type():
        raise CliError("connector type mismatch for %s and %s" %
                       (print_connector(cnt0), print_connector(cnt1)))

    # check direction
    if cnt0.iface.connector.direction() == cnt1.iface.connector.direction():
        raise CliError("Connector direction mismatch for %s and %s." %
                       (print_connector(cnt0), print_connector(cnt1)))

    # check connectors are available
    if not cnt0.iface.connector.multi() and cnt0.iface.connector.destination():
        raise CliError("Connector %s already used." % print_connector(cnt0))
    if not cnt1.iface.connector.multi() and cnt1.iface.connector.destination():
        raise CliError("Connector %s already used." % print_connector(cnt1))

    c0_inst = _connector_instantiated(cnt0)
    c1_inst = _connector_instantiated(cnt1)

    # check connecting to an instantiated component with a non-hotpluggable
    # connector
    if c0_inst and not cnt0.iface.connector.hotpluggable():
        raise CliError("Not allowed to connect to non-hotpluggable connector %s "
                       "as its owner component %s is instantiated." %
                       (print_connector(cnt0), cnt0.owner.name))
    if c1_inst and not cnt1.iface.connector.hotpluggable():
        raise CliError("Not allowed to connect to non-hotpluggable connector %s "
                       "as its owner component %s is instantiated." %
                       (print_connector(cnt1), cnt1.owner.name))

    # check connecting an instantiated up connector to non instantiated
    # down connector
    if ((c0_inst and not c1_inst
         and cnt0.iface.connector.direction() == Sim_Connector_Direction_Up)
        or (not c0_inst and c1_inst
         and cnt1.iface.connector.direction() == Sim_Connector_Direction_Up)):
        raise CliError("Cannot connect instantiated and non-instantiated "
                       "components when the up connector component is instantiated.")

    # it is not possible to connect to copied connectors, i.e connectors with children
    for c in [cnt0, cnt1]:
        if hasattr(c, 'child') and c.child:
            def _get_child(c):
                if not c.child:
                    return ""
                ret = c.child.name
                if c.child.child:
                    ret += " -> " + _get_child(c.child)
                return ret
            raise CliError("Cannot connect to %s as it has been copied, connect "
                           "to %s instead" % (print_connector(c), _get_child(c)))

    # try adding connectors
    if not cnt0.iface.connector.add_destination(cnt1):
        raise CliError("Adding %s to %s failed." %
                       (print_connector(cnt0), print_connector(cnt1)))
    if not cnt1.iface.connector.add_destination(cnt0):
        cnt0.iface.connector.remove_destination(cnt1)
        error_string = "Adding %s to %s failed." % (
            print_connector(cnt1), print_connector(cnt0))
        # handle the fact that cnt0 might request its own deletion at this
        # point
        if (cnt0.iface.connector.deletion_requested and
            cnt0.iface.connector.deletion_requested()):
            SIM_delete_objects([cnt0])
        raise CliError(error_string)

    # update if both components are instantiated
    if c0_inst and c1_inst:
        if (cnt0.iface.connector.direction() == Sim_Connector_Direction_Down or
            cnt1.iface.connector.direction() == Sim_Connector_Direction_Up):
            cnt0.iface.connector.update()
            cnt1.iface.connector.update()
        else:
            cnt1.iface.connector.update()
            cnt0.iface.connector.update()
        # automatic queue and recorder assignment
        hotplug_connect(cnt0, cnt1)
    else:
        trigger_hier_change_connection(cnt0, cnt1)

class cnt_t(obj_t):
    def __init__(self, desc, kind=None, want_port=False):
        obj_t.__init__(self, desc, kind, want_port)
    def expand(self, s):
        print(s)

def get_connect_cnts(cnts, obj = None):
    return [k for (k, c) in cnts.items() if (
        # find connections that support multi or are unconnected
        (c.iface.connector.multi() or not c.iface.connector.destination())
        and
        # find connectors that are not copied
        (not hasattr(c, 'child') or not c.child)
        and
        # find connections of the same type
        (not obj or c.iface.connector.type() == obj.iface.connector.type())
        and
        # find (up -> down, any), (down -> up, any), (any -> up, down)
        (not obj or c.iface.connector.direction() != obj.iface.connector.direction())
        and
        # remove obj from set
        (not obj or obj != c)
        )]

def connect_exp(comp, lst, prev):
    other = [o for o in prev if o]
    vo = visible_objects(iface = 'connector', recursive = True)
    if other:
        obj = other[0]
        return cli.get_completions(comp, get_connect_cnts(vo, obj))
    else:
        return cli.get_completions(comp, get_connect_cnts(vo))

new_command('connect', connect_connectors_cmd,
            [arg(obj_t('connector', 'connector'), 'cnt0', '?', expander = connect_exp),
             arg(obj_t('connector', 'connector'), 'cnt1', '?', expander = connect_exp)],
            short = 'connect connectors',
            type = ['Components'],
            doc = 'Connect connector <arg>cnt0</arg> to <arg>cnt1</arg>.')

def disconnect_connectors_cmd(cnt0, cnt1):

    if not cli.is_connector(cnt0):
        raise CliError("%r is not a connector" % cnt0)
    if not cli.is_connector(cnt1):
        raise CliError("%r is not a connector" % cnt1)

    # make sure connectors are connected in both directions
    if (len([d for d in cnt0.iface.connector.destination() if d == cnt1]) == 0
        or len([d for d in cnt1.iface.connector.destination() if d == cnt0]) == 0):
        raise CliError('Connector %s and %s are not setup correctly.'
                       % (print_connector(cnt0), print_connector(cnt1)))

    c0_inst = _connector_instantiated(cnt0)
    c1_inst = _connector_instantiated(cnt1)

    # make sure connectors are hotpluggable if they are instantiated
    if c0_inst and not cnt0.iface.connector.hotpluggable():
        raise CliError('Cannot disconnect %s connector as it does '
                       'not support hotplugging.' % print_connector(cnt0))
    if c1_inst and not cnt1.iface.connector.hotpluggable():
        raise CliError('Cannot disconnect %s connector as it does '
                       'not support hotplugging.' % print_connector(cnt1))

    # try to disconnect connectors
    if not cnt0.iface.connector.remove_destination(cnt1):
        raise CliError('Failed removing connection from %s to %s.'
                       % (print_connector(cnt0), print_connector(cnt1)))
    if not cnt1.iface.connector.remove_destination(cnt0):
        cnt0.iface.connector.add_destination(cnt1)
        raise CliError('Failed removing connection from %s to %s.'
                       % (print_connector(cnt1), print_connector(cnt0)))

    if c0_inst and c1_inst:
        cnt0.iface.connector.update()
        cnt1.iface.connector.update()
        hotplug_disconnect(cnt0, cnt1)

    trigger_hier_change_connection(cnt0, cnt1)

    for c in [cnt0, cnt1]:
        if (c.iface.connector.deletion_requested and
            c.iface.connector.deletion_requested()):
            SIM_delete_objects([c])

def get_disconnect_cnts(cnts, obj = None):
    return [k for (k, c) in cnts.items() if (
        # find connections that are connected
        c.iface.connector.destination()
        and
        # only allow (up -> down, any), (down -> up, any), (any -> up, down)
        (not obj or obj in c.iface.connector.destination())
        )]

def disconnect_exp(comp, lst, prev):
    other = [o for o in prev if o]
    vo = visible_objects(iface = 'connector', recursive = True)
    if other:
        obj = other[0]
        return cli.get_completions(comp, get_disconnect_cnts(vo, obj))
    else:
        return cli.get_completions(comp, get_disconnect_cnts(vo))

new_command('disconnect', disconnect_connectors_cmd,
            [arg(obj_t('connector', 'connector'), 'cnt0', '?', expander = disconnect_exp),
             arg(obj_t('connector', 'connector'), 'cnt1', '?', expander = disconnect_exp)],
            short = 'disconnect connectors',
            type = ['Components'],
            doc = 'Disconnect connector <arg>cnt0</arg> from <arg>cnt1</arg>.')

def move_object_cmd(src, dst):
    if not src:
        raise CliError("Source object invalid")

    if src.name == dst:
        return

    if CORE_is_permanent_object_name(src.name):
        raise CliError("Cannot move permanent object '%s'" % src.name)

    if dst.startswith("."):
        dst = dst[1:]
    (part1, _, part2) = dst.rpartition(".")
    if part1:
        if not VT_get_object_by_name(part1):
            raise CliError("Object %s could not be found" % part1)
    if VT_get_object_by_name(dst):
        raise CliError("Could not move to %s, name already used." % dst)
    try:
        VT_rename_object(src, dst)
    except SimExc_General as s:
        raise CliError("Failed moving object %s to %s: %s" % (src.name, dst, s))


def relocate_expander(string, obj):
    cmps = ['%s.' % obj.name for obj in list(visible_objects(all = True).values())
            if matches_class_or_iface(obj, 'component')]
    return get_completions(string, cmps)

new_command('move-object', move_object_cmd,
            [arg(obj_t('object'), 'src'),
             arg(str_t, 'dst', expander = relocate_expander)],
            short = 'move object',
            type = ['Components'],
            doc = """Move object location from <arg>src</arg> to <arg>dst</arg>.""")

def copy_connector_cmd(src, dst):
    if not src:
        raise CliError("Source object invalid")

    # check src connector
    if src.destination:
        raise CliError("Not allowed to copy already connected connector.")

    if src.classname != 'connector':
        raise CliError('Copying "%s" connectors is not supported.'
                       % src.classname)

    # absolute path if dst start with '.'
    if dst.startswith("."):
        dst = dst[1:]
    if not '.' in dst:
        raise CliError("Connectors can not be copied to root.")

    # create connector
    try:
        obj = SIM_create_object('connector', dst)
    except SimExc_General as e:
        raise CliError("Creating connector %s: %s" % (dst, e))
    obj.type         = src.type
    obj.hotpluggable = src.hotpluggable
    obj.required     = src.required
    obj.multi        = src.multi
    obj.direction    = src.direction
    obj.owner        = src.owner
    obj.master       = src.master
    obj.parent       = src
    src.child        = obj
    return command_return(message = 'Created %s as a copy of %s' % (
            obj.name, src.name), value = obj)

new_command('copy-connector', copy_connector_cmd,
            [arg(obj_t('connector', 'connector'), 'src'),
             arg(str_t, 'dst', expander = relocate_expander)],
            short = 'copy object',
            type = ['Components'],
            doc = ("""Copy connector from <arg>src</arg> to <arg>dst</arg>."""))

def delete_connector_cmd(cnt):
    if not cnt:
        raise CliError("Connector object invalid")
    try:
        # check for connection
        if cnt.destination:
            raise CliError("Not allowed to delete connected connector.")

        # check for copy
        if cnt.child:
            raise CliError("Not allowed to delete copied connector.")

        # check for parent
        if not cnt.parent:
            raise CliError("Not allowed to delete connector that is not a copy")
    except AttributeError:
        raise CliError("Not allowed to delete connector that is not a copy")

    # delete reference from parent
    cnt.parent.child = None

    # delete connector object
    try:
        SIM_delete_object(cnt)
    except SimExc_General:
        raise CliError("Failed to delete connector object %s" % cnt.name)

new_command('delete-connector', delete_connector_cmd,
            [arg(obj_t('connector', 'connector'), 'cnt')],
            short = 'delete connector copy',
            type = ['Components'],
            doc = ("""Delete connector copy <arg>cnt</arg>."""))

#
# connector info/status
#
def connector_info_cmd(obj):
    return [(None,
             [("Type", obj.type),
              ('Hotpluggable', obj.hotpluggable),
              ('Required', obj.required),
              ('Multi', obj.multi),
              ('Direction', convert_direction(obj.direction)),
              ('Connector Name', obj.connector_name),
              ('Component', obj.component),
              ('Owner', obj.owner.name),
              ('Master', obj.master.name),
              ('Parent', obj.parent.name if obj.parent else '-'),
              ('Child', obj.child.name if obj.child else '-')]
             )]

def connector_status_cmd(obj):
    return [(None,
             [('Connections', obj.destination)])]

new_info_command('connector', connector_info_cmd)
new_status_command('connector', connector_status_cmd)
