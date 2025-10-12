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


import cli
import table
import conf

from simics import *

from . import prop
from . import probe_type_classes

def get_iface(obj, port, iface):
    try:
        if port:
            return SIM_get_port_interface(obj, iface, port)
        else:
            return SIM_get_interface(obj, iface)
    except SimExc_Lookup:
        return None

class ProbeProxy(
        metaclass=cli.doc(
            'wrapper class of probes that exists in Simics',
            module = 'probes',
            doc_id = 'probes_python_api',
            synopsis = False)):
    '''The ProbeProxy class represents a Python object for the detected
    probes in the system. The object wrapping allows easier access
    to the probe objects through the different probe interfaces.

    Object implementing the indexed probe interface, will get a
    dedicated ProbeProxy object per index.

    The formatting of the different types of probes are also
    automatically handled by this class.
    '''

    __slots__ = ('obj', 'port', 'id', 'cli_id', '_start_value', 'pp_prop',
                 'prop', 'probe_iface', 'probe_subscribe_iface',
                 'type_class', '_sorted_value')

    def __init__(self, obj, port, probe_iface, key_value_def, id):
        self.obj = obj
        self.port = port
        self.probe_iface = probe_iface
        self.id = id
        self.cli_id = None
        self._start_value = None

        self.pp_prop = None  # Created lazily
        self.prop = prop.Properties(key_value_def)

        self._validate_and_set_default_props()
        self._set_cli_id()

        # Check for optional interfaces
        self.probe_subscribe_iface = get_iface(
            self.obj, self.port, "probe_subscribe")

        self.type_class = probe_type_classes.get_value_class(self.prop.type)
        if self.type_class.sorting_support():
            self._sorted_value = lambda: self.type_class.sorted(self.value())
        else:
            self._sorted_value = self.value

    def _validate_and_set_default_props(self):
        props = self.prop

        # By default, set the owner_obj to the object implementing this
        if not props.p_owner_obj.has_been_set():
            props.p_owner_obj.set(self.obj)

        # Old style global probes set the owner to None explicitly.
        # Fix this, since this can exist in older packages not updated
        # to what the new framework expects.
        if not props.owner_obj:
            SIM_log_info(
                1, conf.probes, 0,
                f"Probe-kind {props.kind} has Owner_Object property set to"
                f" None, assigning it to the {conf.sim.name} object instead")
            props.p_owner_obj.set(conf.sim, force=True)

        # If not specified use kind as display_name
        if not props.p_display_name.get():
            props.p_display_name.set(props.p_kind.get())

    def value(self):
        '''Read out the value of the probe.'''
        assert 0

    def sorted_value(self):
        '''Read out the sorted value of the probe.'''
        return self._sorted_value()

    def get_pretty_props(self):
        '''Return pretty-printed string of properties'''
        if self.pp_prop == None:
            kv = self.prop.key_value_def
            self.pp_prop = prop.pretty_string(kv)
        return self.pp_prop

    def valid_value(self, value):
        '''Check if a value is value for the probe type'''
        return self.type_class.valid_value(value)

    def table_cell_value(self, value, cell_formatter=None):
        '''Convert any probe value to a value re-presentable in a table (int,
        float, string etc). That is, remove any lists or tuples. Fractions are
        calculated to a float value and a histogram becomes a multi-line string.
        '''
        return self.type_class.table_cell_value(value, cell_formatter)

    def raw_value(self, value, cell_formatter=None):
        '''Return the value of the probe, possibly convert the raw value to a
        string in order to print in a table (fractions and histograms)
        '''
        return self.type_class.raw_value(value, cell_formatter)

    def format_value(self, value, cell_formatter=None, converted=False):
        '''Return a string-representation of the value, formatted accordingly
        to the probe's formatting properties'''

        if not converted:
            value = self.type_class.table_cell_value(value, cell_formatter)

        float_decimals = cell_formatter.float_decimals if cell_formatter else None

        format_props = self.prop.format_properties()
        prop_obj = table.cell_props.CellProps(format_props)
        cell = table.cell.data_to_cell(value, float_decimals, prop_obj)
        val_str = "\n".join([cell.line(i) for i in range(cell.num_lines())])
        return val_str

    def subscribe(self):
        '''Subscribe to the probe (if interface exists)'''
        if self.probe_subscribe_iface:
            self.probe_subscribe_iface.subscribe()
            return True
        return False

    def unsubscribe(self):
        '''Unsubscribe to the probe.'''
        if self.probe_subscribe_iface:
            self.probe_subscribe_iface.unsubscribe()
            return True
        return False

    def num_subscribers(self):
        '''Returns the number of subscribers of the probe.'''
        if self.probe_subscribe_iface:
            return self.probe_subscribe_iface.num_subscribers()
        return None

    def needs_subscription(self):
        '''Check if the probe needs to be subscribed to.'''
        return bool(self.probe_subscribe_iface)

    def table_properties(self):
        '''Return the table-properties for a probe by converting the
        user defined probe properties and adding some more.
        '''
        l = self.prop.table_properties()
        l.append([Column_Key_Int_Radix, 10]) # Use decimals value for probes
        return l

    def active(self):
        '''Check if the probe is currently active.'''
        users = self.num_subscribers()
        if (users == None or users > 0):
            return True
        return False

    def _set_cli_id(self):
        self.cli_id = f"{self.prop.owner_obj.name}:{self.prop.kind}"


class IfaceProbeProxy(ProbeProxy):
    __slots__ = ()

    def __init__(self, obj, port, probe_iface, key_value_def, id):
        super().__init__(obj, port, probe_iface, key_value_def, id)

    def value(self):
        return self.probe_iface.value()


class IndexIfaceProbeProxy(ProbeProxy):
    __slots__ = ('idx')

    def __init__(self, idx, obj, port, probe_iface, key_value_def, id):
        super().__init__(obj, port, probe_iface, key_value_def, id)
        self.idx = idx

    def value(self):
        return self.probe_iface.value(self.idx)


class ArrayIfaceProbeProxy(ProbeProxy):
    __slots__ = ('idx', 'cache')

    def __init__(self, idx, cache, obj, port, probe_iface, key_value_def, id):
        super().__init__(obj, port, probe_iface, key_value_def, id)
        self.idx = idx
        self.cache = cache

    def value(self):
        return self.cache.value(self.idx)


class ProbeArrayCache:
    '''Local implementation of a cached probe read.
    Because it does not call any methods of the probe_sampler_cache iface
    the resulting performance is optimal.'''
    __slots__ = ("probe_iface", "cache_controller", "gen", "values")

    def __init__(self, probe_iface, cache_controller):
        self.probe_iface = probe_iface
        self.cache_controller = cache_controller
        self.gen = 0
        self.values = []

    def value(self, idx):
        gen_ctrl = self.cache_controller.cache_generation_id if self.cache_controller.cache_active else 0
        if gen_ctrl:
            if self.gen != gen_ctrl:
                self.values = self.probe_iface.all_values()
                self.gen = gen_ctrl
            return self.values[idx]
        return self.probe_iface.value(idx)
