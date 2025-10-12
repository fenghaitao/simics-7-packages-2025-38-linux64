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


from simics import (
    Sim_Connector_Direction_Any,
    Sim_Connector_Direction_Down,
    Sim_Connector_Direction_Up,
)

import re
import simics

def get_highest_2exp(i):
    return (1 << i.bit_length()) >> 1

def get_component(conf_obj):
    '''Returns the Python object instance of the component class for a supplied
    conf_object_t object. This function should be avoided when possible. Code
    should not rely on components being written in Python but instead access
    objects using Simics standard attributes and interfaces.'''
    if not isinstance(conf_obj, simics.conf_object_t):
        raise simics.SimExc_Type("Not a conf_object_t: %s" % conf_obj)
    if not hasattr(conf_obj.iface, 'component'):
        raise simics.SimExc_Type("Not a component conf_object_t: %s"
                                 % conf_obj.name)
    return conf_obj.object_data

class ComponentError(Exception):
    pass

writing_template = False

def get_writing_template():
    return writing_template

def set_writing_template(val):
    global writing_template
    writing_template = val

### slot methods
def get_connectors(obj):
    return [o for o in obj.iface.component.get_slot_objects() if (
            isinstance(o, simics.conf_object_t)
            and hasattr(o.iface, 'connector')
            and o.component == obj)]

def get_connector_by_name(obj, name):
    legacy_name = generate_connector_slot_name(name.replace('-', '_'))
    if obj.iface.component.has_slot(legacy_name):
        # legacy connector name
        ret = obj.iface.component.get_slot_value(legacy_name)
    else:
        # new connector name
        import cmputil
        try:
            ret = cmputil.cmp_get_indexed_slot(obj, name)
        except cmputil.CmpUtilException:
            return None
    if (isinstance(ret, simics.conf_object_t)
        and hasattr(ret.iface, 'connector')):
        return ret
    return None

### connector methods
def print_connector(cnt):
    return cnt.name

def add_connector_to_component(obj, cnt_obj, slot_nm):
    get_component(obj).o.__dict__[slot_nm] = cnt_obj

def generate_connector_slot_name(name):
    return 'connector_%s' % name

def generate_connector_object_name(obj_name, cnt_name):
    return "%s_%s" % (obj_name, generate_connector_slot_name(cnt_name))

def create_connector(obj, cnt_nm, cnt_dict):
    object_name = generate_connector_object_name(obj.name, cnt_nm.replace('-', '_'))
    slot_name = generate_connector_slot_name(cnt_nm.replace('-', '_'))
    cnt_obj = simics.SIM_create_object(
        'connector',      object_name,
        [['type',         cnt_dict['type']],
         ['hotpluggable', cnt_dict['hotplug']],
         ['required',     not cnt_dict['empty_ok']],
         ['multi',        cnt_dict['multi']],
         ['direction',    convert_direction(cnt_dict['direction'])],
         ['owner',        obj],
         ['destination',  []],
         ['connector_name', cnt_nm],
         ['component',    obj],
         ['component_slot', slot_name]])
    add_connector_to_component(obj, cnt_obj, slot_name)

### expanders
#raises AttributeError if not found
def expand_component_object(cmp_obj, name):
    import cmputil
    try:
        return cmputil.cmp_get_indexed_slot(cmp_obj, name)
    except cmputil.CmpUtilException:
        raise AttributeError("Component does not contain any %s object" % name)

### haps
def trigger_hier_change(top_obj):
    if top_obj and top_obj.instantiated:
        simics.SIM_hap_occurred_always(hier_change_hap, top_obj, 0, [top_obj])

    simics.SIM_hap_occurred_always(comp_change_hap, None, 0, [])

hier_change_hap = simics.SIM_hap_add_type(
    "Component_Hierarchy_Change", "c", "top_level_component", None,
    "Internal: Triggered when an instantiated component hierarchy is "
    "modified. The hap is associated with the top-level component of the "
    "modified hierarchy.", 0)

comp_change_hap = simics.SIM_hap_add_type(
    "Component_Change", "", "", None,
    "Internal: Similar to Component_Hierarchy_Change but also triggered "
    "for components that are not part of any complete hierarchy including "
    "non-instantiated components.", 0)


# Class used to cache component connection information.
class ComponentGraphCache:
    def __init__(self):
        # outgoing edges
        self._down = dict()      # comp -> [down_comp1, down_comp2, ...]
        self._down_set = dict()  # comp -> {up_comp1, up_comp2, ...}
        # incoming edges
        self._up = dict()        # comp -> [up_comp1, up_comp2, ...]
        self._up_set = dict()    # comp -> {up_comp1, up_comp2, ...}
        # has required connectors
        self._ready = dict()     # comp -> bool
        self._connectors = dict() # comp-> {cnt1, cnt2, ...}

    # return component reached by following connector in specified direction
    def _follow_connector(self, src_cnt, d):
        src_dir = src_cnt.iface.connector.direction()
        if src_dir != d and src_dir != Sim_Connector_Direction_Any:
            return []
        else:
            return [o.component for o in src_cnt.iface.connector.destination()
                    if (o.iface.connector.direction() != d
                        and o.component is not None)]

    def _follow_connector_up(self, src_cnt):
        return self._follow_connector(src_cnt, Sim_Connector_Direction_Up)

    def _follow_connector_down(self, src_cnt):
        return self._follow_connector(src_cnt, Sim_Connector_Direction_Down)

    # update cached information about a node in the component DAG
    def _cache_node(self, obj):
        if obj in self._up:
            return
        (up, down) = (set(), set())
        if obj.component and not obj.top_level:
            up.add(obj.component)
        self._ready[obj] = True
        connectors = set()

        def obj_impl(iface):
            return [o for o in
                    simics.SIM_object_iterator_for_interface([iface])
                    if o.component == obj]

        for o in obj_impl("connector"):
            connectors.add(o)
            if (o.iface.connector.required() and not
                o.iface.connector.destination()):
                self._ready[obj] = False
            down.update(self._follow_connector_down(o))
            up.update(self._follow_connector_up(o))

        for o in obj_impl("component"):
            down.add(o)

        # keep sorted list to ensure determinism
        self._connectors[obj] = connectors
        self._up_set[obj] = up
        self._down_set[obj] = down
        self._up[obj] = list(sorted(up))
        self._down[obj] = list(sorted(down))

    def connectors(self, comp):
        self._cache_node(comp)
        return list(sorted(self._connectors[comp]))

    # return all components (as a sorted list) reached by following
    # "up" connectors and object hierarchy (e.g. viper.mb -> viper)
    def up(self, comp):
        self._cache_node(comp)
        return self._up[comp]

    # same as "up" but returns a set
    def up_set(self, comp):
        self._cache_node(comp)
        return self._up_set[comp]

    # return all components as a sorted list) reached by following
    # "down" connectors and object hierarchy (e.g. viper -> viper.mb)
    def down(self, comp):
        self._cache_node(comp)
        return self._down[comp]

    # same as "down" but returns a set
    def down_set(self, comp):
        self._cache_node(comp)
        return self._down_set[comp]

    # returns True if the component has no missing required connections
    def ready(self, comp):
        self._cache_node(comp)
        return self._ready[comp]


# Class used to represent the graph formed by
# components nodes and directed edges consisting of
#
#   i) parent component -> child component (object hierarchy)
#  ii) down connector component -> up connector component
#
class ComponentGraph:
    def __init__(self, comps, cgc = None):
        self._cgc = cgc if cgc else ComponentGraphCache()
        assert isinstance(self._cgc, ComponentGraphCache)
        self._roots = self._spanning_roots(comps)
        self._seq = None      # (comp1, comp2, ...)
        self._rootmap = {}    # {component: root_component}
        self._cycle_nodes = set()  # components which are part of a cycle

    @property
    def roots(self):
        return self._roots
    @property
    def cache(self):
        return self._cgc

    # return a sorted list of roots (nodes with no "up" connectors)
    # which spans the set of all nodes reachable from the specified components
    def _spanning_roots(self, comps):
        cgc = self._cgc
        span = set()
        work = set(comps)
        while work:
            c = work.pop()
            if c not in span:
                span.add(c)
                work |= cgc.up_set(c)
                work |= cgc.down_set(c)
        # sort top_level objects first and then by name
        roots = tuple(sorted(c for c in span if not cgc.up_set(c)))
        return (tuple(r for r in roots if r.top_level)
                + tuple(r for r in roots if not r.top_level))

    def _build_sequence(self):
        if self._seq is not None:
            return
        visited = set()
        delayed = []
        seq = []
        def add_children(obj):
            if obj in visited:
                return
            seq.append(obj)
            visited.add(obj)
            for o in self._cgc.down(obj):
                if self._cgc.up_set(o) <= visited:
                    add_children(o)
                else:
                    # this is used to detect cycles
                    delayed.append(o)
        work = self._roots
        while True:
            for o in work:
                add_children(o)
            # nodes for which all parents were not visited must be part
            # of a cycle.
            work = [o for o in delayed if o not in visited]
            if not work:
                break
            self._cycle_nodes.update(work)
            delayed = []
        self._seq = tuple(seq)

    # returns a toplogically sorted tuple of components obtained
    # by following "down" connectors from the set of root components
    def topological_sequence(self):
        self._build_sequence()
        return self._seq

    def _build_rootmap(self):
        if not self._rootmap:
            cgc = self._cgc
            rootmap = {}
            def add_rootmap(r, obj):
                if obj in rootmap:
                    return
                rootmap[obj] = r
                for o in cgc.down(obj):
                    add_rootmap(r, o)
            for r in self._roots:
                add_rootmap(r, r)
            self._rootmap = rootmap

    # return the first root component which has comp in its "down" span.
    def component_root(self, comp):
        self._build_rootmap()
        return self._rootmap[comp]

    # returns a nodes which are part of a component cycle (the returned
    # set is not complete)
    def cycle_nodes(self):
        self._build_sequence()
        return list(sorted(self._cycle_nodes))


def class_has_iface(classname, iface):
    return iface in simics.VT_get_interfaces(classname)

def convert_direction(dir):
    dirs = {'up' : Sim_Connector_Direction_Up,
            'down' : Sim_Connector_Direction_Down,
            'any' : Sim_Connector_Direction_Any,
            Sim_Connector_Direction_Up : 'up',
            Sim_Connector_Direction_Down : 'down',
            Sim_Connector_Direction_Any : 'any'}
    return dirs[dir]

def object_exists(name):
    try:
        simics.SIM_get_object(name)
        return True
    except simics.SimExc_General:
        return False

def is_component_hardware(comp):
    '''Takes a component and return True if it represents normal hardware.

    This is used to decide which components should be included in
    component templates.'''
    return not hasattr(comp.iface, 'osa_tracker_component')


# Allow user to opt-out from side effects performed as a result of a
# hotplug connection. These functions are provided as a workaround
# to address hotplug performance issues (SIMINT-1422).
_inhibit_hotplug_side_effects = 0
def inc_hotplug_side_effects_block_count():
    """Increase the block counter for component hotplugging side effects.
    Certain side effects, like queue assignment, are inhibited when the
    counter is > 0. The resulting counter value is returned."""
    global _inhibit_hotplug_side_effects
    _inhibit_hotplug_side_effects += 1
    return _inhibit_hotplug_side_effects

def dec_hotplug_side_effects_block_count():
    """Decrease the block counter for component hotplugging side effects.
    Certain side effects, like queue assignment, are inhibited when the
    counter is > 0. The resulting counter value is returned."""
    global _inhibit_hotplug_side_effects
    _inhibit_hotplug_side_effects -= 1
    return _inhibit_hotplug_side_effects

def inhibit_hotplug_side_effects():
    return _inhibit_hotplug_side_effects > 0

def get_all_cells():
    return list(simics.SIM_object_iterator_for_class("cell"))

def is_cell_object_factory(val):
    try:
        return val[0] == '__magic_cell_object_factory'
    except:
        return False

# Convert "a[1][2].b" to ["a", 1, 2, "b"].
#
# Input grammar:
#  str   ::= attr ("." attr)*
#  attr  ::= name index*
#  index ::= "[" [0-9]+ "]"
#  name  ::= [a-zA-Z_][a-zA-Z_0-9]*
#
def parse_gen_attr_str(s):
    m = re.match(r"[a-zA-Z_][a-zA-Z_0-9]*", s)
    assert m
    out = [m.group(0)]
    s = s[m.end(0):]
    while s:
        m = re.match(r"\[(\d+)\]", s)
        if not m:
            break
        out.append(int(m.group(1)))
        s = s[m.end(0):]
    if s:
        assert s[0] == "."
        return out + parse_gen_attr_str(s[1:])
    else:
        return out

assert parse_gen_attr_str("alfa") == ["alfa"]
assert parse_gen_attr_str("alfa.beta.gamma") == ["alfa", "beta", "gamma"]
assert (parse_gen_attr_str("alfa[2][3].beta.gamma[5]")
        == ["alfa", 2, 3, "beta", "gamma", 5])

# Like getattr, but attr is a list of strings and integers: strings denote
# attributes and integers are for indexing.
#
# Example: get_gen_attr(x, ["a", 3, "b"])    is equivalent to
#          getattr(getattr(x, "a")[3], "b").
#
def get_gen_list_attr(val, attr):
    for a in attr:
        if isinstance(a, str):
            val = getattr(val, a)
        else:
            val = val[a]
    return val

# Like setattr, but attr is a list of strings and integers: strings denote
# attributes and integers are for indexing.
def set_gen_list_attr(val, attr, newval):
    val = get_gen_list_attr(val, attr[:-1])
    a = attr[-1]
    if isinstance(a, str):
        setattr(val, a, newval)
    else:
        val[a] = newval

# Like getattr, but attr_str can contain multiple attributes and indices,
# such as "a[1][2].b".
def get_gen_attr(val, attr_str):
    return get_gen_list_attr(val, parse_gen_attr_str(attr_str))

# Like setattr, but attr_str can contain multiple attributes and indices,
# such as "a[1][2].b".
def set_gen_attr(val, attr_str, newval):
    set_gen_list_attr(val, parse_gen_attr_str(attr_str), newval)

next_nbr = {}

def next_sequence(name):
    # the name is not guaranteed to be unique since the user may create
    # an object with the same name before this one is instantiated, but
    # we avoid the most common collisions here, and handle the rest when
    # the setting the configuration.
    if not '$' in name:
        return

    if not name in next_nbr:
        next_nbr[name] = [0]
    next = next_nbr[name].pop(0)

    while True:
        unique_name = name.replace('$', repr(next))
        if not object_exists(unique_name):
            break
        next += 1

    if len(next_nbr[name]) == 0:
        next_nbr[name] = [next + 1]
    return next
