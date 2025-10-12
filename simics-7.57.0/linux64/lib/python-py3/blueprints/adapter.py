# © 2022 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

# This is functionality for converting a blueprint to a component.
# It is meant to aid step-wise migration to blueprints, by allowing rewriting
# a component into a blueprint but continuing to use it with existing other
# components.

import re
from typing import Callable
from collections import namedtuple

from .types import State, Namespace, List
from .simtypes import ConfObject
from .impl import BlueprintBuilder
from .top import expand
from .params import _get_flat_params, preset_from_args
from .data import _register_parameterised_blueprint
from comp import (StandardConnectorComponent, SimpleConfigAttribute,
                  SimpleAttribute)
from component_utils import get_connectors
from connectors import StandardConnector
import simics
import cli

# Convert state data to simple nested dict data structure
def _serialize_state(comp, ic):
    data = {}

    # Serialize a single state member
    def serialize_value(val):
        if isinstance(val, List):
            return [serialize_value(x) for x in val]
        elif isinstance(val, State):
            return _serialize_state(comp, val)
        elif isinstance(val, Namespace) or isinstance(val, ConfObject):
            # Convert object references to component pre_objects
            if isinstance(val, Namespace) or val.obj is not None:
                return comp.get_slot(str(val))
            else:
                return None
        elif hasattr(val, "_asdict"):
            # NamedTuple case
            vals = {k: serialize_value(v)
                    for (k, v) in val._asdict().items()}
            vals['NamedTuple'] = ["type", type(val).__name__]
            return vals
        else:
            # Scalar values
            return val

    for k in ic:
        v = getattr(ic, k)
        data[k] = serialize_value(v)
    return data

# Convert serialized state data to connector connect_data format
def _obtain_connector_data(comp, data):
    output = []
    for (k, v) in data.items():
        if isinstance(v, dict):
            output.append([k, _obtain_connector_data(comp, v)])
        else:
            output.append([k, v])
    return output

# Convert connector data to nested dict data structure for state
def _deserialize_connector_data(ic, values):
    output = {}

    # Deserialize a single state data member
    # val = connector data value
    # old_val = state member value
    def deserialize_value(val, old_val):
        if isinstance(val, dict) and 'NamedTuple' in val:
            type_data = dict([val.pop('NamedTuple')])
            tuple_type = namedtuple(type_data['type'], val.keys())
            old = old_val._asdict()[k] if old_val is not None else None
            tuple_val = tuple_type._make(deserialize_value(v, old)
                                         for (k, v) in val.items())
            return tuple_val
        elif isinstance(old_val, List):
            return [deserialize_value(x, old_val[0] if old_val else None)
                    for x in val]
        elif isinstance(old_val, State):
            return _deserialize_connector_data(old_val, dict(val))
        elif (isinstance(val, simics.pre_conf_object)
              or isinstance(old_val, Namespace)
              or isinstance(old_val, ConfObject)):
            if val is not None:
                return Namespace(val.name)
            else:
                return None
        else:
            return val

    for k in ic:
        if k in values:
            v = getattr(ic, k)
            output[k] = deserialize_value(values[k], v)
    return output

# Convert deserialized connector data to blueprint preset
def _obtain_preset(ic, data):
    preset = []
    for k in ic:
        # Only override via preset things specified in connect_data
        if k in data:
            v = getattr(ic, k)
            if isinstance(data[k], dict):
                preset += _obtain_preset(v, data[k])
            else:
                preset.append((ic._key + (k,), data[k]))
    return preset

class BlueprintConnector(StandardConnector):
    type = 'blueprint'
    hotpluggable = False
    multi = False

    def __init__(self, ic):
        self.ic = ic
        if hasattr(self.ic, 'legacy_type'):
            self.type = self.ic.legacy_type()

    def get_connect_data(self, comp, cnt):
        # Provide state data members
        data = self.get_check_data(comp, cnt)
        if hasattr(self.ic, 'legacy_data'):
            return self.ic.legacy_data(
                self.direction == simics.Sim_Connector_Direction_Up,
                comp, cnt, data)
        else:
            return [None] + data

    def get_check_data(self, comp, cnt):
        # Provide state data members
        serialized = _serialize_state(comp, self.ic)
        return _obtain_connector_data(comp, serialized)

    def connect(self, comp, cnt, attr):
        if hasattr(self.ic, 'legacy_connect'):
            preset = self.ic.legacy_connect(
                self.direction == simics.Sim_Connector_Direction_Up,
                comp, cnt, attr)
        else:
            preset = None
        if preset is None:
            # Expect attr to contain all data members in state
            vals = dict(attr)
            output = _deserialize_connector_data(self.ic, vals)
            preset = _obtain_preset(self.ic, output)
        comp.presets += preset

        # Expand blueprints again and add objects
        comp._update()

    def disconnect(self, *_):
        # Re-expansion handled in connect
        pass

class BlueprintDownConnector(BlueprintConnector):
    required = False
    direction = simics.Sim_Connector_Direction_Down

class BlueprintUpConnector(BlueprintConnector):
    required = True
    direction = simics.Sim_Connector_Direction_Up

class BlueprintComponent(StandardConnectorComponent):
    _do_not_init = object()

    def _initialize(self):
        super()._initialize()
        self.builder: BlueprintBuilder|None = None
        # Assigned parameter values
        self.params = {}
        # Blueprint presets from component connections
        self.presets = []

    def setup(self):
        super().setup()
        if not self.instantiated.val:
            self._update()
            self._add_connectors()

    def _update(self):
        self._disconnect_connectors()
        self._remove_pre_objects()
        presets = preset_from_args("", type(self).__name__, self.params)
        self._expand_bp(self.obj.name, self.presets + list(presets))
        self.add_objects()

    # Disconnect all added connectors before blueprint expansion
    def _disconnect_connectors(self):
        for cnt in get_connectors(self.obj):
            if isinstance(cnt.object_data, StandardConnector):
                self.obj.iface.component_connector.disconnect(cnt)

    # Remove all added pre-objects before blueprint expansion
    def _remove_pre_objects(self):
        self._slots._dict.clear()

    def add_subset_of_objects(self, config, obj_list):
        def add_port_objects(slot, cls, name):
            # recursively add all port objects as pre-objects for a given class
            # to prevent "not found in set" errors when port objects are used
            # as attribute values
            pclasses = simics.VT_get_port_classes(cls)
            for pcls in pclasses:
                pslot = slot + '.' + pcls
                pname = name + '.' + pcls
                self.add_pre_obj_with_name(pslot,
                                           pclasses[pcls],
                                           pname)
                add_port_objects(pslot, pclasses[pcls], pname)

        array_slot = re.compile(r"\[(\d+)\]")
        # Sorted on object names
        obj_dict = {o[0]: dict(o[2:]) for o in obj_list}

        # Look at array slots first
        array_slots = []
        array_objs = [o for o in config if o.name.endswith(']')]
        array_obj_dict = {o.name: o for o in array_objs}

        # Sorted on object names
        last = None
        for pre_obj in reversed(array_objs):
            name = pre_obj.name
            cls = pre_obj.classname
            attrs = {a: getattr(pre_obj, a) for a in obj_dict[name]}
            if cli.is_connector(pre_obj):
                attrs['connector_name'] = name
            slot_name = name.removeprefix(self.obj.name + ".")
            idx = slot_name.index('[')
            base = slot_name[:idx]

            if base != last:
                # Set attributes on array slot objects, which have now all been
                # seen due to sorting.
                for (n, slot_attrs) in array_slots:
                    pre_obj = self.get_slot(n)
                    assert pre_obj
                    for (k, v) in slot_attrs.items():
                        setattr(pre_obj, k, v)

                # add_pre_obj expects number of objects in [] syntax,
                # but blueprint builder uses indices in []
                # This sets the same attribute values for all slot objects,
                # hence set attributes after all array objects have been seen.
                slot = array_slot.sub(
                    lambda m: "[{0:d}]".format(int(m.group(1)) + 1), slot_name)
                array_slots.append((slot_name, attrs))
                self.add_pre_obj_with_name(slot, cls, name, **attrs)
                last = base
            else:
                array_slots.append((slot_name, attrs))

        for (n, slot_attrs) in array_slots:
            pre_obj = self.get_slot(n)
            assert pre_obj
            for (k, v) in slot_attrs.items():
                setattr(pre_obj, k, v)

        for pre_obj in config:
            name = pre_obj.name
            if name in array_obj_dict:
                continue
            cls = pre_obj.classname
            attrs = {a: getattr(pre_obj, a) for a in obj_dict[name]}
            if cli.is_connector(pre_obj):
                attrs['connector_name'] = name
            slot = name.removeprefix(self.obj.name + ".")
            if self.has_slot(name):
                continue

            # Regular object => slot name is object name
            self.add_pre_obj_with_name(slot, cls, name, **attrs)
            add_port_objects(slot, cls, name)

    # We first handle the "normal" objects. Then we look at objects of
    # non-existing class, which are port objects that got attribute assignments
    # in the blueprint.
    def add_objects(self):
        def get_class_name(o_name):
            # object names appear in array order in the config list,
            # hence index 0 is first. We remember its class and will use
            # it for all other objects from the array, because the
            # get_slot_value call won't work on any index but 0 for some reason.
            # For non-array object names, get_slot_value will just work fine.
            if o_name.endswith(']') and int(o_name[o_name.rfind('[') + 1:-1]) != 0:
                return self.last_array_class
            else:
                rv = (self.obj.iface.component.get_slot_value(
                        '.'.join(o_name.split('.')[1:])).__class_name__)
                self.last_array_class = rv
                return rv

        assert self.builder is not None
        (config, obj_list) = self.builder._make_config(self.obj.name, False)

        pobj_cls = '_non_existing_class'
        config_non_existing = [c for c in config if c.__class_name__ == pobj_cls]
        obj_list_non_existing = [o for o in obj_list if o[1] == pobj_cls]
        config = [c for c in config if c.__class_name__ != pobj_cls]
        obj_list = [o for o in obj_list if o[1] != pobj_cls]

        # we first add the "normal" objects to ensure the later get_slot_value
        # calls on port objects (to get the class name) will work
        self.add_subset_of_objects(config, obj_list)

        # Now we fix the class names for explicitly referenced port objects
        for c in config_non_existing:
            c.__class_name__ = get_class_name(c.__object_name__)

        # Now we add all the port objects that were explicitly mentioned
        self.add_subset_of_objects(config_non_existing, obj_list_non_existing)

    # Return all state externally visible from the blueprint,
    # and never used internally.
    def _published_state(self):
        assert self.builder is not None
        published = dict(self.builder._binds)

        def remove_subscribed(ic: State):
            if ic._key in published:
                del published[ic._key]
                # Remove contained state
                for (k, v) in ic._defaults.items():
                    if isinstance(v, State):
                        remove_subscribed(v)

        # Remove all state that are used within the blueprint
        for (_, _, ic) in self.builder._state_subs:
            if ic:
                remove_subscribed(ic)
        return published

    def _add_connectors(self):
        # Obtain slot name without troublesome characters
        def connector_slot(ns, ic_class):
            name = str(ns).replace('.', '_').replace('[', '').replace(']', '')
            return (f"{name}_" if name else "") + ic_class.__name__

        # Create down connectors for all non-accessed added state
        # i.e. where the blueprint act as server
        for (key, ic) in self._published_state().items():
            (ns, ic_class) = key
            self.add_connector(connector_slot(ns, ic_class),
                               BlueprintDownConnector(ic))
        assert self.builder is not None

        # Accessed state not published in the blueprint
        used = [(n, c) for (n, c, found) in self.builder._state_subs
                if not found]

        for (ns, ic_class) in used:
            # Create up connectors for all accessed state that were not
            # found within the blueprint i.e. where the blueprint act as client
            ic = self.builder.add_state(ns, ic_class)
            self.add_connector(connector_slot(ns, ic_class),
                               BlueprintUpConnector(ic))

    def _expand_bp(self, name, presets):
        raise NotImplementedError()

    # Hook up blueprint post-instantiate calls
    class component(StandardConnectorComponent.component):
        def _prefix_obj(self, prefix, name):
            if (isinstance(name, Namespace)
                           or (isinstance(name, ConfObject)
                               and name.obj is not None)):
                return getattr(Namespace(prefix), str(name))
            else:
                return name

        def _prefix_objs(self, prefix, data):
            return {k: self._prefix_obj(prefix, v) for (k, v) in data.items()}

        def post_instantiate(self):
            # Fix object references to include component name
            self._up.builder._post_instantiate = [
                    (ns, cb, self._prefix_objs(self._up.obj.name, data))
                    for (ns, cb, data) in self._up.builder._post_instantiate
            ]
            self._up.builder.post_instantiate("")

# Convert blueprint parameters to component parameters
def _get_comp_params(bp_name):
    def get_setter(param_name):
        def setter(self, value):
            comp = self._up
            name = param_name
            if comp.instantiated.val:
                return simics.Sim_Set_Illegal_Value
            else:
                # Store argument in component, for later preset calculation
                comp.params[name] = value
                self.val = value
                return simics.Sim_Set_Ok
        return setter

    # Blueprint -> Component parameter types
    attr_types = {
        str: 's',
        int: 'i',
        bool: 'b',
        float: 'f',
        Namespace: 'o',
        ConfObject: 'o',
        list: '[a*]',
    }

    attr_creator = {
        str: SimpleConfigAttribute,
        int: SimpleConfigAttribute,
        bool: SimpleConfigAttribute,
        float: SimpleConfigAttribute,
        Namespace: SimpleAttribute,
        ConfObject: SimpleAttribute,
        list: SimpleAttribute,
    }

    # Obtain blueprint parameters
    params = _get_flat_params(bp_name, "", {})
    # Obtain component parameters (inner classes)
    return {name.replace(':', '_'): type(name.replace(':', '_'),
                                         (attr_creator[p.ptype](
                                             p.default,
                                             attr_types[p.ptype]),),
                                         {'setter': get_setter(name)})
            for (name, p) in params.items()}

def _create_bp_comp(name: str, bp: Callable):
    def expand_bp(self, _, presets):
        self.builder = expand("", bp, presets=presets, ignore_errors=True)

    inner = _get_comp_params(name)
    # Override method in sub-class
    inner['_expand_bp'] = expand_bp
    return type(name, (BlueprintComponent,), inner)

# Decorator used on blueprints to convert them to components
def bp_legacy_comp(params, name: str):
    def inner(f):
        _register_parameterised_blueprint(params, name, f)
        return _create_bp_comp(name, f)
    return inner

class ComponentSlotAdapter():
    def __init__(self, obj, **kwargs):
        self.obj = obj
        self.slots = {}
        for (k, v) in kwargs.items():
            self.slots[k] = v
    def get_slot(self, k):
        return self.slots[k]

def comp_adapter(obj, **kwargs):
    return ComponentSlotAdapter(obj, **kwargs)
