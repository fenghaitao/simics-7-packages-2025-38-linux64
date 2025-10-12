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


from .probe_enums import *
from key_value_pretty_printer import KeyValuePrettyPrinter
import simics                   # need conf_object_t
from table import *
from .common import ProbeException
from .common import get_key
from . import templates
from . import probe_type_classes
# Produce a dict {enum-value : String-of-enum-symbol}
from . import probe_enums
enums_strs = [x for x in dir(probe_enums) if not x.startswith('_')]
enum_to_name_map = {getattr(probe_enums, e): e for e in enums_strs}

def property_name(enum):
    if enum in enum_to_name_map:
        return f"{enum_to_name_map[enum]}({enum})"
    else:
        return f"unknown({enum})"

def pretty_string(lst):
    pp = KeyValuePrettyPrinter(enum_to_name_map)
    return pp.result(lst)

# Check that a key-value list is properly formatted
def check_key_value(kv_list):
    if not isinstance(kv_list, list):
        raise ProbeException(f"properties not a list: {kv_list}")

    for kv in kv_list:
        if not isinstance(kv, (list, tuple)):
            raise ProbeException(
                "key-value pair is not a list: %r" % (kv,))
        elif len(kv) != 2:
            raise ProbeException(
                "key-value pair not 2 elements: %r" % (kv,))

# Helper class for key/value properties of table/columns which verifies
# the type, and checks that a property is not assigned twice.
class Property:
    __slots__ = ('_key', '_value', '_assigned', '_property_type')

    def __init__(self, key, default=None):
        self._value = default
        self._key = key
        self._assigned = False

    def _name_for_prop_type(self):
        if isinstance(self._property_type, tuple):
            return " or ".join(
                sorted([p.__name__ for p in self._property_type]))
        return self._property_type.__name__

    def set(self, value, force=False):
        if not force and self._assigned:
            raise ProbeException(
                f"{property_name(self._key)} parameter already set")

        if self._property_type and (
                not isinstance(value, self._property_type)):
            raise ProbeException(
                f"{property_name(self._key)} property must" +
                f" be {self._name_for_prop_type()}, got" +
                f" {type(value).__name__}"
            )

        self._value = value
        self._assigned = True

    def has_been_set(self):
        return self._assigned

    def get(self):
        return self._value

class StrProp(Property):  __slots__ = (); _property_type = str
class BoolProp(Property): __slots__ = (); _property_type = bool
class IntProp(Property):  __slots__ = (); _property_type = int
class ListProp(Property): __slots__ = (); _property_type = list
class ObjProp(Property): __slots__ = (); _property_type = (
        simics.conf_object_t, type(None))
class MultiProp(Property): __slots__ = (); _property_type = (
        str, bool, int, float, simics.conf_object_t, type(None))

# Properties with some additional checking
class StrSetProp(StrProp):
    __slots__ = ('_str_set')
    def set(self, value):
        # Validate that value is a string first
        super().set(value)
        if self._value not in self._str_set:
            self._value = None
            valid = ', '.join(sorted(self._str_set))
            raise ProbeException(
                f"{property_name(self._key)} parameter must" +
                f" any of {valid}, got {value}")


class EnumProp(IntProp):
    __slots__ = ('_enum_set', '_enum_names')
    def names(self):
        return list(self._enum_names.values())
    def set(self, value):
        # Validate that value is a integer first
        super().set(value)
        if self._value not in self._enum_set:
            self._value = None
            valid = ', '.join(sorted(self.names()))
            raise ProbeException(
                f"{property_name(self._key)} parameter must" +
                f" any of {valid}, got {value}")

class ProbeTypeProp(StrSetProp):
    __slots__ = ()
    _str_set = probe_type_classes.get_supported_probe_types()
    def __init__(self, default=None):
        super().__init__(Probe_Key_Type, default)

class StrList(ListProp):
    __slots__ = ()
    def set(self, value):
        # Validate that value is a list first
        super().set(value)
        for e in self.get():
            if not isinstance(e, str):
                raise ProbeException(
                    f"{property_name(self._key)} property must" +
                     " be list of strings, got" +
                    f" {type(e).__name__}")


class ProbeAggregateScopeProp(StrSetProp):
    __slots__ = ()
    _str_set = ("global", "cell")
    def __init__(self, default="global"):
        super().__init__(Probe_Key_Aggregate_Scope, default)

class ProbeAggregateFunctionProp(StrSetProp):
    __slots__ = ()
    _str_set = probe_type_classes.get_supported_aggregator_functions()
    def __init__(self, default="sum"):
        super().__init__(Probe_Key_Aggregate_Scope, default)

class AggregatesList(ListProp):
    __slots__ = ('_base_probe_prop')
    def __init__(self, base_probe_prop):
        super().__init__(Probe_Key_Aggregates, [])
        self._base_probe_prop = base_probe_prop # Probe property this aggregate belongs to

    def aggregate_defined(self, kv):
        agg_name = get_key(Probe_Key_Kind, kv)
        return templates.template_exist(agg_name)

    def set(self, value):
        # Validate and set the list first
        super().set(value)

        # Optimization, filter out already defined aggregates
        value = [a for a in value if not self.aggregate_defined(a)]

        # Replace the list of properties with the corresponding property objects
        new_val = [ProbeAggregateProperties(a) for a in value]
        self._value = new_val


class ProbeBaseProperties:
    __slots__ = ('property_map', 'key_value_def', 'p_type',
                 'p_categories', 'p_cause_slowdown',
                 'p_owner_obj', 'p_kind', 'p_display_name',
                 'p_desc', 'p_def', 'p_percent', 'p_float_decimals',
                 'p_metric', 'p_unit', 'p_binary', 'p_time_fmt',
                 'p_width', 'p_value_notifier')

    def __init__(self, key_value_def):
        # Header properties (implemented through property objects)
        self.property_map = {}
        self.key_value_def = key_value_def
        self.p_type = self.map_prop(
            Probe_Key_Type,
            ProbeTypeProp(default="int"))

        self.p_categories = self.map_prop(
            Probe_Key_Categories,
            StrList(Probe_Key_Categories, default=[]))

        self.p_cause_slowdown = self.map_prop(
            Probe_Key_Cause_Slowdown,
            BoolProp(Probe_Key_Cause_Slowdown))

        self.p_owner_obj = self.map_prop(
            Probe_Key_Owner_Object,
            ObjProp(Probe_Key_Owner_Object))

        self.p_kind = self.map_prop(
            Probe_Key_Kind,
            StrProp(Probe_Key_Kind))

        self.p_display_name = self.map_prop(
            Probe_Key_Display_Name,
            StrProp(Probe_Key_Display_Name))

        self.p_desc = self.map_prop(
            Probe_Key_Description,
            StrProp(Probe_Key_Description))

        self.p_def = self.map_prop(
            Probe_Key_Definition,
            StrProp(Probe_Key_Definition, default=""))

        self.p_percent = self.map_prop(
            Probe_Key_Float_Percent,
            BoolProp(Probe_Key_Float_Percent))

        self.p_float_decimals = self.map_prop(
            Probe_Key_Float_Decimals,
            IntProp(Probe_Key_Float_Decimals, default=2))

        self.p_metric = self.map_prop(
            Probe_Key_Metric_Prefix,
            StrProp(Probe_Key_Metric_Prefix))

        self.p_unit = self.map_prop(
            Probe_Key_Unit,
            StrProp(Probe_Key_Unit))

        self.p_binary = self.map_prop(
            Probe_Key_Binary_Prefix,
            StrProp(Probe_Key_Binary_Prefix))

        self.p_time_fmt = self.map_prop(
            Probe_Key_Time_Format,
            BoolProp(Probe_Key_Time_Format))

        self.p_width = self.map_prop(
            Probe_Key_Width,
            IntProp(Probe_Key_Width))

        self.p_value_notifier = self.map_prop(
            Probe_Key_Value_Notifier,
            StrProp(Probe_Key_Value_Notifier))

    def finalize(self):
        check_key_value(self.key_value_def)

        for (key, value) in self.key_value_def:
            if not self.assign_properties(key, value):
                raise ProbeException(
                    f"unknown probe key: {property_name(key)}")

    def print(self):
        for p in self.property_map.values():
            print (property_name(p._key), "=", p.get())

    # Remember which property-key is assigned which property object.
    # Simply return the object
    def map_prop(self, key, prop_obj):
        self.property_map[key] = prop_obj
        return prop_obj

    # Set the value for the object matching the 'key' property
    def assign_properties(self, key, value):
        if key in self.property_map:
            # Call the corresponding object and set the value
            self.property_map[key].set(value)
            return True
        return False

    @property
    def type(self):
        return self.p_type.get()

    @property
    def categories(self):
        return self.p_categories.get()

    @property
    def cause_slowdown(self):
        return self.p_cause_slowdown.get()

    @property
    def kind(self):
        return self.p_kind.get()

    @property
    def display_name(self):
        return self.p_display_name.get()

    @property
    def desc(self):
        return self.p_desc.get()

    @property
    def definition(self):
        return self.p_def.get()

    @property
    def owner_obj(self):
        return self.p_owner_obj.get()

    @property
    def percent(self):
        return self.p_percent.get()

    @property
    def float_decimals(self):
        self.p_float_decimals.get()

    @property
    def metric(self):
        return self.p_metric.get()

    @property
    def unit(self):
        return self.p_unit.get()

    @property
    def binary(self):
        return self.p_binary.get()

    @property
    def time_fmt(self):
        return self.p_time_fmt.get()

    @property
    def width(self):
        return self.p_width.get()


    # Convert probe properties to similar table properties
    def table_properties(self):
        d = {
            Probe_Key_Display_Name: Column_Key_Name,
            Probe_Key_Description: Column_Key_Description,
            Probe_Key_Float_Percent: Column_Key_Float_Percent,
            Probe_Key_Float_Decimals: Column_Key_Float_Decimals,
            Probe_Key_Metric_Prefix: Column_Key_Metric_Prefix,
            Probe_Key_Binary_Prefix: Column_Key_Binary_Prefix,
            Probe_Key_Time_Format: Column_Key_Time_Format,
            Probe_Key_Width: Column_Key_Width,
        }
        l = []
        for key in d:
            prop_obj = self.property_map[key]
            table_key = d[key]
            value = prop_obj.get()
            if value != None:
                l.append((table_key, value))
        return l

    # Convert some probe properties to table properties.
    # These are related to formatting a single cell value.
    def format_properties(self):
        d = {
            Probe_Key_Float_Percent: Column_Key_Float_Percent,
            Probe_Key_Float_Decimals: Column_Key_Float_Decimals,
            Probe_Key_Metric_Prefix: Column_Key_Metric_Prefix,
            Probe_Key_Binary_Prefix: Column_Key_Binary_Prefix,
            Probe_Key_Time_Format: Column_Key_Time_Format,
        }
        l = [(Column_Key_Int_Radix, 10)]
        for key in d:
            prop_obj = self.property_map[key]
            table_key = d[key]
            value = prop_obj.get()
            if value != None:
                l.append((table_key, value))
        return l


class ProbeAggregateProperties(ProbeBaseProperties):
    __slots__ = ('p_aggregate_scope', 'p_aggregate_function')
    def __init__(self, key_value_def):
        super().__init__(key_value_def)
        # Add special properties for aggregate probes
        self.p_aggregate_scope = self.map_prop(
            Probe_Key_Aggregate_Scope,
            ProbeAggregateScopeProp())

        self.p_aggregate_function = self.map_prop(
            Probe_Key_Aggregate_Function,
            ProbeAggregateFunctionProp())

        self.finalize()

    @property
    def aggregate_scope(self):
        return self.p_aggregate_scope.get()

    @property
    def aggregate_function(self):
        return self.p_aggregate_function.get()


class Properties(ProbeBaseProperties):
    __slots__ = ('p_aggregates')

    def __init__(self, key_value_def):
        super().__init__(key_value_def)
        # Add special properties for top level probes
        self.p_aggregates = self.map_prop(
            Probe_Key_Aggregates,
            AggregatesList(self))

        self.finalize()

        for a in self.aggregates:
            if not probe_type_classes.supports_aggregate_function(
                    self.type, a.aggregate_function):
                raise ProbeException(
                    f"{self.kind} of type {self.type} cannot aggregate"
                    f" using {a.aggregate_function} function.")

    @property
    def aggregates(self):
        return self.p_aggregates.get()
