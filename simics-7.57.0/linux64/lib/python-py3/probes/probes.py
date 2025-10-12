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
import conf
import traceback
from functools import partial

from simics import *

from .probe_enums import *
from . import prop
from . import templates
from . import factories
from . import common
from . import global_probes
from . import host_probes
from . import procfs_probes
from . import sketch

from .probe_proxy import (IfaceProbeProxy, IndexIfaceProbeProxy,
                          ArrayIfaceProbeProxy, ProbeArrayCache)

# This must exist outside the ProbesClass. The idea is that some
# simics_start.py script could pre-register certain probes, before the
# feature is enabled.
registered_probes = {} # name -> [(key, value), ...]

def get_probes_data():
    '''Get the singleton 'probes' object, defined by the ProbeClass'''
    if hasattr(conf, "probes"):
        return conf.probes.object_data
    return None

def include_internal_probes():
    return cli.unsupported_enabled("internals")


# The singleton Simics 'probes' object.
class ProbesClass:
    __slots__ = ('objects_impl_iface', 'objects_impl_idx_iface',
                 'objects_impl_array_iface', 'failed_probes',
                 'objects_created_hap_id', 'objects_deleted_hap_id',
                 'objects_pre_delete_hap_id',
                 'probes_next_id', 'update_probes_count',
                 'hap_callback_count', 'probe_proxies',
                 'generation_id', 'probe_delete_callbacks',
                 'probe_dependencies', 'cli_id_dict',
                 'probes_by_kind',
                 'probes_by_cell', 'user_subscribed_probes', 'obj',
                 'cache_generation_id', 'cache_active',
                 'internal_probes')
    cls = confclass("probes", pseudo = True,
                    short_doc = "probe framework class",
                    doc = "Singleton object class for the probes framework.")

    @cls.iface.probe_sampler_cache
    def enable(self):
        self.cache_generation_id += 1
        self.cache_active = True

    @cls.iface.probe_sampler_cache
    def disable(self):
        self.cache_active = False

    @cls.iface.probe_sampler_cache
    def get_generation(self):
        return self.cache_generation_id if self.cache_active else 0

    def __init__(self):
        self.objects_impl_iface = set()  # All objects implementing the probe iface
        self.objects_impl_idx_iface = set()  # All objects implementing the probe index iface
        self.objects_impl_array_iface = set()  # All objects implementing the probe array iface
        self.failed_probes = []
        self.objects_created_hap_id = None
        self.objects_deleted_hap_id = None
        self.objects_pre_delete_hap_id = None
        self.probes_next_id = 0
        self.update_probes_count = 0
        self.hap_callback_count = 0

        self.probe_proxies = {} # id : ProbeProxy()
        self.generation_id = 1  # increased when probes added/deleted

        self.probe_delete_callbacks = []

        # conf object probes that depend on other probes
        # needed for deletion
        self.probe_dependencies = {} # obj : [conf_object_t.name, ...]
        self.cli_id_dict = {}        # { cli_id : Probe }

        self.cache_generation_id = 0
        self.cache_active = False

        self.probes_by_kind = {} # probe-kind : set(Probe...)
        self.probes_by_cell = {} # cell-object: set(Probe...)
        self.user_subscribed_probes = set()
        self.internal_probes = set()

    def start(self):
        SIM_log_info(1, conf.probes, 0, "Enabling probes (could take a while)")
        self.add_default_probes()
        self.enable_object_changed_detection()
        self.objects_changed()

        all_probes = get_all_probes()
        num_probes = len(get_all_probes())
        num_probe_kinds = len({p.prop.kind for p in all_probes})
        SIM_log_info(1, conf.probes, 0,
                     f"Found {num_probes} probes using {num_probe_kinds} different probe-kinds")
        SIM_log_info(1, conf.probes, 0,
                     "Additional probe-related command now exists under"
                     " the 'probes' singleton object")

    def add_default_probes(self):
        # Gather all objects that needs to be created by the probes
        # and instantiate all of them in one call.
        objs = global_probes.create_probe_sketches()
        objs += host_probes.create_probe_sketches()
        objs += procfs_probes.create_probe_sketches()
        sketch.create_configuration_objects(objs)

    def enable_object_changed_detection(self):
        self.objects_created_hap_id = SIM_hap_add_callback(
            "Core_Conf_Objects_Created", self.objects_created_hap, None)
        self.objects_pre_delete_hap_id = SIM_hap_add_callback(
            "Core_Conf_Object_Pre_Delete", self.object_pre_delete, None)

    def disable_object_changed_detection(self):
        SIM_hap_delete_callback_id("Core_Conf_Objects_Created",
                                   self.objects_created_hap_id)
        SIM_hap_delete_callback_id("Core_Conf_Object_Pre_Delete",
                                   self.objects_pre_delete_hap_id)

    def user_subscribe(self, p):     # used by probes.subscribe command
        self.user_subscribed_probes.add(p)

    def user_unsubscribe(self, p):   # used by probes.unsubscribe command
        self.user_subscribed_probes.remove(p)

    def is_user_subscribed(self, p):
        return p in self.user_subscribed_probes

    def register_dependencies(self, conf_object_name, dependencies):
        self.log(f"added dependencies: {conf_object_name}, {dependencies}")
        for d in dependencies:
            objs = self.probe_dependencies.get(d, [])
            objs.append(conf_object_name)
            self.probe_dependencies[d] = objs

    def define_aggregate_probe(self, aggregate_probe, base_probe):
        agg_probe_kind = aggregate_probe.kind

        # Any aggregates already added as template, should have been removed
        # from prop.aggregates list when assigning the prop.
        assert not templates.template_exist(agg_probe_kind)

        function = aggregate_probe.aggregate_function
        SIM_log_info(2, conf.probes, 0,
                     f"Adding {agg_probe_kind} {function}-function")

        if aggregate_probe.aggregate_scope == "global":
            new = factories.AggregateProbeFactory(
                agg_probe_kind, base_probe.prop.kind, function,
                keys=inherit_aggregate_keys_from_base_probe(
                    base_probe.prop.key_value_def,
                    aggregate_probe.key_value_def))
        else:
            new = factories.CellAggregateProbeFactory(
                agg_probe_kind, base_probe.prop.kind, function,
                inherit_aggregate_keys_from_base_probe(
                    base_probe.prop.key_value_def,
                    aggregate_probe.key_value_def))

        templates.add_aggregate_template(new)

    def add_probe(self, p):
        self.check_duplicate(p) # May raise common.ProbeException
        self.probe_proxies[self.probes_next_id] = p
        self.probes_next_id += 1
        self.generation_id += 1
        self.cli_id_dict[p.cli_id] = p
        self.probes_by_kind.setdefault(p.prop.kind, set())
        self.probes_by_kind[p.prop.kind].add(p)
        if "internals" in p.prop.categories:
            self.internal_probes.add(p)

        cell = VT_object_cell(p.prop.owner_obj)
        if cell:  # sim or host probes don't have any cell assigned
            self.probes_by_cell.setdefault(cell, set())
            self.probes_by_cell[cell].add(p)

        for a in p.prop.aggregates:
            self.define_aggregate_probe(a, p)

    def delete_probe(self, p):
        del self.cli_id_dict[p.cli_id]
        self.probes_by_kind[p.prop.kind].remove(p)
        self.internal_probes.discard(p) # Might not be part of set()
        self.generation_id += 1
        cell = VT_object_cell(p.prop.owner_obj)
        if cell:
            if p not in self.probes_by_cell[cell]:
                SIM_log_info(
                    1, conf.probes, 0,
                    f"Warning: probe '{p.cli_id}' deleted, but this is"
                    f" NOT included in the probes_by_cell[{cell.name}] set."
                    " Cell assigned later?")
            else:
                self.probes_by_cell[cell].remove(p)
        self.user_subscribed_probes.discard(p)

        for cb in self.probe_delete_callbacks:
            cb(p)

        del self.probe_proxies[p.id]

    def get_probe_by_id(self, id):
        return self.probe_proxies[id]

    def get_probe_by_cli_id(self, cli_id):
        if cli_id in self.cli_id_dict:
            return self.cli_id_dict[cli_id]
        return None

    def get_generation_id(self):
        return self.generation_id

    def check_duplicate(self, p):
        if p.cli_id in self.cli_id_dict:
            o = self.cli_id_dict[p.cli_id]
            raise common.ProbeException(
                f"probe {p.cli_id}"
                f" already implemented by '{o.obj.name}'."
                f" {p.obj.name}'s illegal keys: {p.get_pretty_props()}")

    def object_pre_delete(self, data, obj):
        self.log(f"Deleted {obj.name}, dependencies:"
                 f" {self.probe_dependencies.get(obj, [])}")
        if obj in self.probe_dependencies:
            delete_objs = []
            for obj_name in self.probe_dependencies[obj]:
                if cli.object_exists(obj_name):
                    delete_objs.append(SIM_get_object(obj_name))
            del self.probe_dependencies[obj]
            if delete_objs:
                self.log(f"Deleting dependencies: {delete_objs}")
                SIM_delete_objects(delete_objs)
            else:
                self.log("No dependency objs deleted (already removed?)")

        for p in list(self.probe_proxies.values()):
            if obj in [p.obj, p.prop.owner_obj]:
                self.log(f"Removing Python reference for {p.obj.name}")
                self.delete_probe(p)


    def objects_changed(self):
        self.update_probes()  # Find possibly new objects with probe interfaces
        templates.create_new_probe_objects()

    # Hap call-back for created objects
    def objects_created_hap(self, cb_data, obj):
        self.hap_callback_count += 1
        self.objects_changed()

    def log(self, msg):
        SIM_log_info(4, self.obj, 0, msg)

    def update_probes(self):
        self.update_probes_count += 1
        self.log(f"update_probes({self.update_probes_count})")

        def create_and_add_proxy(obj, port, probe_if, prop, proxy_constructor):
            try:
                pp = instantiate_proxy(obj, port, probe_if, prop, proxy_constructor)
                if pp:
                    self.add_probe(pp)
            except common.ProbeException as msg:
                SIM_log_error(conf.probes, 0,
                              f"Illegal key/value settings detected for object"
                              f" {obj.name}: {msg}")
                self.failed_probes.append((obj, port))

        def instantiate_proxy(obj, port, probe_if, prop, proxy_constructor):
            kind = common.get_key(Probe_Key_Kind, prop)
            if kind == None:
                SIM_log_error(obj, 0, f"Probe_Key_Kind not set in {obj.name}"
                              " call to <probe interface>.properties()")
                return None
            if kind in registered_probes:
                prop = common.merge_keys_without_listify(registered_probes[kind], prop)
            return proxy_constructor(obj, port, probe_if, prop, self.probes_next_id)

        # Handle new probes
        new_ifaces = set(get_all_ifaces("probe", ignore_objs=self.objects_impl_iface))
        self.log(f"new_ifaces {len(new_ifaces)}")

        for (obj, port, pr_if) in new_ifaces:
            prop = pr_if.properties()
            proxy_constructor = IfaceProbeProxy
            create_and_add_proxy(obj, port, pr_if, prop, proxy_constructor)

        self.objects_impl_iface.update({o for (o, _, _) in new_ifaces})

        # Handle new index probes
        new_idx_ifaces = set(get_all_ifaces("probe_index", ignore_objs=self.objects_impl_idx_iface))
        self.log(f"new_idx_ifaces {len(new_idx_ifaces)}")

        for (obj, port, idx_pr_if) in new_idx_ifaces:
            num_indices = idx_pr_if.num_indices()
            for i in range(num_indices):
                prop = idx_pr_if.properties(i)
                proxy_constructor = partial(IndexIfaceProbeProxy, i)
                create_and_add_proxy(obj, port, idx_pr_if, prop, proxy_constructor)

        self.objects_impl_idx_iface.update({o for (o, _, _) in new_idx_ifaces})

        # Handle new array probes
        new_array_ifaces = set(get_all_ifaces("probe_array", ignore_objs=self.objects_impl_array_iface))
        self.log(f"new_array_ifaces {len(new_array_ifaces)}")

        for (obj, port, array_pr_if) in new_array_ifaces:
            num_indices = array_pr_if.num_indices()
            cache = ProbeArrayCache(array_pr_if, self)
            for i in range(num_indices):
                prop = array_pr_if.properties(i)
                proxy_constructor = partial(ArrayIfaceProbeProxy, i, cache)
                create_and_add_proxy(obj, port, array_pr_if, prop, proxy_constructor)

        self.objects_impl_array_iface.update({o for (o, _, _) in new_array_ifaces})


# If you want to change the python documentation in Simics:
# rm core/linux64/obj/binaries/api-help/api_help_py.py*
# rm core/linux64/lib/python-py3/api_help_py.py*
# make core
#
# If not, Simics will not recreate the files correctly and use the old ones

# Exported
class CellFormatter(
        metaclass=cli.doc(
            'helper object for various format properties',
            module = 'probes',
            doc_id = 'probes_python_api',
            synopsis = False)):
    '''Helper Class for summary-probe formatting. Simply holds various
    formatting properties together, in one class object.'''
    __slots__ = (
        'max_lines',
        'key_col_width',
        'val_col_width',
        'total_width',          # Comes from the table columns' width
        'ignore_column_widths',
        'float_decimals'
    )
    def __init__(self, max_lines=None, key_col_width=None, val_col_width=None,
                 total_width=None, float_decimals=None,
                 ignore_column_widths=False):
        # For histogram probes
        self.max_lines = max_lines         # How many lines in a cell
        self.key_col_width = key_col_width # Characters used for key column
        self.val_col_width = val_col_width # Characters used for value column
        self.total_width = total_width     # Suggested total width
        self.ignore_column_widths = ignore_column_widths
        # For generic float output
        self.float_decimals = float_decimals



# Exported
@cli.doc('get hold of all ProbeProxy instances implementing a specific probe-kind',
         module = 'probes',
         doc_id = 'probes_python_api',
         see_also = 'probes.get_all_probe_kinds, probes.get_all_probes')
def get_probes(kind):
    '''Returns the Python 'ProbeProxy' objects, for probes matching the specific
    probe-kind.
    These objects can be used to access the probe interfaces in a
    convenient way by using methods in them.
    '''

    pd = get_probes_data()
    if pd and kind in pd.probes_by_kind:
        return list(pd.probes_by_kind[kind])
    return []


# Exported
@cli.doc('get all ProbeProxy instances',
         module = 'probes',
         doc_id = 'probes_python_api',
         see_also = 'probes.get_all_probe_kinds, probes.get_probes')
def get_all_probes():
    '''Returns all Python 'ProbeProxy' objects that exists currently.
    These objects can be used to access the probe interfaces in a
    convenient way by using methods in them.
    '''

    pd = get_probes_data()
    if pd:
        all_probes = pd.probe_proxies.values()
        if include_internal_probes():
            return all_probes

        internal_probes = pd.internal_probes
        return set(all_probes).difference(internal_probes)
    return []

@cli.doc('get all registered probe-kinds in the system',
         module = 'probes',
         doc_id = 'probes_python_api',
         see_also = 'probes.get_probes, probes.get_all_probes')
def get_all_probe_kinds():
    '''Returns all registered probe-kinds in the system. The probe-kind is
    the unique probe identifier, not including the objects associated
    with it.
    '''
    all_probes = get_all_probes()
    return set([p.prop.kind for p in all_probes])


# TODO: export?
def get_probe_by_cli_id(cli_id):
    pd = get_probes_data()
    if not pd:
        return None
    return pd.get_probe_by_cli_id(cli_id)


@cli.doc('request a callback when a probe is deleted',
         module = 'probes',
         doc_id = 'probes_python_api',
         see_also = 'probes.unregister_probe_delete_cb')
def register_probe_delete_cb(cb):
    '''Register a function which will be called when a probe is deleted from
    the system. The function only takes a single argument; the ProbeProxy
    instances that is about to be deleted.'''

    conf.probes.object_data.probe_delete_callbacks.append(cb)

@cli.doc('cancel a callback for probe deletion',
         module = 'probes',
         doc_id = 'probes_python_api',
         see_also = 'probes.register_probe_delete_cb')
def unregister_probe_delete_cb(cb):
    '''Unregister a function callback when probes are deleted.
    Typically needed when a python module itself is removed.'''

    conf.probes.object_data.probe_delete_callbacks.remove(cb)

def register_probe(kind, keys):
    '''Unsupported, may change.'''
    keys = common.listify(keys)
    if common.get_key(Probe_Key_Kind, keys) != None:
        SIM_log_error(
            conf.probes, 0,
            "Probe_Key_Kind should not be part of a probe registration")
        return
    if kind in registered_probes:
        present_keys = registered_probes[kind]
        if not compare_and_merge_key_sets(keys, present_keys):
            pp_keys = prop.pretty_string(keys)
            pp_pres = prop.pretty_string(present_keys)
            SIM_log_error(conf.probes, 0,
                          f"registering probe {kind} with different"
                          f" key/value properties: {pp_keys},"
                          f" already defined as {pp_pres}")
    else:
        registered_probes[kind] = keys

# Helper functions

def get_cell_probes(cell, kind):
    pd = get_probes_data()
    if (pd and kind in pd.probes_by_kind
        and cell in pd.probes_by_cell):
        return pd.probes_by_cell[cell].intersection(
            pd.probes_by_kind[kind])
    return []

# TODO: possibly add a way to extend this list with additional
# user-defined singleton objects.
def is_singleton(obj):
    '''Check if the Simics object is a singleton object,
    currently only any of [sim, host]'''
    return obj in [conf.sim, conf.host]

# Exported
@cli.doc('get the ProbeProxy instance for an object ',
         module = 'probes',
         doc_id = 'probes_python_api',
         see_also = 'probes.get_all_probe_kinds, probes.get_probes')
def get_probe_by_object(kind, obj):
    '''Returns the 'ProbeProxy' Python object for a probe-kind in a
    specific conf object.'''

    for p in get_probes(kind):
        if p.prop.owner_obj == obj:
            return p
    return None

def get_probe_by_implementer(kind, obj):
    for p in get_probes(kind):
        if p.obj == obj:
            return p
    return None


def compare_and_merge_key_sets(keys, present_keys):
    for (k,v) in keys:
        present_val = common.get_key(k, present_keys)
        if present_val == None:
            present_keys.append([k, v])
        else:
            if k == Probe_Key_Categories:
                v = sorted(v)
                present_val = sorted(present_val)

            if k == Probe_Key_Aggregates:
                # Cannot add new aggregates to a predefined probe
                # TODO: perhaps allow this
                return False

            if present_val != v:
                return False
    return True


def register_dependencies(conf_object_name, dependencies):
    get_probes_data().register_dependencies(conf_object_name, dependencies)

def inherit_aggregate_keys_from_base_probe(default, override):
    # Inherit the keys from the base probe to the aggregates

    # Remove some keys which should not be inherited
    default = common.filter_out_keys(default,
                                     { Probe_Key_Kind,
                                       Probe_Key_Aggregates,
                                       Probe_Key_Definition,
                                       Probe_Key_Owner_Object })
    # Remove some keys from the aggregate probe
    override = common.filter_out_keys(override,
                                      { Probe_Key_Aggregate_Scope,
                                        Probe_Key_Aggregate_Function })
    return common.merge_keys(default, override)


def get_port_ifaces(cmp_iface, ignore_objs):
    ifaces = []
    for c in SIM_get_all_classes():
        for [port, _, iface] in VT_get_port_interfaces(c):
            if iface != cmp_iface:
                continue
            for o in SIM_object_iterator_for_class(c):
                if o in ignore_objs:
                    continue
                ifaces.append(
                    (o, port, SIM_get_port_interface(o, cmp_iface, port)))
    return ifaces

def get_ifaces(cmp_iface, ignore_objs):
    return [(o, None, SIM_get_interface(o, cmp_iface))
            for o in SIM_object_iterator_for_interface([cmp_iface])
            if not o in ignore_objs]

def get_all_ifaces(cmp_iface, ignore_objs):
    return get_ifaces(cmp_iface, ignore_objs) + get_port_ifaces(cmp_iface, ignore_objs)
