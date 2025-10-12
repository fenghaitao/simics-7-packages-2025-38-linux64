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


from .table_enums import *  # Table constants
from .common import (TableException,)

import simics                   # need conf_object_t
from key_value_pretty_printer import KeyValuePrettyPrinter

# Produce a dict {enum-value : String-of-enum-symbol}
from . import table_enums
enums = [x for x in dir(table_enums) if not x.startswith('_')]
enum_to_name_map = {getattr(table_enums, e): e for e in enums}

def property_name(enum):
    if enum in enum_to_name_map:
        return f"{enum_to_name_map[enum]}({enum})"
    else:
        return f"unknown({enum})"

# Check that a key-value list is properly formatted
def check_key_value(kv_list):
    if not isinstance(kv_list, list):
        raise TableException(f"properties not a list: {kv_list}")

    for kv in kv_list:
        if not isinstance(kv, (list, tuple)):
            raise TableException(
                "key-value pair is not a list: %r" % (kv,))
        elif len(kv) != 2:
            raise TableException(
                "key-value pair not 2 elements: %r" % (kv,))

def pretty_string(lst):
    pp = KeyValuePrettyPrinter(enum_to_name_map)
    return pp.result(lst)

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

    def set(self, value):
        if self._assigned:
            raise TableException(
                f"{property_name(self._key)} parameter already set")

        if self._property_type and (
                not isinstance(value, self._property_type)):
            raise TableException(
                f"{property_name(self._key)} property must" +
                f" be {self._name_for_prop_type()}, got" +
                f" {type(value).__name__}"
            )

        self._value = value
        self._assigned = True

    def get(self):
        return self._value

class StrProp(Property):  __slots__ = (); _property_type = str
class BoolProp(Property): __slots__ = (); _property_type = bool
class IntProp(Property):  __slots__ = (); _property_type = int
class ListProp(Property): __slots__ = (); _property_type = list
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
            # fisketur[lost-assignment]
            valid = ', '.join(sorted(self._str_set))
            raise TableException(
                f"{property_name(self._key)} parameter must" +
                f" any of {valid}, got {value}")

class AlignProp(StrSetProp):
    __slots__ = ()
    _str_set = {"left", "right", "center"}
    def __init__(self):
        super().__init__(Column_Key_Alignment, None)

class EnumProp(IntProp):
    __slots__ = ('_enum_set', '_enum_names')
    def names(self):
        return list(self._enum_names.values())
    def set(self, value):
        # Validate that value is a integer first
        super().set(value)
        if self._value not in self._enum_set:
            self._value = None
            # fisketur[lost-assignment]
            valid = ', '.join(sorted(self.names()))
            raise TableException(
                f"{property_name(self._key)} parameter must" +
                f" any of {valid}, got {value}")

class RadixProp(EnumProp):
    __slots__ = ()
    _enum_set = {2, 10, 16}
    _enum_names = {
        2 : "2 (binary)",
        10: "10 (decimal)",
        16: "16 (hexadecimal)"
    }
    def __init__(self):
        super().__init__(Column_Key_Int_Radix, None)
