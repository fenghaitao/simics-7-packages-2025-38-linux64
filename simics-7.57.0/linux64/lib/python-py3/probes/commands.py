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

import platform

import conf
import psutil
import simics
import sim_commands
import simics_common
import log_commands

from table import (
    Column_Key_Alignment,
    Column_Key_Footer_Sum,
    Column_Key_Hide_Homogeneous,
    Column_Key_Int_Radix,
    Column_Key_Name,
    Table,
    Table_Key_Columns,
    Table_Key_Default_Sort_Column,
    get_table_arg_value,
    new_table_command,
    new_unsupported_table_command,
    show,
    get
)
from simics import (
    Probe_Key_Cause_Slowdown,
    Probe_Key_Owner_Object,
    Probe_Key_Type,
    Probe_Key_Display_Name,
    Probe_Key_Width,
    SIM_create_object,
    SIM_get_all_classes,
    SIM_get_class,
    SIM_log_info,
    SIM_object_data,
)
from . import probes
from . import templates
from . import probe_type_classes
from . import sketch

from .common import listify

# To get the Simics classes registered for info/status
from . import cell_probes
from . import global_probes

from cli import (new_command, new_unsupported_command,
                 new_info_command, new_status_command,
                 arg, range_t, str_t, flag_t, float_t, obj_t, int_t,
                 string_set_t,
                 get_shortest_unique_object_names, command_return,
                 get_completions, CliError, visible_objects,
                 unsupported_enabled)

# probes.info
def probes_info_cmd(obj):
    num_probe_kinds = 0
    num_internal_kinds = 0
    num_subscription_probe_kinds = 0
    num_probes = 0
    categories = {}
    namespaces = {}
    for kind in probes.get_all_probe_kinds():
        num_probe_kinds += 1
        probe_instances = probes.get_probes(kind)
        num_probes += len(probe_instances)
        # Assume properties are same for all instances
        p0 = probe_instances[0]

        if p0.needs_subscription():
            num_subscription_probe_kinds += 1
        if "internals" in p0.prop.categories:
            num_internal_kinds += 1
        for c in p0.prop.categories:
            categories.setdefault(c, 0)
            categories[c] += 1

        top_namespace = kind.split(".")[0]
        namespaces.setdefault(top_namespace, 0)
        namespaces[top_namespace] += 1

    sorted_categories = sorted(list(categories.items()),
                               key=lambda kv: kv[1], reverse=True)
    sorted_namespaces = sorted(list(namespaces.items()),
                               key=lambda kv: kv[1], reverse=True)

    kinds_str = f"{num_probe_kinds}"
    if num_internal_kinds:
        kinds_str += f" (including {num_internal_kinds} internal probes)"

    return [("Global probe counts",
             [
              ("Probes", num_probes),
              ("Probe kinds", kinds_str),
              ("Probe kinds w/ subscription", num_subscription_probe_kinds),
              ]),
            ("Probe kind top-level name-spaces"
             " (and # of probe-kinds under each namespace)",
             sorted_namespaces),
            ("Probe categories (and # of probe-kinds with this category)",
             sorted_categories),
            ]

# probes.status
def probes_status_cmd(obj):
    all_probes = probes.get_all_probes()
    num_probes = len(all_probes)
    num_active = 0          # Can be read
    num_subscriptions = 0
    num_subscribed = 0

    for p in all_probes:
        if p.needs_subscription():
            num_subscriptions += 1
            if p.num_subscribers():
                num_subscribed += 1
        if p.active():
            num_active += 1

    active_percent = num_active * 100.0 / num_probes
    subscribed_percent = num_subscribed * 100.0 / num_subscriptions
    return [("",
             [("Readable probes",
               f"{num_active} ({active_percent:5.2f}% of {num_probes})"),
              ("Subscribed probes",
               f"{num_subscribed} ({subscribed_percent:5.2f}% of"
               f" {num_subscriptions})"),
              ]),
            ]

new_info_command("probes", probes_info_cmd)
new_status_command("probes", probes_status_cmd)

# host.info
def host_info_cmd(obj):
    sim = conf.sim
    (system, node, _, version, machine, _) = platform.uname()
    hv_info = simics.CORE_host_hypervisor_info()
    hypervisor = ("no" if not hv_info.is_hv_detected else
                  (hv_info.vendor or "an unknown hypervisor detected"))
    cpu_brand = simics.CORE_host_cpuid_brand_string()
    cpu_cores = psutil.cpu_count(logical=False)
    cpu_logical = psutil.cpu_count(logical=True)
    cpu_freqs = list({x.max for x in psutil.cpu_freq(True)})
    return [
        (None, [
             ("name", node),
             ("CPU brand", cpu_brand),
             ("CPU cores",  cpu_cores),
             ("CPU logical cores",  cpu_logical),
             ("CPU max freqs", cpu_freqs),
             ("memory", sim_commands.abbrev_size(sim.host_phys_mem)),
             ("IPv4_address", sim.host_ipv4),
             ("IPv6 address", sim.host_ipv6),
             ("OS", system),
             ("OS architecture", machine),
             ("OS release", simics_common.os_release()),
             ("OS version", version),
             ("hypervisor", hypervisor),
         ])]

# host.status
def host_status_cmd(obj):
    def subscribe_host_probes():
        conf.probes.cli_cmds.subscribe(probe_kind="host.")

    def read_probe(p):
        return conf.probes.cli_cmds.read(probe=p)

    subscribe_host_probes()
    mem_total = read_probe("host:host.memory.total")
    mem_used = read_probe("host:host.memory.used")
    mem_percent = read_probe("host:host.memory.used_percent")
    mem_str = f"{mem_percent} ({mem_used} of {mem_total})"

    swap_total = read_probe("host:host.swap.total")
    swap_used = read_probe("host:host.swap.used")
    swap_percent = read_probe("host:host.swap.used_percent")
    swap_str = f"{swap_percent} ({swap_used} of {swap_total})"

    load_percent = read_probe("host:host.load_percent")
    load_1m = read_probe("host:host.load_average_1m")
    load_5m = read_probe("host:host.load_average_5m")
    load_15m = read_probe("host:host.load_average_15m")
    load_str = f"{load_percent} [1m:{load_1m}, 5m:{load_5m}, 15m:{load_15m}]"

    freq_min = read_probe("host:host.cpu_freq_min")
    freq_max = read_probe("host:host.cpu_freq_max")
    freq_mean = read_probe("host:host.cpu_freq_mean")
    freq_str = f"Max:{freq_max}, Min:{freq_min}, Mean:{freq_mean}"

    temp_min = read_probe("host:host.core_temp_min")
    temp_max = read_probe("host:host.core_temp_max")
    temp_mean = read_probe("host:host.core_temp_mean")
    temp_str = f"Max:{temp_max}, Min:{temp_min}, Mean:{temp_mean}"

    return [
        (None, [
            ("Memory used", mem_str),
            ("Swap used", swap_str),
            ("Load", load_str),
            ("Frequency", freq_str),
            ("Temperature", temp_str),
        ]),
    ]

new_info_command("host_system", host_info_cmd)
new_status_command("host_system", host_status_cmd)

# Expander for the probe-kind sim.time, cpu.mips etc.
def probe_kind_expander(prefix):
    strings = probes.get_all_probe_kinds()
    return get_completions(prefix, strings)

# Expander for fully qualified probes sim:sim.time, cpu0:cpu0.mips etc
def probe_expander(prefix):
    strings = {p.cli_id for p in probes.get_all_probes()}
    return get_completions(prefix, strings)

def category_expander(prefix):
    cats = set()
    for p in probes.get_all_probes():
        for c in p.prop.categories:
            cats.add(c)
    return get_completions(prefix, cats)


# Given a number of user command arguments, filter out the probes
# that do not match the filters. A list of proxy-probes that were
# not filtered out is returned.
def filtered_probes(probe_kind, object, recursive,
                    substr, categories, probe_types, active):

    unique_probe_kinds = probes.get_all_probe_kinds()
    def keep(p):
        if probe_kind:
            if probe_kind in unique_probe_kinds:
                if p.prop.kind != probe_kind:
                    return False
            elif not p.prop.kind.startswith(probe_kind):
                return False

        if object:
            if recursive:
                if not p.prop.owner_obj.name.startswith(object.name):
                    return False
            else:
                if p.prop.owner_obj != object:
                    return False

        if substr:
            if not substr in p.cli_id:
                return False

        if categories:
            req_categories = set(categories)
            intersection = set(p.prop.categories).intersection(req_categories)
            if not intersection == req_categories:
                return False

        if probe_types:
            if p.prop.type not in probe_types:
                return False

        if active:
            if not p.active():
                return False

        return True             # Not filtered out

    return [p for p in probes.get_all_probes() if keep(p)]


# Generic list of arguments used in many of the commands
def filter_arguments(add_active_filter=True):
    args = [
        arg(str_t, "probe-kind", "?", None, expander = probe_kind_expander),
        arg(obj_t("object"), "object", "?", None),
        arg(flag_t, "-recursive"),
        arg(str_t, "substr", "?", None),
        arg(str_t, "categories", "*", expander = category_expander),
        arg(string_set_t(
            set(probe_type_classes.probe_type_to_class.keys())),
            "probe-types", "*"),
    ]
    if add_active_filter:
        args.append(arg(flag_t, "-active"))
    return args

def filter_documentation(add_active_filter=True):
    doc = (
        'The <arg>probe-kind</arg> filter specifies which probe-kinds to'
        ' include.  This can be the full name of a specific probe'
        ' kind, or the string can be a partial kind, for example'
        ' specifying <tt>cpu.exec_modes.</tt> would include all'
        ' probe-kinds starting with this string.'
        '\n\n'
        'The <arg>substr</arg> argument filter allows only probes which'
        ' has a specific string in the probe name to be displayed.'
        '\n\n'
        'To find probes in a particular object the <arg>object</arg>'
        ' argument can be used, only showing the probes on that specific'
        ' object.'
        '\n\n'
        'In combination with the <arg>object</arg> argument the'
        ' <tt>-recursive</tt> switch can be used to look at the probes that'
        ' exists beneath the specified object, in the object hierarchy.'
        ' This allows zooming in on the probes within a particular subsystem'
        ' of the entire target system.'
        '\n\n'
        'Each probe might be assigned with a number of categories represented'
        ' as strings that describe some property of what they measure. The'
        ' <arg>categories</arg> filter can be used to only include the probes'
        ' which have <b>all</b> of the requested categories included.'
        '\n\n'
        'Probes can returned different types when read. The'
        ' <arg>probe-types</arg> argument allows only certain types to be shown.'
        '\n\n')

    if add_active_filter:
        doc += (
            'Some probes requires subscription before they can return any'
            ' value. The <tt>-active</tt> switch automatically discards the'
            ' probes that cannot currently be read. For these to be shown the'
            ' <cmd class="probes">subscribe</cmd> command should be used first.'
            '\n'
        )
    return doc

def enable_probes_cmd(log_level):
    if hasattr(conf, "probes"):
        print("Probes already enabled")
        return
    p = SIM_create_object("probes", "probes",
                          [["log_level", log_level]])
    SIM_object_data(p).start()

new_command("enable-probes", enable_probes_cmd,
            args = [
                arg(range_t(0, 4, "0..4"), "log-level", "?", 1,
                    expander = log_commands.exp_log_levels),
            ],
            short = "enable probe framework",
            type = ["Probes"],
            doc = """
Enable the probes framework. Probes allows easy retrieval of data from
all objects that supports the probe interfaces. This command will
create a global object called probes that handles the probes. More
probe commands are visible under this object. The <arg>log-level</arg>
argument sets the log level of the probe object, useful for
debugging.""")

# Generic for both probes.list-kinds and probes.list-kinds-internal
def list_kinds(
        obj,
        # Output switches
        print_classes, print_objects,
        print_impl_clss, print_impl_objs,
        print_definition, print_probe_type, print_categories,
        no_description,

        # Filters
        probe_kind, object,  recursive,
        substr, categories, probe_types,
        active,

        *table_args):

    # A class per probe-kind capturing all the probes implementing
    # this kind. Keeping track of various statistics used by the
    # list-kinds command.
    class KindInfo:
        __slots__ = ('probe_kind', 'classes', 'objects',
                     'impl_objs', 'impl_clss',
                     'display_name', 'probe_type', 'definition',
                     'categories', 'desc', 'num')
        def __init__(self, probe_kind):
            self.probe_kind = probe_kind
            self.classes = set()
            self.objects = set()
            self.impl_objs = set()
            self.impl_clss = set()

            # These should be the same for each probe with the same kind
            self.display_name = None
            self.probe_type = None
            self.definition = None
            self.categories = set()
            self.desc = None
            self.num = 0

        # Add a probe with the same kind
        def add_probe(self, p):
            self.num += 1
            self.objects.add(p.prop.owner_obj.name)
            self.classes.add(p.prop.owner_obj.classname)
            self.impl_objs.add(p.obj.name)
            self.impl_clss.add(p.obj.classname)
            assert self.num == len(self.objects)

            # Avoid causing multi-line output
            display_name = p.prop.display_name.replace('\n', ' ')
            if self.num == 1: # First probe
                self.display_name = display_name
                self.probe_type = p.prop.type
                self.definition = p.prop.definition
                self.categories = p.prop.categories
                self.desc = p.prop.desc
            elif (display_name != self.display_name
                  or p.prop.type != self.probe_type
                  or p.prop.definition != self.definition
                  or p.prop.categories != self.categories
                  or p.prop.desc != self.desc):
                print(
                    f"Warning: found {p.cli_id} not implementing"
                    f" {self.probe_kind} in a consistent manner.")

        # Return the data for a probe-kind, respect the command
        # switches on what should be included and otherwise return
        # an empty string for non-printed data
        def data_row(self):

            def comma_lst(lst):
                return ", ".join(sorted(lst))

            return [
                self.probe_kind,
                self.display_name,
                self.num,
                self.probe_type if print_probe_type else "",
                self.definition if print_definition else "",
                comma_lst(self.categories) if print_categories else "",
                comma_lst(self.classes) if print_classes else "",
                comma_lst(self.objects) if print_objects else "",
                comma_lst(self.impl_clss) if print_impl_clss else "",
                comma_lst(self.impl_objs) if print_impl_objs else "",
                self.desc if not no_description else ""
            ]

    optional = (Column_Key_Hide_Homogeneous, "")
    tcols = [
        [(Column_Key_Name, "Probe Kind")],
        [(Column_Key_Name, "Display Name")],
        [(Column_Key_Name, "Num"),
         (Column_Key_Int_Radix, 10),
         (Column_Key_Footer_Sum, True),],
        [(Column_Key_Name, "Type"),         optional],
        [(Column_Key_Name, "Definition"),   optional],
        [(Column_Key_Name, "Categories"),   optional],
        [(Column_Key_Name, "Classes"),      optional],
        [(Column_Key_Name, "Objects"),      optional],
        [(Column_Key_Name, "Impl Classes"), optional],
        [(Column_Key_Name, "Impl Objects"), optional],
        [(Column_Key_Name, "Description"),  optional],
    ]
    tprops = [(Table_Key_Columns, tcols),
              (Table_Key_Default_Sort_Column, "Probe Kind")]

    fpl = filtered_probes(probe_kind, object, recursive,
                          substr, categories, probe_types, active)

    d = {}
    for p in fpl:
        kind = p.prop.kind
        d.setdefault(kind, KindInfo(kind))
        d[kind].add_probe(p)

    tdata = []
    for pk in d.values():
        row = pk.data_row()
        tdata.append(row)

    # Print out the table using the supplied table arguments
    show(tprops, tdata, *table_args)

def probes_list_kinds_cmd(
        obj,
        # Output switches
        print_classes, print_objects,
        print_definition, print_probe_type, print_categories,
        no_description,

        # Filters
        probe_kind, object,  recursive,
        substr, categories, probe_types,
        active,

        *table_args):

    list_kinds(obj, print_classes, print_objects,
               False, False,    # impl_classes, impl_objects
               print_definition, print_probe_type, print_categories,
               no_description,
               probe_kind, object, recursive,
               substr, categories, probe_types,
               active, *table_args)

def probes_list_kinds_internal_cmd(
        obj,
        # Output switches
        print_classes, print_objects,
        print_definition, print_probe_type, print_categories,
        no_description,
        impl_classes, impl_objects,

        # Filters
        probe_kind, object,  recursive,
        substr, categories, probe_types,
        active,

        *table_args):

    list_kinds(obj, print_classes, print_objects,
               impl_classes, impl_objects,
               print_definition, print_probe_type, print_categories,
               no_description,
               probe_kind, object,  recursive,
               substr, categories, probe_types,
               active, *table_args)

list_kinds_args = [
    # Output switches
    arg(flag_t, "-classes"), arg(flag_t, "-objects"),
    arg(flag_t, "-definition"),
    arg(flag_t, "-probe-type"),
    arg(flag_t, "-categories"),
    arg(flag_t, "-no-description"),
]

list_kinds_documentation = """
Output column selection.

By default, a few columns are printed for each probe-kind.
To add additional information, or remove some columns the following
command switches.

The <tt>-classes</tt> switch list the Simics classes where the probe-kind
belongs. The <tt>-objects</tt> flag adds a column showing the
objects that provides the probe.
<tt>-probe-type</tt> lists the probe-type in a additional column.

<tt>-definition</tt> adds a column on how the probes have been defined.

<tt>-categories</tt> adds a column showing which categories that was
assigned to the probe-kind.

By default the probe description is printed in the rightmost column,
since this can become wide, the <tt>-no-description</tt> switch removes
this column from the output.
"""

new_table_command(
    "list-kinds", probes_list_kinds_cmd,
    args = list_kinds_args + filter_arguments(),
    cls = "probes",
    type = ["Probes"],
    short = "print table of probe-kinds",
    doc = f"""
Print a table with all probe-kinds detected in the system, useful for
exploring what kind of information that is available.

By default all probe-kinds are listed, but there are many filter
arguments reducing the amount of probes presented.

{filter_documentation()}

{list_kinds_documentation}
""",
    sortable_columns = [
        "Probe Kind", "Display Name", "Type"
    ]
)

new_unsupported_table_command(
    "list-kinds-internal", "internals", probes_list_kinds_internal_cmd,
    args = list_kinds_args + [
        arg(flag_t, "-impl-classes"),
        arg(flag_t, "-impl-objects"),
    ] + filter_arguments(),
    cls = "probes",
    type = ["Probes"],
    short = "print table of probe-kinds",
    doc = f"""
This command is identical to probes.list-kinds except it adds two
switches for internal usage:
<tt>-impl-classes</tt> which shows the Simics class implementing
a probe, and <tt>-impl-objects</tt> which shows the Simics object.

{filter_documentation()}

{list_kinds_documentation}
""",
    sortable_columns = [
        "Probe Kind", "Display Name", "Type"
    ]
)

def probes_subscribe_cmd(
        obj,
        # Filters
        probe_kind, object,  recursive,
        substr, categories, probe_types):

    fpl = filtered_probes(probe_kind, object, recursive,
                          substr, categories, probe_types, active=False)

    probes_py = obj.object_data
    num = 0
    for p in fpl:
        if (p.needs_subscription()
            and not probes_py.is_user_subscribed(p)):
            p.subscribe()
            probes_py.user_subscribe(p)
            SIM_log_info(2, obj, 0, f"Subscribing to {p.cli_id}")
            num += 1
    return command_return(value = num,
                          message = f"Subscribed to {num} probes")

new_command(
    "subscribe", probes_subscribe_cmd,
    args = filter_arguments(add_active_filter=False),
    cls = "probes",
    type = ["Probes"],
    short = "subscribe to probes",
    doc = (f"""
Some probes cannot be read without someone first subscribing to
them. These subscription probes typically need to activate some
feature which could reduce run-time performance.
Hence, they are only accessible when someone wants to read them.

Without any arguments, all probes that requires
subscription will be subscribed too.

To more precisely select the probes that should be subscribed
to, there are a number of filters to reduce the scope.

{filter_documentation(add_active_filter=False)}
"""))

def probes_unsubscribe_cmd(
        obj,
        # Filters
        probe_kind, object,  recursive,
        substr, categories, probe_types):

    fpl = filtered_probes(probe_kind, object, recursive,
                          substr, categories, probe_types, active=False)

    num = 0
    probes_py = obj.object_data
    for p in fpl:
        if (p.needs_subscription()
            and probes_py.is_user_subscribed(p)):
            p.unsubscribe()
            probes_py.user_unsubscribe(p)
            SIM_log_info(2, obj, 0, f"Unsubscribing to {p.cli_id}")
            num += 1
    return command_return(value = num, message = f"Unsubscribed to {num} probes")

new_command(
    "unsubscribe", probes_unsubscribe_cmd,
    args = filter_arguments(add_active_filter=False),
    cls = "probes",
    type = ["Probes"],
    short = "unsubscribe to probes",
    doc = (f"""
Probes which have already been subscribed to, using the
<cmd class="probes">subscribe</cmd> command, can with this command
be unsubscribed to. If there are zero users on the subscribed
probe, some features can be turned off, potentially reducing
run-time overhead.

Without any arguments, all probes which have been earlier
subscribed too will be unsubscribed.
To more precisely select the probes that should be unsubscribed
to, there are a number of filters to reduce the scope.

{filter_documentation(add_active_filter=False)}
"""))

def list_probe_templates_cmd(obj, unused_flag, substr, *table_args):
    tcols = [[(Column_Key_Name, "Factory Object")],
             [(Column_Key_Name, "Factory Class")],
             [(Column_Key_Name, "#Created"),
              (Column_Key_Int_Radix, 10),
              (Column_Key_Footer_Sum, True),],
             ]
    tprops = [(Table_Key_Columns, tcols),
              (Table_Key_Default_Sort_Column, "Factory Object")]

    tdata = []
    for t in templates.all_templates():
        if unused_flag and t.created > 0:
            continue
        if substr and not substr in t.name:
            continue
        tdata.append((t.name, type(t).__name__, t.created))

    # Print out the table using the supplied table arguments
    show(tprops, tdata, *table_args)


new_unsupported_table_command(
    "list-templates", "internals", list_probe_templates_cmd,
    args = [arg(flag_t, "-unused"),
            arg(str_t, "substr", "?", ""),
            ],
    cls = "probes",
    type = ["Probes"],
    short = "print probe-templates",
    doc = """
    List the templates currently registered.
    The <tt>-unused</tt> flag only shows the templates that exists that
    never has been used to create a probe.
    The <arg>substr</arg> can be used to filter out certain names
    in the factory object names. The sub-string must be somewhere
    in the name to be included.
    """,
    sortable_columns = [
        "Factory Object", "Factory Class", "#Created"
    ]
)

def probes_read_cmd(
        obj,
        probe,
        # Output formatting
        values, raw_values,
        # Filters
        probe_kind, object,  recursive,
        substr, categories, probe_types,
        active,
        # Table arguments
        *table_args):

    def read_one_probe(p, max_widths):
        if p.needs_subscription() and p.num_subscribers() == 0:
            raise CliError((f"Probe {p.cli_id} is not active. Use"
                            " probes.subscribe to activate it."))

        probe_val = p.sorted_value()
        float_decimals = get_table_arg_value("float-decimals", table_args)
        cf = probes.CellFormatter(float_decimals=float_decimals,
                                  key_col_width=max_widths[0],
                                  val_col_width=max_widths[1])

        if values:
            vret = p.table_cell_value(probe_val, cf)
            mret = vret
        elif raw_values:
            vret = probe_val
            mret = p.raw_value(probe_val, cf)
        else:
            # Formatted to strings (default)
            vret = p.format_value(probe_val, cf)
            mret = vret
        return (vret, mret)

    def get_histogram_max_widths(probes):
        # Find max widths for all printed out histogram types
        histogram_probes = [p for p in probes
                            if p.prop.type == "histogram"]
        max_key = 0
        max_val = 0
        for p in histogram_probes:
            val = p.value()
            (mk, mv) = p.type_class.histogram_max_widths(val)
            max_key = max([max_key, mk])
            max_val = max([max_val, mv])
        return (max_key, max_val)

    if raw_values and values:
        raise CliError("Only one of -values and -raw-values can be given")

    if probe and any([probe_kind, object, active, categories]):
        raise CliError(
            "Cannot handle filtering with a explicit 'probe' argument"
        )

    # One probe only
    if probe:
        p = probes.get_probe_by_cli_id(probe)
        if not p:
            raise CliError(f"Unknown probe: {probe}")
        if p.needs_subscription() and p.num_subscribers() == 0:
            raise CliError((f"Probe {p.cli_id} is not active. Use"
                            " probes.subscribe to activate it."))

        max_widths = get_histogram_max_widths([p])
        (value, msg) = read_one_probe(p, max_widths)
        return command_return(value=value, message=msg)

    # From all probes, filter out the probes to read
    fpl = filtered_probes(probe_kind, object, recursive,
                          substr, categories, probe_types, active)

    # Multiple probes read, format it as a table and return a list
    ret_list = []
    non_active = {p for p in fpl if not p.active()}
    reads = set(fpl) - non_active
    max_widths = get_histogram_max_widths(reads)
    for p in reads:
        (value, msg) = read_one_probe(p, max_widths)
        ret_list.append((p, value, msg))

    if non_active:
        print(f"{len(non_active)} probes could not be read since they need"
              " subscription.\nUse the -active switch to discard these or"
              " use the probes.subscribe command to activate them.")
        verbose = get_table_arg_value("-verbose", table_args)
        if not verbose:
            print("Use the -verbose switch to show the inactive probes.")
        else:
            non_active_cli_ids = sorted([p.cli_id for p in non_active])
            print(f"Non active probes: {', '.join(non_active_cli_ids)}")

    props = [(Table_Key_Columns,
              [[(Column_Key_Name, "Probe")],
               [(Column_Key_Name, "Value"),
                (Column_Key_Alignment, "right")],
               ]),
             (Table_Key_Default_Sort_Column, "Probe")]
    data = [(p.cli_id, msg)
            for (p, value, msg) in ret_list]

    # Get the table as a string
    msg = get(props, data, *table_args)

    ret_vals = [[p.cli_id, value]
                for (p, value, msg) in ret_list]

    return command_return(value=ret_vals, message=msg)

new_table_command(
    "read", probes_read_cmd,
    args = [
        arg(str_t, "probe", "?", None, expander = probe_expander),
        # Output formatting
        arg(flag_t, "-values"),
        arg(flag_t, "-raw-values"),

    ] + filter_arguments(),
    cls = "probes",
    type = ["Probes"],
    short = "return probe value",
    doc = (
f"""Reads and display the current value of one, or several probes in
the system.

The optional <arg>probe</arg> argument specifies a specific probe to
read. When this is used, only one probe is read, displayed and
returned. In all other cases a table is shown and a list of values is
being returned, even if there is only one probe actually read.

Without any arguments or switches, all probes in the system
are being read and shown.

Filtering.

To reduce the number of probes shown, there are a large number of
command arguments/switches that filters out the non-matching
probes. Many filters can be used in the same command invocation.

{filter_documentation()}

Controlling value output format.

By default, the value displayed, and returned, is formatted as
a string, according to how the probe's suggested human-readable format.

To get the actual (non-formatted) values, the <tt>-values</tt> switch
can be used.

If <tt>-raw-values</tt> is given the raw representation of the probe
will be printed, i.e., for fraction probes the numerator and the
denominator will be printed separately and for histogram probes the
list of keys together with the corresponding value will printed. If
the command is used in an expression these values will also be returned
in CLI lists.
"""),
    sortable_columns = [
        "Probe", "Value"
    ]
)

def print_properties_cmd(obj, probe_name, keys):

    def get_cli_probe(name):
        pl = [c for c in probes.get_all_probes() if c.cli_id == name]
        if pl == []:
            return None
        return pl[0]

    p = get_cli_probe(probe_name)
    if p == None:
        raise CliError(f"Probe {probe_name} not found")

    if keys:
        print(p.get_pretty_props())
        return

    properties = [
        (Table_Key_Columns, [
            [(Column_Key_Name, "Property")],
            [(Column_Key_Name, "Value")],
        ])]

    FD = p.prop.float_decimals
    FP = p.prop.percent
    FM = p.prop.metric
    IB = p.prop.binary
    TR = p.prop.time_fmt

    rep = []
    if FD:
        rep.append(f"Decimals = {FD}")
    if FP:
        rep.append("Percent")
    if FM != None:
        rep.append("Metric Prefix" + (f" {FM}" if FM else ""))
    if IB != None:
        rep.append("Binary Prefix" + (f" {IB}" if IB else ""))
    if TR:
        rep.append("Time Format")

    aggs = []
    for a in p.prop.aggregates:
        f = a.aggregate_function
        s = a.aggregate_scope
        k = a.kind
        aggs.append(f"{k}({s}-{f})")

    data = [
        ["Name", probe_name],
        ["Display Name", p.prop.display_name],
        ["Description", p.prop.desc],
        ["Definition", p.prop.definition],
        ["Type", p.prop.type],
        ["Representation", ", ".join(rep)],
        ["Width", f"{p.prop.width}"],
        ["Categories", " ".join(p.prop.categories)],
        ["Unit", p.prop.unit or ""],
        ["Cause Slowdown", "Yes" if p.prop.cause_slowdown else "No"],
        ["Implementor", p.obj],
        ["Aggregates", ", ".join(aggs)],
    ]

    tab = Table(properties, data)
    print(tab.to_string(no_row_column=True))

new_unsupported_command(
    "print-properties", "internals", print_properties_cmd,
    args = [
        arg(str_t, "probe", expander = probe_expander),
        arg(flag_t, "-show-key-values"),
    ],
    cls = "probes",
    type = ["Probes"],
    short = "print probe properties",
    doc = (
"""Print the properties of a <arg>probe</arg>.

With <tt>-show-key-values</tt> the key value pairs will be printed as
they where implemented by the <iface>probe_interface</iface>, the
<iface>probe_index</iface> interface or the <iface>probe_array</iface>
interface method <fun>properties</fun>.

Without those flags the probe value will be printed without any
particular formatting.
"""))

#
# User defined probe commands
#

def probe_relate_doc(probe_type):
    return f"""For all objects that have the numerator probe and the denominator
    probe (the owner object of the probes is the same) a new
    {probe_type} probe will be created for that object.

    If one of the numerator or denominator probes is a global probe
    (i.e. only one probe exists in the system and it does not belong
    to an object) and the other has an owner object, a new
    {probe_type} probe will be created for the nonomator or
    denominator that has the owner object. Each of the new
    {probe_type} probes for the owner objects will then relate to the
    single global probe as either numerator or denominator.

    If both probes are global only one new global probe will be
    created that is the {probe_type} of the numerator and the
    denominator probes.

    The numerator and denominator must be of the following types: "int",
    "int128", "float", or "fraction"."""

def check_valid_type(probe_kind, pt, valid_types):
    if pt not in valid_types:
        valid_types_str = ", ".join([f'"{t}"' for t in valid_types])
        raise CliError(f'Probe {probe_kind} have type "{pt}", must be one of:'
                       f' {valid_types_str}.')


def check_probe_type(probe_kind, valid_types):
    ps = probes.get_probes(probe_kind)

    if not ps:
        raise CliError(f"Probe {probe_kind} is not defined")

    first = ps[0].prop.type
    check_valid_type(probe_kind, first, valid_types)

def new_percent_cmd(obj, name, display_name, numerator, denominator):
    if probes.get_probes(name):
        raise CliError(f"There is already a probe called {name}")

    valid_types = ["int", "int128", "float", "fraction"]
    check_probe_type(numerator, valid_types)
    check_probe_type(denominator, valid_types)

    if not display_name:
        display_name = name

    templates.add_percent(name, display_name, numerator, denominator)
    return command_return(value = name,
                          message = f"Created new '{name}' probe-kind")

new_command("new-percent-probe", new_percent_cmd,
            args = [arg(str_t, "name"),
                    arg(str_t, "display-name"),
                    arg(str_t, "numerator-probe",
                        expander = probe_kind_expander),
                    arg(str_t, "denominator-probe",
                        expander = probe_kind_expander)],
            cls = "probes",
            type = ["Probes"],
            short = "create new percent probe",
            doc = ("""
Add a new probe-kind called <arg>name</arg> which is the percent of the
<arg>numerator-probe</arg> compared to the <arg>denominator-probe</arg>. The
<arg>display-name</arg> can be used when presenting the probe in a monitor tool
or similar.

""" + probe_relate_doc("percent")))

def new_fraction_probe_cmd(obj, name, display_name, numerator, denominator,
                           factor):
    if probes.get_probes(name):
        raise CliError(f"There is already a probe called {name}")

    valid_types = ["int", "int128", "float", "fraction"]
    check_probe_type(numerator, valid_types)
    check_probe_type(denominator, valid_types)

    if not display_name:
        display_name = name

    templates.add_fraction(name, display_name, numerator, denominator, factor)

new_command("new-fraction-probe", new_fraction_probe_cmd,
            args = [arg(str_t, "name"),
                    arg(str_t, "display-name", "?"),
                    arg(str_t, "numerator-probe",
                        expander = probe_kind_expander),
                    arg(str_t, "denominator-probe",
                        expander = probe_kind_expander),
                    arg(float_t, "extra-factor", "?", 1.0)],
            cls = "probes",
            type = ["Probes"],
            short = "create probe fraction probe",
            doc = (
"""Add a new probe with <arg>name</arg> which is the fraction of the
<arg>numerator-probe</arg> compared to the
<arg>denominator-probe</arg>. The <arg>display-name</arg> can be used
when presenting the probe in a monitor tool or similar. The
<arg>extra-factor</arg> argument can be used to add a factor to the
new fraction probe to scale it. Default extra-factor is 1.

""" + probe_relate_doc("fraction")))


def add_object_fraction(name, display_name, numerator, denominator, factor,
                        owner):
    def get_cli_probe(name):
        pl = [c for c in probes.get_all_probes() if c.cli_id == name]
        if pl == []:
            return None
        return pl[0]

    np = get_cli_probe(numerator)
    if not np:
        raise CliError("numerator probe not found: " + numerator)
    dp = get_cli_probe(denominator)
    if not dp:
        raise CliError("denominator probe not found: " + denominator)

    valid_types = ["int", "int128", "float", "fraction"]
    check_valid_type(np.prop.kind, np.prop.type, valid_types)
    check_valid_type(dp.prop.kind, dp.prop.type, valid_types)

    cause_slowdown = any([np.prop.cause_slowdown, dp.prop.cause_slowdown])
    props = [(Probe_Key_Cause_Slowdown, cause_slowdown)]
    if owner:
        props += [(Probe_Key_Owner_Object, owner)]
        pname = owner.name
    else:
        props += [(Probe_Key_Owner_Object, conf.sim)]
        pname = "probes"

    objs = []
    oname = f"{pname}.probes.{name}"
    objs += sketch.new(
        "probe_fraction_probe", oname,
        [["cname", name],
         ["part", np.id],
         ["total", dp.id],
         ["cprops", listify(props)],
         ["factor", factor]
         ])
    if not objs:
        raise CliError(
            f"Couldn't create fraction object {oname}, already exists?")

    probes.register_dependencies(oname, [np.obj, dp.obj])
    sketch.create_configuration_objects(objs)

def new_fraction_object_probe_cmd(obj, name, display_name,
                                  numerator, denominator, factor, owner):
    if probes.get_probes(name):
        raise CliError(f"There is already a probe called {name}")

    if not display_name:
        display_name = name
    add_object_fraction(name, display_name, numerator, denominator, factor,
                        owner)
    return command_return(value = name,
                          message = f"Created new '{name}' probe-kind")

new_command("new-fraction-object-probe", new_fraction_object_probe_cmd,
            args = [arg(str_t, "name"),
                    arg(str_t, "display-name", "?"),
                    arg(str_t, "numerator-probe",
                        expander = probe_expander),
                    arg(str_t, "denominator-probe",
                        expander = probe_expander),
                    arg(float_t, "extra-factor", "?", 1.0),
                    arg(obj_t("owner"), "owner", "?", None)],
            cls = "probes",
            type = ["Probes"],
            short = "create object specific fraction probe",
            doc = (
""" Add a new probe with <arg>name</arg> which is the fraction of the
<arg>numerator-probe</arg> compared to the
<arg>denominator-probe</arg>. The <arg>display-name</arg> can be used
when presenting the probe in a monitor tool or similar. The
<arg>extra-factor</arg> argument can be used to add a factor to the
new fraction probe to scale it. Default extra-factor is 1.

This numerator and the denominator represents a single probe in
possibly different objects. The syntax for pointing out the probes is
object:probe-name, e.g., board.mb.cpu[0]:cpu.cycles, or just
probe-name if it is a global object.

The <arg>owner</arg> sets the owner of the new fraction probe."""))


# templates.add-attribute class attribute
def attr_name_expander(prefix, _, args):
    if not args[0]:
        return []
    try:
        cls = SIM_get_class(args[0])
    except simics.SimExc_General:
        return []

    valid_types = probe_type_classes.attr_type_to_probe_type.keys()

    return [a[0] for a in cls.attributes
            if a[0].startswith(prefix) and a[3] in valid_types]

def get_attr_info(cls, attribute):
    for info in cls.attributes:
        if info[0] == attribute:
            return info
    return None

def new_attribute_probe_cmd(obj, attr_cls, attribute, name, display_name):
    name = name if name else attribute

    if probes.get_probes(name):
        raise CliError(f"There is already a probe called {name}")

    if hasattr(conf.classes, attr_cls.replace("-", "_")):
        cls = SIM_get_class(attr_cls)
        attr_info = get_attr_info(cls, attribute)

        if attr_info is None:
            raise CliError(f"Class {attr_cls} has no attribute {attribute}")

        # We can only handle simple attributes, not any lists
        valid_types = probe_type_classes.attr_type_to_probe_type.keys()

        attr_type = attr_info[-1]
        if not attr_type in valid_types:
            valid_types_str = ", ".join([f'"{t}"' for t in valid_types])
            raise CliError(f'Attribute {attribute} has type "{attr_type}", must'
                           f' be one of: {valid_types_str}')

    if not display_name:
        display_name = name
    templates.add_attribute(attr_cls, attribute, name, display_name)

    return command_return(value = name,
                          message = f"Created new '{name}' probe-kind")


def class_expander(prefix):
    return get_completions(prefix, SIM_get_all_classes())

def get_attribute_types():
    return ", ".join(
        [f'"{k}"' for k in probe_type_classes.attr_type_to_probe_type])

new_command("new-attribute-probe", new_attribute_probe_cmd,
            args = [arg(str_t, "class", expander = class_expander),
                    arg(str_t, "attribute-name",
                        expander = attr_name_expander),
                    arg(str_t, "name", "?"),
                    arg(str_t, "display-name", "?")],
            cls = "probes",
            type = ["Probes"],
            short = "new attribute based probe",
            doc = (f"""
Creates a new probe with a <arg>name</arg> that uses an attribute as the source
of data. The <arg>class</arg> is the Simics class and the
<arg>attribute-name</arg> is the attribute in the class to use. The
<arg>display-name</arg> can be used when presenting the probe in a monitor tool
or similar.

A new probe will be created for all object of the class that has the
attribute. Only these attribute types are accepted: {get_attribute_types()}."""))

def new_sum_probe_cmd(obj, name, display_name, probe, objs):
    return new_aggregate_probe_cmd(obj, name, display_name, probe, "sum", objs, 10)

# If the probe has been specified, only list the objects which
# implements this probe.
def object_probe_expander(prefix, obj, prev_args):
    (name, display_name, probe, objects) = prev_args
    if probe:
        pprobes = probes.get_probes(probe)
        obj_names = [p.prop.owner_obj.name for p in pprobes]
    else:
        obj_names = visible_objects(recursive=True)
    return get_completions(prefix, obj_names)

def object_probe_aggregator_expander(prefix, obj, prev_args):
    (name, display_name, probe, _, objects, _) = prev_args
    if probe:
        pprobes = probes.get_probes(probe)
        obj_names = [p.prop.owner_obj.name for p in pprobes]
    else:
        obj_names = visible_objects(recursive=True)
    return get_completions(prefix, obj_names)

new_command("new-sum-probe", new_sum_probe_cmd,
            args = [arg(str_t, "name"),
                    arg(str_t, "display-name", "?"),
                    arg(str_t, "probe", expander = probe_kind_expander),
                    arg(obj_t("object"), "objects", "*",
                        expander = object_probe_expander),
                    ],
            cls = "probes",
            type = ["Probes"],
            short = "create new sum probe",
            doc = ("""
Creates a new global probe-kind with a <arg>name</arg> that will be the sum
of all probes with the probe-kind <arg>probe</arg>.

The <arg>display-name</arg> can be used when presenting the probe in a
monitor tool or similar.

The <arg>objects</arg> argument is optional, if used, only the specified
objects will be part of the sum.

This command is deprecated, use new-aggregate-probe instead.
 """))

def new_aggregate_probe_cmd(obj, new_probe_kind, display_name, agg_probe_kind,
                            function, objects, width):
    if not display_name:
        display_name = new_probe_kind

    if probes.get_probes(new_probe_kind):
        raise CliError(f"There is already a probe called {new_probe_kind}")

    ps = probes.get_probes(agg_probe_kind)
    if not ps:
        raise CliError(f"No {new_probe_kind} probe-kind exists")

    for o in objects:
        if not probes.get_probe_by_object(agg_probe_kind, o):
            raise CliError(f"Object {o.name} does not have a {agg_probe_kind} probe-kind")


    obj_names = [o.name for o in objects]
    p = ps[0]         # Pick the key-value definition from first found

    # Check that the function used for aggregation is really
    # implemented in the probe type.
    if not probe_type_classes.supports_aggregate_function(
            p.prop.type, function):
        raise CliError(
            f"Probe {agg_probe_kind} (type {p.prop.type}) does not"
            f" support {function}")

    histogram_probe = function in ['object-histogram', 'class-histogram']
    if width is None:
        width = 40 if histogram_probe else 10

    new_props = [
        (Probe_Key_Type, "histogram" if histogram_probe else p.prop.type),
        (Probe_Key_Width, width),
        (Probe_Key_Display_Name, display_name),
        (Probe_Key_Owner_Object, conf.sim)]

    keys = probes.inherit_aggregate_keys_from_base_probe(
                    p.prop.key_value_def,
                    new_props)

    templates.add_aggregate(new_probe_kind, display_name, agg_probe_kind, function, obj_names, keys)
    return command_return(value = new_probe_kind,
                          message = f"Created new '{new_probe_kind}' probe-kind")


# Get hold of which aggregate functions that supports which underlying probe
# types
def get_aggregate_description():
    probe_types = probe_type_classes.probe_type_to_class.keys()
    supported_types = {}
    for f in probe_type_classes.defined_aggregator_functions:
        types = []
        for t in probe_types:
            if probe_type_classes.function_map.get(t).get(f) != None:
                types.append(t)
            supported_types[f] = sorted(types)

    aggregate_description = ""
    for (k, v) in probe_type_classes.aggregator_descriptions.items():
        types = ", ".join(supported_types[k])
        aggregate_description += f"<b>{k}:</b> {v} Valid probe types: {types}.\n\n"
    return aggregate_description

new_command("new-aggregate-probe", new_aggregate_probe_cmd,
            args = [arg(str_t, "name"),
                    arg(str_t, "display-name", "?"),
                    arg(str_t, "probe", expander = probe_kind_expander),
                    arg(string_set_t(
                        probe_type_classes.get_supported_aggregator_functions()),
                        "function"),
                    arg(obj_t("object"), "objects", "*",
                        expander = object_probe_aggregator_expander),
                    arg(int_t, "width", "?", None),
                    ],
            cls = "probes",
            type = ["Probes"],
            short = "create new aggregate probe",
            doc = (f"""
Creates a new global probe with a <arg>name</arg> that will be the aggregate
of all probes with the name <arg>probe</arg> using the <arg>function</arg>.
The following aggregator functions are supported:

{get_aggregate_description()}
The <arg>display-name</arg> can be used when presenting the probe in a
monitor tool or similar.

The <arg>objects</arg> argument is optional, if used, only the specified
objects will be part of the sum.

The display width (used by probe-monitors) can be set by the <arg>width</arg>
argument. If not set it will default to 10 character for scalar probes and 40
for histograms."""))
