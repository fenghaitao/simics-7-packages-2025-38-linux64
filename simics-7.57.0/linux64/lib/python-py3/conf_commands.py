# © 2023 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and
# your use of them is governed by the express license under which they were
# provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software
# or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or
# implied warranties, other than those that are expressly stated in the License.

import codecs
import io
import os
import pathlib
import re
import sys
import traceback

from alias_util import user_defined_aliases
import checkpoint_info
import cli
import simics
import conf
import table
import targets
import cli_impl
from deprecation import DEPRECATED
import refmanual
from simicsutils.internal import is_checkpoint_bundle

from simics import (
    SIM_VERSION_5,
    SIM_VERSION_6,
    SIM_VERSION_7,
    SIM_get_all_classes,
    SIM_get_all_modules,
    SIM_get_object,
    SIM_native_path,
    SIM_object_iterator,

    Column_Key_Alignment,
    Column_Key_Hide_Homogeneous,
    Column_Key_Int_Grouping,
    Column_Key_Int_Radix,
    Column_Key_Name,
    Table_Key_Columns,
)

from cli import (
    arg,
    filename_t,
    flag_t,
    int_t,
    nil_t,
    obj_t,
    poly_t,
    str_t,
    string_set_t,
    uint_t,

    command_return,
    command_verbose_return,
    print_columns,
)

from sim_commands import (
    abbrev_size,
    all_known_interfaces,
    class_exists,
    component_arg_deprecation,
    conf_class_expander,
    iface_expander,
    internal_classes,
    object_expander,
)

from img_commands import (
    expand_checkpoint_path,
    set_persistent_data,
    with_cwd,
)

#
# -------------------- l --------------------
#

def l_cmd(long_fmt):
    ns = cli.current_namespace()
    base = SIM_get_object(ns) if ns else None
    offs = len(ns) if ns else 0
    def oname(x):
        s = x.name[offs:]
        if s[0] == ".":
            s = s[1:]
        if hasattr(x.iface, "component"):
            s += "/"
        elif hasattr(x.iface, "connector"):
            s += "*"
        return s

    objs = [x for x in simics.CORE_shallow_object_iterator(base, True)]
    def pr_help():
        if long_fmt:
            print_columns('ll', [["<{}>".format(x.classname), oname(x)]
                                 for x in objs],
                          has_title = False, wrap_space = '    ')
        else:
            print_columns('l', [oname(x) for x in objs],
                          has_title = False, wrap_space = '  ')
        return " "
    return command_verbose_return(pr_help, objs)

def ll_cmd():
    return l_cmd(long_fmt = True)

cli.new_command("l", l_cmd,
            [arg(flag_t, "-l"), ],
            type = ["Configuration"],
            short = "list namespace objects",
            see_also = ["list-objects", "change-namespace",
                        "ll"],
            doc = """
Lists objects in the current namespace. Classnames are included
in the output if the <tt>-l</tt> flag is used.
""")

cli.new_command("ll", ll_cmd,
            [],
            type = ["Configuration"],
            short = "list namespace objects",
            see_also = ["list-objects", "change-namespace"],
            doc = """
Lists objects in the current namespace. Class information is included in
the output. This command is a shorthand for <cmd>l -l</cmd>
""")


#
# -------------------- list-objects --------------------
#

class tree_node:
    def __init__(self, name, obj = None):
        self._name = name
        self._obj = obj
        self._subtrees = {}

    def reset_name(self, name):
        self._name = name

    def subtree(self, name):
        if not name in self._subtrees:
            self._subtrees[name] = tree_node(name)
        return self._subtrees[name]

    def items(self):
        return self._subtrees.items()

    def keys(self):
        return self._subtrees.keys()

    def is_subtree(self, name):
        return name in self._subtrees

    def set_object(self, obj):
        self._obj = obj

    def is_leaf(self):
        return len(self._subtrees) == 0

    def name(self):
        if self._obj:
            return f"{self._name} ({self._obj.classname})"
        return self._name

    def pop(self, name):
        self._subtrees.pop(name)

    def push(self, node):
        self._subtrees[node._name] = node

def sortable_array_name(name):

    def extract_num(txt):
        try:
            return "%08d" % int(txt.split('..')[0])
        except:
            return txt

    parts = name.split('[')
    sname = ""
    for p in parts:
        pp = p.split(']')
        sname += extract_num(pp[0]) + pp[1] if len(pp) > 1 else p
    return sname

def print_object_list(comp, objs, classname_sort, c_desc):
    def table_items():
        for (s, o) in objs.items():
            isalias = user_defined_aliases().get(s, None) == o.name and s != o.name
            name = s if isalias else o.name
            yield [o.classname,
                   sortable_array_name(name),
                   name + f' (alias for {o.name})' * isalias,
                   o.class_desc if o.class_desc and c_desc else '']

    l = list(table_items())
    if classname_sort:
        l.sort()
    else:
        l.sort(key=lambda x: x[1])

    props = [(
        Table_Key_Columns,
        # If all class descriptions are empty, only show the class description
        # column if requested (c_desc), to indicate missing descriptions.
        [[(Column_Key_Name, h)] if c_desc else [
            (Column_Key_Name, h), (Column_Key_Hide_Homogeneous, "")] for h in [
                    "Object",
                    "Component Class" if comp else "Class",
                    "Class description"]])]

    # Add <> to class name after sorting, to obtain correct order for
    # hierarchical objects, with . in the classname.
    tbl = table.Table(props, [[o, f"<{c}>", d] for (c, _, o, d) in l])
    return tbl.to_string(rows_printed=0, no_row_column=True)

def obj_cls_name_match(substr, name):
    # check if substr is part of the object/class name (treating - as _)
    return (name.replace("-", "_").find(substr.replace("-", "_")) >= 0)

def iface_match(obj, iface_name):
    if not iface_name:
        return True
    if hasattr(obj.iface, iface_name):
        return True
    for port_name in set(obj.ports):
        port = getattr(obj.ports, port_name)
        if hasattr(port, iface_name):
            return True
        elif hasattr(port, "__getitem__"):
            # port array
            for p in port:
                if (hasattr(p, iface_name)):
                    return True
    return False

def cls_match(obj, cls):
    return not cls or obj.classname == cls

def array_sorted(keys):
    x = {sortable_array_name(k): k for k in keys}
    return [x[k] for k in sorted(x.keys())]

def print_tree(tree, prefix, name_prefix, name, output, max_depth):
    if max_depth is not None:
        if max_depth >= 0:
            max_depth -= 1
        else:
            return
    slots = array_sorted(tree.keys())
    num_slots = len(slots)
    if num_slots == 0 or (max_depth is not None and max_depth < 0):
        print(name_prefix + name, file=output)
    else:
        print(name_prefix + name + "┐", file=output)
    spaces = " " * len(name)

    for (i, slot) in enumerate(slots):
        subtree = tree.subtree(slot)
        if i == num_slots - 1:
            print_tree(subtree, prefix + spaces + " ",
                       prefix + spaces + "└", f" {subtree.name()} ", output,
                       max_depth)
        else:
            print_tree(subtree, prefix + spaces + "│",
                       prefix + spaces + "├", f" {subtree.name()} ", output,
                       max_depth)

def find_index_ranges(indicies):
    ranges = []
    start = 0
    while((len(indicies) - start) > 1):
        end = start + 1
        while(end < len(indicies)
              and (indicies[end] - indicies[start]) == (end - start)):
            end += 1
        if end - start > 1:
            ranges.append((indicies[start], indicies[end-1]))
        start = end
    return ranges

def combine_arrays(tree):
    leaf_array_nodes = {}

    for node, subtree in tree.items():
        if not subtree.is_leaf():
            combine_arrays(subtree)
        else:
            m = re.search(r"(\w*)\[(\d+)\]$", node)
            if m:
                node_base = m[1]
                index = int(m[2])
                if node_base not in leaf_array_nodes:
                    leaf_array_nodes[node_base] = []
                leaf_array_nodes[node_base].append(index)

    for node_base in leaf_array_nodes:
        for s,e in find_index_ranges(sorted(leaf_array_nodes[node_base])):
            subtree = tree.subtree(f"{node_base}[{s}]")
            subtree.reset_name(f"{node_base}[{s}..{e}]")
            for i in range(s,e+1):
                tree.pop(f"{node_base}[{i}]")
            tree.push(subtree)

def is_port_object(obj):
    contains = [".port.", ".bank.", ".impl.", ".probes."]
    if simics.SIM_port_object_parent(obj):
        if [p for p in contains if p in obj.name]:
            return True
        if obj.name[-7:] == '.probes':
            return True
        if obj.name[-6:] == '.vtime':
            return True
        if obj.name[-13:] == '.vtime.cycles' or obj.name[-9:] == '.vtime.ps':
            return True
    return False

def print_object_tree(objs, expand_all, with_class_names, max_depth):
    # Make dict tree of all
    top = tree_node("")

    for name, obj in objs.items():
        isalias = (user_defined_aliases().get(name, None) == obj.name
                   and name != obj.name)
        if isalias:
            d = top.subtree(name + f' (alias for {obj.name})')
        else:
            # split multi-dimensional arrays in "objects" to better show the
            # levels of the arrays
            name = name.replace("][", "].[")

            d = top
            for p in name.split("."):
                d = d.subtree(p)

        if with_class_names and obj and not is_port_object(obj):
            d.set_object(obj)

    if not expand_all:
        combine_arrays(top)

    output = io.StringIO()
    print_tree(top, "", "", "", output, max_depth)
    msg = output.getvalue()
    output.close()
    return msg

# Given an iterable of (name, object) pairs, returns a corresponding dict,
# filtered such that any duplicates due to aliases are removed. Non-alias
# names are prioritized
def nub_visible_objects(objs):
    by_object = {}
    aliases = user_defined_aliases()
    for (s, o) in objs:
        isalias = aliases.get(s, None) == o.name and s != o.name
        if isalias:
            by_object.setdefault(o, [None, []])[1].append(s)
        else:
            by_object.setdefault(o, [None, []])[0] = s
    return {tn if tn is not None else min(aliases): o
            for (o, [tn, aliases]) in by_object.items()}

def list_objects(objs, classname_sort, a_flag, tree, class_desc, expand_all,
                 with_class_name, max_depth):
    if tree:
        return print_object_tree(objs, expand_all, with_class_name, max_depth)

    msg = ""
    if not a_flag:
        # Print the components separately, and remove them from the
        # objs dictionary so that we won't print them again.
        orig = objs
        objs = {}
        comps = {}
        for s, o in orig.items():
            (comps if cli.is_component(o) else objs)[s] = o
        if comps:
            msg = print_object_list(True, comps, classname_sort, class_desc) + "\n"

    # Print the remaining objects.
    if objs:
        msg += print_object_list(False, objs, classname_sort, class_desc)
    return msg

def invisible_namespace(obj, cls):
    name = obj.name
    return (cls != 'namespace' and cls_match(obj, "namespace")
            and name[-5:] in {'.port', '.bank', '.impl'})

def port_match(obj, port_name):
    if not port_name:
        return True
    if hasattr(obj.iface, port_name):
        if any(x in obj.name for x in {".port.", ".bank.", ".impl."}):
            return True
    for port in obj.ports.__dict__:
        tmp = getattr(obj.ports, port)
        if hasattr(tmp, port_name):
            return True
        elif hasattr(tmp, "__getitem__"):
            # port array
            for p in tmp:
                if (hasattr(p, port_name)):
                    return True
    return False

def find_objects(cls, iface, namespace, substr, all_flag, recursive,
                 hideports=False, port=""):
    objs = cli.visible_objects(component=namespace, all=all_flag,
                               recursive=recursive, ports=True,
                               include_root=False)
    invisible = set(internal_classes()) - set([cls])
    return {name: obj for (name, obj) in objs.items()
            if (obj_cls_name_match(substr, name)
                and iface_match(obj, iface)
                and port_match(obj, port)
                and cls_match(obj, cls)
                and not (hideports
                        and (is_port_object(obj) and port == ""))
                and not invisible_namespace(obj, cls)
                and not any(cls_match(obj, c) for c in invisible))}

def list_objects_cmd(cls, namespace, substr, max_depth,
                     all_flag, classname_sort,
                     a_flag, recursive, tree, hideports, class_desc,
                     expand_all, with_class_name,
                     local, show_ports, ifaces, ports=""):
    namespace = component_arg_deprecation(
        namespace, None, "list-objects")

    if max_depth is not None and not tree:
        raise cli.CliError('The "max-depth" parameter is only valid'
                       ' for tree output')

    if recursive:
        if local:
            raise cli.CliError("The -recursive and -local flags are mutually"
                           " exclusive.")
        DEPRECATED(SIM_VERSION_6,
                   "The -recursive flag is deprecated.",
                   "It is the default, use -local to turn it off")
    else:
        # Default is to display all objects
        recursive = not local

    if hideports:
        if show_ports:
            raise cli.CliError("The -hide-port-objects and -show-port-objects"
                               " flags are mutually exclusive.")
        DEPRECATED(SIM_VERSION_6,
                   "The -hide-port-objects flag is deprecated.",
                   "It is the default, use -show-port-objects to turn it off")
    else:
        hideports = not show_ports

    if all_flag:
        hideports = False

    if cls and not class_exists(cls):
        raise cli.CliError(f"Class '{cls}' not registered by any loadable module")
    for ifc in ifaces:
        # ifc may be an empty string if this function is invoked such as
        # cli.global_cmds.list_objects(**{'class': 'sim'}) because
        # cli_impl.py:wrap_cli_cmd_impl treats lists as poly arguments
        if ifc and ifc not in all_known_interfaces():
            raise cli.CliError(f"Interface '{ifc}' not registered"
                           " by any loaded class")

    for port in ports:
        if port and port not in all_known_interfaces():
            raise cli.CliError(f"Port '{port}' not registered")

    objs = set(
        find_objects(cls, "", namespace, substr,
                     all_flag, recursive or tree, hideports, "").items())

    for ifc in ifaces:
        objs.intersection_update(set(
            find_objects(cls, ifc, namespace, substr,
                         all_flag, recursive or tree, hideports,
                         "").items()))

    for port in ports:
        objs.intersection_update(set(
            find_objects(cls, "", namespace, substr,
                         all_flag, recursive or tree, hideports,
                         port).items()))

    objs = nub_visible_objects(objs)
    msg = list_objects(objs, classname_sort, a_flag, tree, class_desc,
                       expand_all, with_class_name, max_depth)

    if classname_sort:
        l = sorted(objs.values(), key=lambda o: (o.classname, o))
    else:
        l = sorted(objs.values())
    return cli.command_verbose_return(message = msg, value = l)

object_list_doc_common = """
By default, only the objects in the current namespace are listed (see the
<cmd>change-namespace</cmd> command). The <arg>namespace</arg> argument can be
used to override the current namespace.)

When the <arg>namespace</arg> argument is used, objects in standard
sub-namespaces are always included, e.g. <tt>list-objects
namespace=DEV</tt> will always include objects hierarchies rooted at
<tt>DEV.bank</tt>, <tt>DEV.port</tt> and <tt>DEV.impl</tt>.

Objects of class """ + ", ".join("<class>{}</class>".format(c)
                                 for c in internal_classes()) + """
are only listed if specifically asked for, using the
<arg>class</arg> argument.

If the optional <arg>substr</arg> argument is specified, only objects with a
name matching this sub-string will be printed. The current namespace part of
the object name will not be included in the name matched against.

The default is to list objects in the current namespace as well as
namespaces below, i.e. list the whole tree rooted at the given
namespace. Use the <tt>-local</tt> flag to only list the current
namespace.

The <tt>-show-port-objects</tt> flag will include port objects in the
result; this includes "port", "bank", and "impl" objects.

With the <tt>-all</tt> flag, all objects are listed, regardless of namespace.
This implies the <tt>-show-port-objects</tt> flag.
"""

cli.new_command("list-objects", list_objects_cmd,
            [arg(str_t, "class", "?", "", expander = conf_class_expander()),
             arg(obj_t('namespace'), 'namespace', '?'),
             arg(str_t,"substr","?",""),
             arg(uint_t, 'max-depth', '?'),
             arg(flag_t, '-all'),
             arg(flag_t, "-sort-by-classname"),
             arg(flag_t, "-a"),
             arg(flag_t, '-recursive'),
             arg(flag_t, '-tree'),
             arg(flag_t, '-hide-port-objects'),
             arg(flag_t, '-class-desc'),
             arg(flag_t, '-expand-all'),
             arg(flag_t, '-with-class-name'),
             arg(flag_t, '-local'),
             arg(flag_t, '-show-port-objects'),
             arg(str_t, "iface", "*", expander = iface_expander),
             arg(str_t, "port", "*", expander = iface_expander)],
            type = ["Configuration"],
            short = "list objects",
            see_also = ["change-namespace", "l", "ll"],
            doc = (
"""
Lists configuration objects and the classes they belong to. With the
<arg>class</arg>, <arg>iface</arg> and <arg>port</arg> arguments, you can
restrict the listing to objects of a particular class, or to objects that
implement particular interfaces. Notice, the <arg>iface</arg> argument must
come last on the line.
"""
                + object_list_doc_common +
"""
By default objects are sorted by name. The
<tt>-sort-by-classname</tt> flag sorts them by class name instead.

Component objects are printed first and then all other objects. Use the
<tt>-a</tt> flag to mix all objects in the same list.

The <tt>-tree</tt> flag prints a tree of all the objects descending
from the current namespace. This implies <tt>-recursive</tt>. If
<tt>-all</tt> is given the tree will start from the root. Objects not
belonging to any hierarchy will be put in the root node. Arrays of
leaf objects will be summarized unless <tt>-expand-all</tt> is
given. With the <tt>-with-class-name</tt> flag class names are added
to all non port objects. The <arg>max-depth</arg> argument can be used
to only traverse the object tree up to the given depth.

The <tt>-class-desc</tt> flag will include a short description in the result.

The <tt>port</tt> argument selects objects that have all the interfaces
specified as port/bank. Writing <tt>list-objects port=signal</tt> will
return <tt>obj.port/bank.RESET</tt> if <tt>RESET</tt> is type interface
<tt>signal</tt>, as well as the root object <tt>obj</tt>.

The <cmd>list-objects</cmd> command returns a list of objects
when used in an expression."""))

def list_persistent_images():
    def get_table_line(img):
        return [img,
                abbrev_size(img.size),
                "yes" if img.attr.dirty else "no",
                "\n".join(f"{expand_checkpoint_path(f[0])} ({f[1]})"
                          for f in img.files)]

    images = sorted(img for img in simics.SIM_object_iterator_for_class('image')
                    if img.iface.checkpoint.has_persistent_data())
    if not images:
        return cli.command_verbose_return(
            message = 'No image objects with persistent data are found',
            value = [])
    data = [get_table_line(img) for img in images]
    header = [("Image", "left"),
              ("Size", "right"),
              ("Unsaved data", "right"),
              ("File(s) (read-only/read-write)", "left")]
    properties = [(table.Table_Key_Columns,
                   [[(table.Column_Key_Name, n),
                     (table.Column_Key_Alignment, a)]
                    for (n, a) in header])]
    result_table = table.Table(properties, data)
    msgstring = result_table.to_string(rows_printed=0, no_row_column=True)
    return cli.command_verbose_return(message = msgstring,
                                      value = images)

cli.new_command("list-persistent-images", list_persistent_images,
                type  = ["Configuration"],
                short = 'show information about images with "persistent" data',
                see_also = ["list-objects"],
                doc = """The command shows information about objects of
the <class>image</class> class which have "persistent" data, i.e. data that
survive reboots. Such <class>image</class> objects are typically
found in device models having non-volatile memory: disks, flash memories,
non-volatile BIOS memories. The data from such images is saved as a part of
a state saved by the <cmd>save-persistent-state</cmd> command.

When the command is used in an expression the list of objects is returned.

NB: for images with at least one read-write file the "Unsaved data" value is
always 'no' since Simics will automatically write any new data to the file.""")

#
# -------------------- load-module --------------------
#


def module_expander(prefix):
    nonloaded = [mod[0] for mod in SIM_get_all_modules() if not mod[2]]
    return cli.get_completions(prefix, nonloaded)

def all_class_expander(prefix):
    return cli.get_completions(prefix, simics.CORE_get_all_known_module_classes())


def load_module_cmd(module_or_class):
    if simics.VT_outside_execution_context_violation():
        raise cli.CliError('load-module command is disallowed in Cell Context')

    (_, value, variant) = module_or_class
    class_modules = (
        simics.VT_get_all_implementing_modules(value)
        + simics.VT_get_all_implementing_modules(value.replace("-", "_")))
    class_module = class_modules[0] if class_modules else None

    if variant == "class":
        if not class_module:
            raise cli.CliError(f"Unknown class: {value}")
        module = class_module
    else:
        all_mods = [x[0] for x in SIM_get_all_modules()]
        module = value if value in all_mods else None

    module = module or class_module
    if not module:
        raise cli.CliError(f"Unknown module: {value}")

    try:
        simics.SIM_load_module(module)
    except Exception as ex:
        raise cli.CliError(str(ex))

    if value != module and module == class_module:
        extra = f" (defining class {value})"
    else:
        extra = ""
    return command_return(message = f"{module} module loaded" + extra,
                          value = module)

cli.new_command("load-module", load_module_cmd,
            args = (
                arg((str_t, str_t), ("module", "class"),
                    expander = (module_expander, all_class_expander)),
            ),
            type = ["Configuration", "Modules"],
            see_also = ["list-modules", "list-failed-modules",
                        "module-list-refresh", "add-module-directory"],
            short = "load module into Simics",
            doc = """
Load the specified <arg>module</arg>.

Normally, modules are loaded automatically as needed
for the configuration classes they implement, and there is rarely any need
to call this function explicitly.

By specifying <arg>class</arg>, the module implementing the specified
class will be loaded.

Read the <cite>Simics Model Builder User's Guide</cite> for more
information on how to write modules.
""")

#
# -------------------- list-modules --------------------
#

def module_list_cmd(substr, pkg_num, loaded, verbose, threadsafe):
    mods = [x for x in SIM_get_all_modules() if x[0].find(substr) >= 0]
    if len(mods) == 0:
        print("No modules %sfound." % (
            ('matching pattern "%s" ' % substr) if len(substr) else ''))
        return command_verbose_return("", [])

    # Map path to package name
    pkg_paths = {os.path.abspath(p[9]): p[0] for p in conf.sim.package_info
                 if (pkg_num == 0 or pkg_num == p[2])}

    info = []
    for mod in mods:
        (name, path, report_loaded, compat, usr_ver, build_id,
         build_date, classes, thread_safe, cmps, user_path) = mod[:11]
        # see SIMICS-10153
        (bid_ns, api, abi, shadowing) = simics.CORE_get_extra_module_info(name)[:4]
        base_path = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(path))))

        if pkg_num and base_path not in pkg_paths:
            continue
        if loaded and not report_loaded:
            continue

        if thread_safe:
            safe = "Yes"
        else:
            safe = "No"
        if threadsafe not in safe.lower():
            continue
        if bid_ns == '__simics_project__':
            bid_text = 'project'
        elif bid_ns == 'simics':
            bid_text = build_id
        else:
            bid_text = "%s:%d" % (bid_ns, build_id)
        line = [name,
                'Loaded' if report_loaded else '',
                bid_text,
                abi if abi else "?",
                compat,
                api if api else "?",
                safe,
                usr_ver if usr_ver else '',
                pkg_paths[base_path] if base_path in pkg_paths else ""]
        if verbose:
            line.append(path)
            line.append("Yes" if shadowing else "")
        info.append(line)

    if not info:
        return command_verbose_return("", [])

    info.sort()
    title = ['Name', 'Status', 'Build\nID', 'ABI', 'Compat', 'API',
             'Thread\nsafe', 'User\nVersion', 'Package']
    if verbose:
        title += ['Path', 'Shadowing']

    props = [(Table_Key_Columns,
              [[(Column_Key_Name, h), (Column_Key_Int_Radix, 10),
                (Column_Key_Int_Grouping, False)]
               for h in title])]
    tbl = table.Table(props, info)
    msg = tbl.to_string(rows_printed=0, no_row_column=True)
    val = info if verbose else [x[0] for x in info]
    return command_verbose_return(msg, val)

cli.new_command("list-modules", module_list_cmd,
            [arg(str_t,"substr","?",""),
             arg(int_t,"package-number","?",0),
             arg(flag_t,"-l"),
             arg(flag_t,"-v"),
             arg(string_set_t(["yes", "no"]), "thread-safe", "?", "")],
            alias = "module-list",
            type = ["Configuration", "Modules"],
            see_also = ['list-failed-modules', 'module-list-refresh',
                        'load-module', 'add-module-directory'],
            short = "list loadable modules",
            doc = """
Lists all modules that can be loaded into Simics. If the <arg>substr</arg>
argument is specified, only modules with a matching name will be listed. If a
<arg>package-number</arg> is specified, only modules from that package will
be listed.

Use <tt>-l</tt> to only list loaded modules and <tt>-v</tt> to enable
verbose output, which includes the module file system path, package
name if the module comes from a package, and if the module shadows
another module (which will be listed by <cmd>list-failed-modules</cmd>).

"Build ID" is the module-specific build ID, defaulting to the build-ID of the
Simics package that the module was compiled with. The full build-ID reads for
example "namespace:1234", except for Simics modules which displays just the
integer part.

The "ABI" column is the build-ID of the Simics package
that the module was compiled with.

The "Compat" column is the oldest Simics ABI version the module is binary
compatible with. Note that a module with a low "compat" value may still
require a later version of Simics for API functions that were introduced later
on.

The "API" column is the API version that was set in the modules' makefile.

The "Thread-safe" column shows whether the module has been tagged as thread
safe, "Yes" or "No". Use the <arg>thread-safe</arg> argument to filter on
this column.

The "User Version" column shows the user defined version string (if any)
which was provided in the MODULE_USER_VERSION variable in the module's
<file>Makefile</file>.

When used in an expression, a list of module names is returned, or a list of
[&lt;module name>, &lt;loaded status>, &lt;build ID>, &lt;ABI>, &lt;compat>,
&lt;API>, &lt;thread-safe>, &lt;user version>, &lt;path>, &lt;package>,
&lt;shadowing>] entries if <tt>-v</tt> is specified.""")

#
# -------------------- list-failed-modules --------------------
#

def module_list_failed_cmd(substr, verbose):

    mods = [x for x in simics.SIM_get_all_failed_modules() if substr in x[0]]
    if len(mods) == 0:
        msg = "No failed modules {0}found.".format(
            (f'matching pattern "{substr}s" ') if len(substr) else '')
        return command_return(msg, [])

    # Map path to package name
    pkg_paths = {p[9]: p[0] for p in conf.sim.package_info}

    mod_infos = {x[0]: x for x in SIM_get_all_modules()
                               if x[0] in [m[0] for m in mods]}
    errors = []
    for mod in mods:
        (name, path, dup, fail, compat, build_id, _, usr_ver, fail_reason) = mod
        safe = mod_infos[name][8] if name in mod_infos and name else 'unknown'
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(path)))
        if not name:
            # no name means broken metadata; this means the module
            # doesn't have a name, so print a clue.
            name = f'[{os.path.basename(path)}]'
        if fail:
            msg = fail_reason or 'unknown linker error'
        elif compat and compat != conf.sim.version_compat:
            msg = f'Unsupported Simics ABI version: {compat}'
        elif dup:
            msg = 'Duplicated module'
        elif fail_reason:
            msg = fail_reason
        else:
            msg = 'Unknown failure'
        line = [name,
                msg,
                build_id,
                compat,
                safe,
                usr_ver if usr_ver else '',
                pkg_paths[base_path] if base_path in pkg_paths else ""]
        if verbose:
            line.append(path)
        errors.append(line)

    errors.sort()
    title = ['Name', 'Error', 'Build\nID', 'Compat',
             'Thread\nsafe', 'User\nVersion', 'Package']
    if verbose:
        title.append('Path')
    props = [(Table_Key_Columns, [[(Column_Key_Name, h)] for h in title])]
    tbl = table.Table(props, errors)
    msg = f"Current ABI version: {conf.sim.version}  " \
        + f"Lowest supported: {conf.sim.version_compat}\n"
    msg += tbl.to_string(rows_printed=0, no_row_column=True)
    return command_verbose_return(msg, errors)

cli.new_command("list-failed-modules", module_list_failed_cmd,
            [arg(str_t, "substr", "?", ""),
             arg(flag_t, "-v")],
            alias="module-list-failed",
            type=["Configuration", "Modules"],
            see_also=["list-modules", "module-list-refresh", "load-module",
                      "add-module-directory"],
            short="list the modules that are not loadable",
            # Whenever you change the columns, make sure to update the
            # example in the programming guide.
            doc="""
Lists the modules (Simics extensions) that are not loadable,
optionally only those matching <arg>substr</arg>.

Similar to <cmd>list-modules</cmd> but shows modules that will not load into
Simics, and the reason why Simics refuses to load them (e.g., missing symbol,
wrong version, ...).

If the <tt>-v</tt> flag is specified, show verbose information, with the full
path to the module file and any library loader error message.

The <tt>MODULE</tt> column contains the name of the module or the filename of the
shared library file if the module name could not be established.

If the module has the same name as another module, an <tt>X</tt> will
be printed in the <tt>DUP</tt> column.

If the module could not be loaded since it was compiled or written for
a different version of Simics, the version it was built for will be
printed in the <tt>VERSION</tt> column.

The <tt>USR_VERS</tt> will contain the user version string, if provided.

The <tt>LINK</tt> column contains any linker error (cf. the <tt>dlerror(3)</tt>
manpage).

When the <tt>-v</tt> flag is provided, the <tt>PATH</tt> column will contain
linker information for the module.

When this command is used in an expression a list of the errors is returned.
""")

#
# -------------------- module-list-refresh --------------------
#

def module_list_refresh_cmd():
    simics.SIM_module_list_refresh()
    cli_impl.check_for_gcommands()

cli.new_command("module-list-refresh", module_list_refresh_cmd,
            [], # module-list-refresh
            type = ["Configuration", "Modules"],
            short = "create a new list of loadable modules",
            see_also = ["list-modules", "list-failed-modules", "load-module"],
            doc = """
Refresh (reload) the list of all Simics modules.<br/>
This command causes Simics to re-query all modules currently
not loaded. This can be used after changing or
adding a module that Simics, when started, considered as
non-loadable.""")


#
# -------------------- read-configuration --------------------
#

import update_checkpoint

class ObjNameError(cli.CliError):
    pass

def read_configuration(file, prefix = ""):
    objects = simics.VT_get_configuration(file)

    conf_names = {prefix + s for s in objects}
    existing_names = {o.name for o in SIM_object_iterator(None)
                      if not simics.CORE_is_permanent_object_name(o.name)}
    clashes = conf_names & existing_names
    if clashes:
        example = sorted(clashes)[0]
        errstr = ("The checkpoint %s contains an object named %s,"
                  " but an object by that name already exists."
                  % (file, example))
        if prefix:
            errstr += " Try using a different prefix."
        else:
            errstr += " Try adding a prefix."
        raise ObjNameError(errstr)

    if prefix:
        new_objects = {}
        for (n, o) in objects.items():
            if simics.CORE_is_permanent_object_name(n):
                new_objects[n] = o   # Keep 'as is'
            else:
                o.name = prefix + n  # New prefixed name
                if hasattr(o, 'object_id'):
                    o.object_id = prefix + o.object_id
                new_objects[o.name] = o
        objects = new_objects

    try:
        update_checkpoint.update_configuration(objects, file)
    except cli.CliError:
        raise
    except Exception as ex:
        # unexpected error, simplify debugging
        traceback.print_exc(file = sys.stdout)
        raise cli.CliError("Failed updating configuration: %s" % ex)
    simics.SIM_add_configuration(objects, file)

def wrap_read_configuration(file, prefix = ""):
    simics.VT_set_restoring_state(True)
    try:
        # Set prioritized packages before any modules are loaded
        info = checkpoint_info.load_checkpoint_info(file)
    except simics.SimExc_General:
        # not critical if checkpoint info fails to load
        info = {}
    conf.sim.prioritized_packages += info.get('prioritized_packages', [])
    try:
        read_configuration(file, prefix)
    finally:
        simics.VT_set_restoring_state(False)

def load_session_from_checkpoint(filename):
    import recording_commands
    # Load session comments, if any
    sessfile = os.path.join(filename, "session_comments")
    if os.path.exists(sessfile):
        objects = simics.VT_get_configuration(sessfile)
        pre_sim = [x for x in list(objects.values()) if x.__class_name__ == 'sim'][0]
        for comment in pre_sim.session_comments:
            # Add loaded comments to the existing ones, avoiding duplicates
            if not comment in conf.sim.session_comments:
                conf.sim.session_comments.append(comment)
    # If there is a recording saved with the checkpoint, load it together with
    # comments associated with the recorded future.
    recfile = os.path.join(filename, "recording")
    if not os.path.exists(recfile):
        return (True, "")  # This is ok, don't say anything
    if recording_commands.playback_active():
        return (None, "Already replaying input,"
                " ignoring recording in checkpoint")
    recording_commands.start_playback_cmd(recfile)
    return (False, "Playback of recorded session from checkpoint started")

def read_configuration_cmd(file, prefix = ""):
    cli.assert_not_running()
    try:
        wrap_read_configuration(file, prefix)
    except ObjNameError as ex:
        raise cli.CliError("Configuration not loaded: %s" % ex)
    except Exception as ex:
        raise cli.CliError("Failed reading configuration: %s\n"
                       "This has left the configuration system in an "
                       "inconsistent state.\n"
                       "Restarting Simics is recommended."
                       % ex)
    (ret, msg) = load_session_from_checkpoint(file)
    return command_return(message = msg, value = ret)

cli.new_command("read-configuration", read_configuration_cmd,
            [arg(filename_t(simpath=True, checkpoint=True), "file"),
             arg(str_t, "prefix", "?", "")],
            type  = ["Configuration"],
            short = "load a saved configuration",
            see_also = ["write-configuration", "load-persistent-state",
                        "record-session"],

            doc = """
Restore simulation state from the state saved in <arg>file</arg>. We refer
to such saved state as a checkpoint. Checkpoints can be created with
the <cmd>write-configuration</cmd> Simics command.

The <arg>prefix</arg> argument can be used to add a name prefix to all objects
loaded from the checkpoint file. The argument can be used to load the same
checkpoint multiple times creating multiple copies of the target machine.

More information about checkpoints can be found in the Configuration
and Checkpointing chapter in the <cite>Simics User's Guide</cite> manual.

The command returns <tt>FALSE</tt> if a recording was present
in the configuration, and playback of it was started. If a recording was
present but a playback is already in progress, the command returns
<tt>NIL</tt>. If the configuration contained no recording, the
command returns <tt>TRUE</tt>.
""")

# called from main.c to handle command line option -c
def cmdline_read_configuration(file):
    try:
        wrap_read_configuration(file)
        (_, msg) = load_session_from_checkpoint(file)
        if msg:
            print(msg)
    except ObjNameError as ex:
        raise simics.SimExc_Break("Configuration not loaded: %s" % ex)
    except cli.CliError as ex:
        raise simics.SimExc_Break(ex.value())
    except simics.SimExc_General as ex:
        raise simics.SimExc_Break("Failed reading configuration: %s " % ex)

def py_SIM_read_configuration(file, prefix = ""):
    try:
        wrap_read_configuration(file, prefix)
        (_, msg) = load_session_from_checkpoint(file)
        if msg:
            print(msg)
    except ObjNameError as ex:
        raise cli.CliError("Configuration not loaded: %s" % ex)
    except simics.SimExc_General as ex:
        raise cli.CliError("Failed reading configuration: %s" % ex)

#
# -------------------- write-configuration --------------------
#

flush_messages_errors = {
    simics.Async_Flush_Pending: 'Internal error: Async_Flush_Pending',
    simics.Async_Flush_Sim_Running: ('Another session in the distributed'
                                     ' simulation is still running.'),
    simics.Async_Flush_Fail: 'Internal error: Async_Flush_Fail',
    simics.Async_Flush_Timeout: 'Distributed message flushing timed out'}

def flush_pending_messages():
    if cli.distributed_simulation():
        td = simics.CORE_process_top_domain()
        status = td.iface.dist_control.initiate_async_flush()
        if status != simics.Async_Flush_Done:
            raise cli.CliError(flush_messages_errors[status])

def check_state_can_be_saved(file, is_independent):
    if os.path.exists(file):
        raise cli.CliError(f"{file} already exists; overwriting is not supported")

    if not is_independent:
        # Check that there are no writable images since otherwise a checkpoint
        # will become inconsistent after any update done to such images.
        rw_images = [img
                     for img in simics.SIM_object_iterator_for_class('image')
                     if any(read_write == "rw"
                            for (_, read_write, *_) in img.files)]
        if rw_images:
            msg = ("Cannot save state since the following images have"
                   " writable files:\n" + "\n".join(img.name for img in rw_images)
                   + "\nPlease save an independent state by passing"
                   " the -independent-checkpoint or -independent-state flag.")
            raise cli.CliError(msg)

def wrap_write_configuration(file, u, raw, is_independent, comment):

    # Checks if one can save simulation state:
    cli.assert_not_running()
    file = SIM_native_path(file)
    check_state_can_be_saved(file, is_independent)
    if any(i.is_wait for i in simics.CORE_get_deferred_transactions_info()):
        simics.SIM_log_error(conf.sim.transactions, 0,
            "Created checkpoint will be incomplete because some model(s)"
            " used in simulation invoked SIM_transaction_wait function"
            " and it has not completed yet. Unfortunately, the simulator"
            " cannot save the whole state in such cases. One can try"
            " the following command to run the simulation until all calls to"
            " the SIM_transaction_wait function are completed:"
            ' "bp.notifier.run-until name = transaction-wait-all-completed".'
            ' See "help transaction-wait-all-completed" for more information.'
            ' The "list-transactions -chains" command can be used to see'
            " information about the transactions that are used in the call(s)"
            " to SIM_transaction_wait function that have not completed yet.")


    flush_pending_messages()

    save_flags = 0

    if u:
        save_flags |= simics.Sim_Save_Image_Uncompressed_Craff
    if raw:
        save_flags |= simics.Sim_Save_Image_Raw

    if is_independent:
        # Independent checkpoint does not depend upon any global
        # checkpoint paths and should not change them.
        save_flags |= simics.Sim_Save_Standalone_Checkpoint
        simics.CORE_save_global_checkpoint_paths()

    try:
        simics.SIM_write_configuration_to_file(file, save_flags)
        checkpoint_info.update_checkpoint_info(file, {'comment' : comment})

    except Exception as ex:
        raise cli.CliError("Failed writing configuration: %s" % ex)

    finally:
        if is_independent:
            simics.CORE_restore_global_checkpoint_paths()

def write_configuration_cmd(file, uflag, save_selection,
                            is_independent_checkpoint, comment):
    (_, _, save_type) = save_selection
    wrap_write_configuration(file, uflag, save_type == "-save-raw",
                             is_independent_checkpoint, comment)

cli.new_command("write-configuration", write_configuration_cmd,
            [arg(filename_t(checkpoint=True), "file"),
             arg(flag_t, "-u"),
             arg((flag_t, flag_t), ("-save-raw", "-save-craff"), "?",
                 (flag_t, 0, "-save-craff")),
             arg(flag_t, "-independent-checkpoint"),
             arg(str_t, "comment", "?", None)],
            type  = ["Configuration"],
            short = "save configuration",
            see_also = ["read-configuration", "save-persistent-state",
                        "record-session"],
            doc = """
Save simulation state to <arg>file</arg>. We refer to such saved state
as a checkpoint. Simulation state can be restored later from a checkpoint
with the <cmd>read-configuration</cmd> command.

Unless the <tt>-independent-checkpoint</tt> flag is specified,
the simulation state is saved incrementally. This allows to save time
and disk space but, as result, created checkpoints
usually depend on the checkpoints which were created earlier as well as on
the files (e.g., disk images) which were used when simulation objects
were created. This means that care should be taken when deleting older
checkpoints.

The <tt>-independent-checkpoint</tt> flag allows to save a completely
independent checkpoint which can be freely moved around and will not
need any files (e.g., checkpoints created earlier) for its use. Also,
checkpoints created later will not depend on such checkpoint.

To add a description to the checkpoint, one can use the <arg>comment</arg>
parameter. The comment is saved in the <file>info</file> file in the checkpoint
bundle.

More information about checkpoints can be found in the Configuration
and Checkpointing chapter in the <cite>Simics User's Guide</cite> manual.

The command flags described below allow to control some subtle
aspects related to created checkpoints and are rarely needed.

The <tt>-save-raw</tt> flag tells Simics to store images in raw format. The
<tt>-save-craff</tt> flag (default) tells Simics to store images
in the craff format.

The <tt>-u</tt> flag tells Simics to store images in the uncompressed craff
format.""")

#
# -------------------- save-persistent-state --------------------
#

def wrap_save_persistent(file, u, raw, is_independent, comment):
    cli.assert_not_running()

    file = SIM_native_path(file)
    save_flags = 0

    if u:
        save_flags |= simics.Sim_Save_Image_Uncompressed_Craff
    if raw:
        save_flags |= simics.Sim_Save_Image_Raw

    if is_independent:
        # Independent checkpoint does not depend upon any global
        # checkpoint paths and should not change them.
        save_flags |= simics.Sim_Save_Standalone_Checkpoint

    try:
        simics.SIM_write_persistent_state(file, None, save_flags)
        checkpoint_info.update_checkpoint_info(file, {'comment' : comment})

    except Exception as ex:
        raise cli.CliError("Failed saving persistent state: %s" % ex)


def save_persistent_cmd(file, uflag, save_selection,
                        is_independent_state, comment):
    (_, _, save_type) = save_selection
    wrap_save_persistent(file, uflag, save_type == "-save-raw",
                         is_independent_state, comment)
    msg = f"State saved {file}"
    return command_return(message=msg, value=None)

cli.new_command("save-persistent-state", save_persistent_cmd,
            [arg(filename_t(checkpoint=True), "file"),
             arg(flag_t, "-u"),
             arg((flag_t, flag_t), ("-save-raw", "-save-craff"), "?",
                 (flag_t, 0, "-save-craff")),
             arg(flag_t, "-independent-state"),
             arg(str_t, "comment", "?", None)],
            type  = ["Configuration", "Disks"],
            short = "save persistent simulator state",
            see_also = ["load-persistent-state", "write-configuration"],
            doc = """
Save the persistent simulator state to <arg>file</arg>. Persistent
data typically includes disk images, NVRAM and flash memory contents
and clock settings, i.e. data that survive reboots. The persistent
state is saved as a standard Simics configuration.

Unless the <tt>-independent-state</tt> flag is specified,
the state is saved incrementally. This allows to save time
and disk space but, as result, the saved state
usually depends on the files which were saved earlier as well as on
the files (e.g., disk images) which were used when simulation objects
were created. This means that care should be taken when deleting files
created previously.

Use the <tt>-independent-state</tt> flag for saving the complete image
data independent of states which were saved earlier, instead of just
the modified data (which is the default).

To add a description to the saved state, use the <arg>comment</arg>
argument. The comment is saved in the <file>info</file> file in the
persistent state bundle.

More information about saving persistent state can be found in the
Configuration and Checkpointing chapter of the <cite>Simics User's
Guide</cite> manual.

The command flags described below allow to control some subtle aspects
related to the format used for the saved state and are rarely needed.

The <tt>-save-raw</tt> flag tells Simics to store images in raw format. The
<tt>-save-craff</tt> flag (default) tells Simics to store images
in the craff format.

The <tt>-u</tt> flag tells Simics to store images in the uncompressed craff
format.""")

# only called from main.c and winsome
def run_command_or_checkpt(filename, args, presets):
    try:
        if is_checkpoint_bundle(pathlib.Path(filename)):
            wrap_read_configuration(filename)
            (_, msg) = load_session_from_checkpoint(filename)
            if msg:
                print(msg)
        else:
            preset_list = targets.sim_params.get_preset_list()
            preset_files = []
            for p in presets:
                f = pathlib.Path(p)
                if not f.is_file():
                    f = targets.targets.get_script_file(p, preset_list)
                preset_files.append([str(f), ""])
            simics.CORE_run_target(filename, "", preset_files,
                                   "", args, False)
    except ObjNameError as ex:
        raise cli.CliError("Configuration not loaded: %s" % ex)
    except Exception as ex:
        if isinstance(ex, (simics.SimExc_Break, simics.SimExc_Stop)):
            raise ex
        raise cli.CliError("%s" % ex)

def load_persistent_cmd(file, prefix):
    cli.assert_not_running()

    try:
        config = simics.VT_get_configuration(file)
    except simics.SimExc_General as ex:
        raise cli.CliError("Failed opening persistent state file: %s" % ex)

    if os.path.isdir(file):
        confdir = file                  # bundle
    else:
        # old (non-bundle) format
        confdir = os.path.dirname(file) or os.path.curdir

    simics.VT_set_restoring_state(True)
    try:
        # File names in the configuration are relative the directory where
        # the config file is located, so we need to go there.
        with_cwd(confdir, lambda: set_persistent_data(config, prefix))
    finally:
        simics.VT_set_restoring_state(False)

cli.new_command("load-persistent-state", load_persistent_cmd,
            [arg(filename_t(simpath=True, checkpoint=True), "file"),
             arg(str_t, "prefix", "?", "")],
            type  = ["Configuration", "Disks"],
            short = "load persistent state",
            see_also = ["save-persistent-state", "read-configuration"],
            doc = """
Load persistent simulator state from <arg>file</arg>. Persistent data
typically includes disk images, NVRAM and flash memory contents and
clock settings, i.e. data that survive reboots. The <arg>prefix</arg>
argument can be used to add a name prefix to all objects in the
persistent state file.
""")

#
# -------------------- list-checkpoints --------------------
#

def list_checkpoints_cmd(root, recursive):

    def get_checkpoint_info(ckpt):
        try:
            info = checkpoint_info.load_checkpoint_info(ckpt)
        except simics.SimExc_General:
            return
        return info['comment'] if info and info['comment'] else ""

    l = []
    for root, dirs, files in os.walk(root):
        for d in dirs:
            ckpt = os.path.join(root, d)
            if cli_impl.is_checkpoint_bundle(ckpt):
                if ckpt.startswith("./"):
                    ckpt = ckpt[2:]
                l += [[ckpt, get_checkpoint_info(ckpt)]]
        if not recursive:
            break

    def print_checkpoints_cmd():
        tw = cli.terminal_width()
        msg = ""
        for (name, comment) in sorted(l):
            msg += name
            cmt = comment.strip()
            if cmt:
                indent = 2
                msg += "\n" + " " * indent
                msg += cli.get_format_string(text = cli_impl.html_escape(cmt),
                                             width = tw - indent - 1,
                                             mode = "text", indent=indent)
            msg += "\n"
        return msg.rstrip()
    return command_verbose_return(value=l, message=print_checkpoints_cmd)

cli.new_command("list-checkpoints", list_checkpoints_cmd,
            [arg(filename_t(dirs=1,exist=1), "path", "?", "."),
             arg(flag_t, "-r")],
            type = ["Configuration", "Files"],
            short = "list checkpoints",
            see_also = ["read-configuration"],
            doc = """
Lists all checkpoints in the <arg>path</arg> directory or in the current
directory if no path argument given. Use <tt>-r</tt> to search for
checkpoints recursively in all sub-directories to <arg>path</arg>.""")

#
#
# -------------------- list-attributes --------------------
#

attr_list = {
    simics.Sim_Attr_Required: "Required",
    simics.Sim_Attr_Optional: "Optional",
    simics.Sim_Attr_Pseudo: "Pseudo"
    }

def list_attributes_impl(obj, classname, attrname, substr, internal, show_desc):
    try:
        cls = simics.SIM_get_class(classname)
    except simics.SimExc_General as ex:
        raise cli.CliError("Failed accessing class %s: %s" % (classname, ex))

    attrs = cls.attributes
    attrs = [a for a in attrs if substr in a[0]]

    def a_val(obj, a):
        if not obj:
            return ""
        try:
            val = simics.SIM_get_attribute(obj, a[0])
        except Exception:
            return "<unreadable attribute>"
        else:
            ret = cli.format_attribute(val)
            return ret if len(ret) < 100 else ret[:100] + " ..."

    def f(attr):
        s = []
        if attr[1] & simics.Sim_Attr_Integer_Indexed:
            s += [ "Integer_Indexed" ]
        if attr[1] & simics.Sim_Attr_String_Indexed:
            s += [ "String_Indexed" ]
        if attr[1] & simics.Sim_Attr_List_Indexed:
            s += [ "List_Indexed" ]
        internal_attr = " Internal" if internal \
            and attr[1] & simics.Sim_Attr_Internal else ""
        persistent_attr = " Persistent" \
            if attr[1] & simics.Sim_Attr_Persistent else ""
        ret = [ attr[0], attr[3], attr_list[int(attr[1] & 0xff)]
                     + persistent_attr + internal_attr, " ".join(s),
                     a_val(obj, attr)]
        if show_desc:
            ret.append(attr[2])

        return ret

    if not internal:
        attrs = [a for a in attrs if not a[1] & simics.Sim_Attr_Internal]

    if attrname == None:
        dl_old = conf.sim.deprecation_level
        if internal:  ##  deprecated attributes should be internal
            conf.sim.deprecation_level = 0
        try:
            attrs_to_print = sorted(map(f, attrs))
            data = sorted([[a[0], a_val(obj, a)] for a in attrs])
        finally:
            conf.sim.deprecation_level = dl_old
        if show_desc:
            props = [(Table_Key_Columns, [
                [(Column_Key_Name, "Attribute")],
                [(Column_Key_Name, "Type")],
                [(Column_Key_Name, "Attr")],
                [(Column_Key_Name, "Flags")],
                [(Column_Key_Name, "Value"),
                 (Column_Key_Alignment, "left")],
                [(Column_Key_Name, "Description"),
                 (Column_Key_Alignment, "left")]])]
        else:
            props = [(Table_Key_Columns, [
            [(Column_Key_Name, "Attribute")],
            [(Column_Key_Name, "Type")],
            [(Column_Key_Name, "Attr")],
            [(Column_Key_Name, "Flags")],
            [(Column_Key_Name, "Value"),
             (Column_Key_Alignment, "left")]])]

        tbl = table.Table(props, attrs_to_print)
        msg = tbl.to_string(rows_printed=0, no_row_column=True)
        return (msg, data)
    else:
        for a in attrs:
            if a[0] == attrname:
                def msg_f():
                    refmanual.help_cmd(f"attribute:{cls.name}.{attrname}")
                    if obj:
                        print(f"   Value: {a_val(obj, a)}")
                        return " " # hack so not "value" is also printed

                return (msg_f, a_val(obj, a))
        # end of for-loop
        return (f"No attribute '{attrname}' was found", None)

def list_attributes_cmd(obj_or_class, attrname, substr, internal, show_desc):
    _, val, arg_name = obj_or_class
    classname = val if arg_name == "class" else val.classname
    obj = val if arg_name == "object" else None

    (msg, data) = list_attributes_impl(obj, classname,
                                       attrname, substr, internal, show_desc)
    return command_verbose_return(msg, data)

def list_attr_name_expander(substr, _, args):
    if not args[0]:
        return []

    ns = args[0][1]
    if args[0][2] == "class":
        try:
            ns = simics.SIM_get_class(ns)
        except simics.SimExc_General:
            return []

    internals = args[3]
    substr = substr if substr else ""
    return [a[0] for a in ns.attributes if substr in a[0]
            and (internals or not a[1] & simics.Sim_Attr_Internal)]

cli.new_command("list-attributes", list_attributes_cmd,
            args  = [
                arg((obj_t("object"), str_t), ("object", "class"),
                    expander = (object_expander(None), conf_class_expander())),
                arg(str_t, "attribute-name", "?", None,
                    expander = list_attr_name_expander),
                arg(str_t, "substr", "?", ""),
                arg(flag_t, "-i"),
                arg(flag_t, "-show-description", "?")],
            type  = ["Configuration", "Help"],
            short = "list all attributes",
            doc = """
Lists all attributes that are registered on a <arg>class</arg> or an
<arg>object</arg>. For every attribute its name, type, attribute type, flags,
and value are listed. See the documentation of the
<fun>SIM_register_attribute</fun> function for more information.
When used in an expression, a list of attribute-name/value pairs is returned.

It is possible to filter on attribute names matching the <arg>substr</arg>
argument.

If an <arg>attribute-name</arg> is given, the description of that particular
attribute will be displayed. If an <arg>object</arg> were given its value is
displayed.

Attributes marked as internal will only be listed when the <tt>-i</tt> flag is
used.

If the <tt>-show-description</tt> flag is used then description for the
attribute is shown.
""")

#
#
# -------------------- list-classes --------------------
#

def get_class_list(substr, module, only_loaded, report_modules,
                   show_port_classes):
    if module:
        class_data = {(cls, mod[2]) for mod in SIM_get_all_modules()
                      for cls in mod[7] if mod[0] == module}
        loaded_classes = {d[0] for d in class_data if d[1]}
        port_classes = set()
        if show_port_classes:
            for c in loaded_classes:
                try:
                    port_classes |= set(simics.VT_get_port_classes(c).values())
                except (LookupError, simics.SimExc_Lookup) as ex:
                    # Module load failure
                    print(ex, file=sys.stderr)
            loaded_classes |= port_classes
        if only_loaded:
            classes = loaded_classes
        else:
            classes = {d[0] for d in class_data} | port_classes
        all_classes = [x for x in classes if obj_cls_name_match(substr, x)]
    else:
        loaded_classes = SIM_get_all_classes()
        classes = set(loaded_classes)
        if not only_loaded:
            classes.update(simics.CORE_get_all_known_module_classes())
        all_classes = [x for x in classes if obj_cls_name_match(substr, x)]

    if not show_port_classes:
        port_classes = {}
        for c in loaded_classes:
            try:
                port_classes[c] = set(simics.VT_get_port_classes(c).values())
            except (LookupError, simics.SimExc_Lookup) as ex:
                # Module load failure
                print(ex, file=sys.stderr)
        filtered_classes = set(all_classes)
        for c in loaded_classes:
            filtered_classes -= port_classes.get(c, set())
        classes = sorted(filtered_classes)
    else:
        classes = sorted(all_classes)

    if not classes:
        return ([], "")

    def class_desc_or_empty_string(class_name):
        if class_name not in loaded_classes:
            return "N/A (module is not loaded yet)"
        desc = simics.VT_get_class_short_desc(class_name)
        if not desc:
            desc = simics.VT_get_class_description(class_name)
        if not desc:
            return ""
        if desc.count("."):
            desc = desc[:desc.index(".")]

        # desc is formatted as-is in the source code, including \n and
        # indentation white-spaces; remove it
        desc = desc.replace("\n", " ")
        desc = re.sub(" {2,}", " ", desc)

        return desc[:50]  ## restrict length of description anyway

    if report_modules:
        cls_mod = {cls: mod[0] for mod in SIM_get_all_modules()
                   for cls in mod[7]}
        class_list = [[cn, cls_mod.get(cn.rsplit(".")[0], "<no module>"),
                       class_desc_or_empty_string(cn)] for cn in classes]
        classes = [[cn, mod] for (cn, mod, _) in class_list]
        title = ['Class', 'Module', 'Short description']
    else:
        class_list = [[cn, class_desc_or_empty_string(cn)] for cn in classes]
        title = ['Class', 'Short description']

    if only_loaded:
        msg = "The following classes have been registered:\n"
    else:
        msg = "The following classes are available:\n"

    props = [(Table_Key_Columns,
              [[(Column_Key_Name, h)] for h in title])]
    tbl = table.Table(props, class_list)
    msg += tbl.to_string(rows_printed=0, no_row_column=True)
    # TODO: simplify when get-class-list is removed
    return (classes, msg)

def list_classes_cmd(substr, module, only_loaded, report_modules,
                     show_port_classes):
    (result, output) = get_class_list(substr, module, only_loaded,
                                      report_modules, show_port_classes)
    return command_verbose_return(output, result)

cli.new_command("list-classes", list_classes_cmd,
            args=[arg(str_t, "substr", "?", ""),
                  arg(str_t, "module", "?", "", expander=module_expander),
                  arg(flag_t, "-l"),
                  arg(flag_t, "-m"),
                  arg(flag_t, "-show-port-classes")],
            type=["Configuration"],
            short="list all configuration classes",
            doc="""
Lists all available configuration classes. It is possible to only
include classes whose name matches a certain sub-string, specified by the
<arg>substr</arg> argument. The <tt>-l</tt> flag will reduce the list to
classes that has been registered by loaded modules. The <tt>-m</tt> flag
extends the output with the name of the module that registered each class.

The <arg>module</arg> argument can be used to only list classes from
the specified module.

Port classes are not included in the list, unless
<tt>-show-port-classes</tt> is specified. Note that this only includes
port classes for classes from loaded modules.

When used in an expression, a list of class names is returned, or a list of
[&lt;class name>, &lt;module name>] pairs, depending on the <tt>-m</tt> flag.
""")

#
# -------------------- list-interfaces --------------------
#

def list_interfaces_impl(cls, substr, include_standard_interfaces):
    if cls:
        try:
            obj_ifaces = simics.VT_get_interfaces(cls)
        except LookupError as ex:
            raise cli.CliError(ex)
    else:
        obj_ifaces = all_known_interfaces()
    obj_ifaces = sorted([x for x in obj_ifaces if substr in x])

    if obj_ifaces:
        props = [
            (table.Table_Key_Columns, [
                [(table.Column_Key_Name, 'Interfaces'),
                 (table.Column_Key_Alignment, "left")]
            ])
        ]
        tbl1  = table.Table(props, [[x] for x in obj_ifaces])
        out1  = tbl1.to_string(rows_printed=0, no_row_column=True)
    else:
        out1 = f"No match for substr '{substr}'"

    if cls:
        seen_ports = set()
        new_ports = {}
        for port, port_cls in simics.VT_get_port_classes(
                cls).items():
            for iface in simics.VT_get_interfaces(port_cls):
                if (not include_standard_interfaces and
                    iface in ('conf_object', 'log_object')):
                    continue
                if not substr in iface:
                    continue
                if port in new_ports:
                    new_ports[port][0].append(iface)
                else:
                    new_ports[port] = [[iface],
                                       simics.VT_get_port_obj_desc(
                                           cls, port)]
                    seen_ports.add(port.split('[')[0])
                    for p in port.split('.'):
                        seen_ports.add(p.split('[')[0])

        arrays = {}
        for port, data in new_ports.items():
            m = re.match(r'^(.+)\[(\d+)\]$', port)
            if not m:
                continue
            ifaces, desc = data
            # This will create a dictionary key with portname without index,
            # all interfaces and the description.
            # This key will keep arrays with different description or different
            # set of interfaces as separate entries in the dict.
            array_key = "%s;%s;%s" % (m[1], ",".join(ifaces), desc)
            if array_key in arrays:
                arrays[array_key][0].append(int(m[2]))
            else:
                arrays[array_key] = [[int(m[2])], m[1], ifaces, desc]

        for indices, port, ifaces, desc in arrays.values():
            for s,e in find_index_ranges(sorted(indices)):
                for i in range(s, e+1):
                    new_ports.pop("%s[%d]" % (port, i))
                new_ports["%s[%d..%d]" % (port, s, e)] = [ifaces,desc]

        old_ports = {}
        for (port, length, iface) in simics.VT_get_port_interfaces(cls):
            if not substr in iface:
                continue
            if port in seen_ports:
                continue
            if length > 1:
                port = port + f"[{length}]"
            if port in old_ports:
                old_ports[port][0].append(iface)
            else:
                # assume same desc is set for all ifaces in the port
                old_ports[port] = [
                    [iface],
                    simics.CORE_get_port_description(cls, port)
                ]
        rows = []
        for (port, [ifaces, desc]) in sorted(new_ports.items()):
            rows.append([port, ', '.join(ifaces), desc])

        header = ['Portname', 'Interfaces', 'Description']
        props  = [
            (table.Table_Key_Columns, [
                [(table.Column_Key_Name, h),
                 (table.Column_Key_Word_Delimiters, " -:,."),
                 (table.Column_Key_Alignment, "left")] for h in header]
             )
        ]
        port_objects_header = [
            (table.Table_Key_Extra_Headers, [
                (table.Extra_Header_Key_Row, [
                    [(table.Extra_Header_Key_Name, "Port objects")]
                ])
            ])
        ]
        tbl2   = table.Table(props + port_objects_header , rows)
        out2   = "" if not rows else "\n\n" + tbl2.to_string(
            rows_printed=0, no_row_column=True)

        old_rows = []
        for (port, [ifaces, desc]) in sorted(old_ports.items()):
            old_rows.append([port, ', '.join(ifaces), desc])

        port_interface_header = [
            (table.Table_Key_Extra_Headers,[
                (table.Extra_Header_Key_Row, [
                    [(table.Extra_Header_Key_Name, "Named port interfaces")]
                ])
            ])
        ]
        tbl3   = table.Table(props + port_interface_header, old_rows)
        out3   = "" if not old_rows else "\n\n" + tbl3.to_string(
            rows_printed=0, no_row_column=True)
    else:
        out2 = " "
        out3 = " "
        new_ports = []
        old_ports = []

    return command_verbose_return(
        message = out1 + out2 + out3,
        value   = [obj_ifaces,
                   [[port] + new_ports[port][0] for port in sorted(new_ports)],
                   [[port] + old_ports[port][0] for port in sorted(old_ports)]])

def list_interfaces_cmd(obj_or_class, *args):
    if obj_or_class is not None:
        (_, val, arg_name) = obj_or_class
        cls = val.classname if arg_name == "object" else val
        return list_interfaces_impl(cls, *args)
    else:
        return list_interfaces_impl(None, *args)

cli.new_command("list-interfaces", list_interfaces_cmd,
            [arg((obj_t("object"), str_t), ("object", "class"), '?', None,
                 expander=(object_expander(None), conf_class_expander())),
             arg(str_t, "substr", "?", ""),
             arg(flag_t, "-include-standard-interfaces")],
            type  = ["Configuration"],
            short = "list all interfaces",
            doc = """
The <cmd>list-interfaces</cmd> command displays a list of all
interfaces implemented by an <arg>object</arg> or a <arg>class</arg>,
all its named port interfaces, as well as all interfaces implemented
by associated port objects.

If neither <arg>object</arg> nor <arg>class</arg> is not specified,
all currently known interfaces will be listed, except port interfaces.

If <arg>substr</arg> is specified, just interfaces whose names contain the
given substring will be listed.

If the flag <tt>-include-standard-interfaces</tt> is supplied all interfaces
implemented by port objects will be listed, including namespace objects.

When used in an expression, the command returns a list with three
elements: a list of interfaces implemented by the object/class,
a list of lists of the form [port, iface1, ..., ifaceN] of port objects
interfaces and a similar list of implemented port interfaces.
""")

def add_module_path_cmd(path):
    simics.SIM_add_module_dir(path)
    simics.SIM_module_list_refresh()

cli.new_command("add-module-directory", add_module_path_cmd,
            [arg(filename_t(dirs = 1), "path")],
            type = ["Configuration", "Files", "Modules"],
            short = "add a directory to the module search path",
            doc = """
Adds a directory, specified by <arg>path</arg>, to the Simics module search
path. This path is used to look for additional modules, that can be used to
extend the functionality of Simics.

Modules from directories added with this command have lower priority
than modules in the project, and higher priority than modules in installed packages
(including prioritized packages).
            """)

#
# -------------------- list-references --------------------
#
def attribute_refs_to_obj(objs, src_obj, attr_name, hide_queue):
    def obj_refs_in(val):
        if isinstance(val, simics.conf_attribute_t):
            val = val.copy()

        if val:
            if isinstance(val, dict):
                return [(f"[{k}]{r}", t) for (k, v) in val.items()
                        for (r, t) in obj_refs_in(v)]
            elif isinstance(val, list):
                return [(f"[{i}]{r}", t) for (i, v) in enumerate(val)
                        for (r, t) in obj_refs_in(v)]
            elif (isinstance(val, simics.conf_object_t)
                  and (objs is None or val in objs)):
                return [("", val)]
        return []

    keep_attr = lambda n: n != "queue" if hide_queue else lambda n: True
    return [(f"{attr_name}{r}", t) for (r, t) in
            obj_refs_in(getattr(src_obj, attr_name)) if keep_attr(attr_name)]


def obtain_refs_from(o, dest_objs, only_list_objects, hide_queue):
    orefs = []
    for a in o.attributes:
        try:
            (name, itype, doc, atype) = a
        except:
            continue

        if (itype & simics.Sim_Attr_Pseudo or not atype
            or ('o' not in atype and
                ('a' not in atype and 'D' not in atype))):
            continue

        orefs += attribute_refs_to_obj(dest_objs, o, name, hide_queue)
        if only_list_objects and orefs:
            break

    return orefs

def construct_object_refs(all_objs, objs, max_len, only_list_objects,
                          only, hide_queue):
    refs = []
    nrefs = 0

    def finished():
        return (max_len is not None
                and ((only_list_objects and len(refs) > max_len) or
                     (not only_list_objects and nrefs > max_len)))

    if only != "-only-outbound":
        # References to "objs"
        for o in all_objs:
            if o in objs:
                continue

            orefs = obtain_refs_from(o, objs, only_list_objects, hide_queue)
            if orefs:
                nrefs += len(orefs)
                refs.append((o, orefs))
                if finished():
                    break

    if finished() or only == "-only-inbound":
        return (refs, nrefs)

    # References from "objs"
    for o in objs:
        orefs = obtain_refs_from(o, None, only_list_objects, hide_queue)
        if orefs:
            nrefs += len(orefs)
            refs.append((o, orefs))
            if finished():
                break
    return (refs, nrefs)

def list_object_references_cmd(obj, namespace, include_ports,
                               max_len, only_list_objects,
                               inorout, hide_queue):
    import itertools

    objs = {obj}
    if include_ports:
        objs |= {simics.SIM_get_object(f"{obj.name}.{p}")
                 for p in simics.VT_get_port_classes(
                         simics.SIM_object_class(obj))}

    if namespace is None:
        ns = cli.current_namespace()
        if ns:
            namespace = simics.SIM_get_object(ns)
    if namespace:
        objlist = itertools.chain(simics.SIM_object_iterator(namespace),
                                  [namespace])
    else:
        objlist = simics.SIM_object_iterator(None)
    (_,_, only) = inorout
    (refs, nrefs) = construct_object_refs(objlist, objs, max_len,
                                          only_list_objects,
                                          only, hide_queue)
    if only_list_objects:
        props = [(Table_Key_Columns,
                  [[(Column_Key_Name, f"Objects referencing {obj.name}")]])]
        rlist = [[o.name] for (o, _) in refs]
    else:
        props = [(Table_Key_Columns,
                  [[(Column_Key_Name, "Object")],
                   [(Column_Key_Name, "Attribute")],
                   [(Column_Key_Name, "Reference")]])]

        rlist = [[o.name, ar, t.name] for (o, r) in refs for (ar, t) in r]

    if max_len is not None:
        rlist = rlist[:max_len]

    tbl = table.Table(props, rlist)
    msg = tbl.to_string(rows_printed=0, no_row_column=True)

    if max_len is not None:
        if only_list_objects and (len(rlist) < len(refs)):
            msg += f"\nFirst {max_len} objects listed."
        elif not only_list_objects and (len(rlist) < nrefs):
            msg += f"\nFirst {max_len} references listed."

    if not rlist:
        msg = ""

    return cli.command_verbose_return(message=msg, value=rlist)


cli.new_command(
    "list-object-references", list_object_references_cmd,
    args = [arg(obj_t('object'), 'object'),
            arg(obj_t('namespace'), 'namespace', '?'),
            arg(flag_t, '-include-ports'),
            arg(poly_t('max-len', uint_t, nil_t), 'max-len', '?', 10),
            arg(flag_t, '-only-list-objects'),
            arg((flag_t, flag_t), ('-only-inbound', '-only-outbound'), "?",
                 (flag_t, 0, None)),
            arg(flag_t, '-hide-queue')],
    short = "list attributes that references 'object'",
    type = ["Configuration"],
    doc = """
List object attributes references from/to <arg>object</arg>.

If the <tt>-include-ports</tt> flag is used, attribute references
from/to port objects belonging to <arg>object</arg> is included in the
list.

By default, every non-pseudo attribute in every object in the
configuration is considered. With the <arg>namespace</arg> argument
the scope of the search can be reduced.

The maximum number of displayed and returned references is controlled
by the <arg>max-len</arg> argument, which defaults to 10. Set the
argument to <tt>NIL</tt> to display/return all references.

By default, object, attribute and referenced object is listed.
With the <tt>-only-list-objects</tt> flag only the objects containing an
attribute referencing <arg>object</arg> is listed.

By default, both inbound and outbound references are listed. If the
<tt>-only-inbound</tt> flag is used, outbound references are omitted. If
<tt>-only-outbound</tt> flag is used, inbound references are omitted.

If the command is used in an expression, the command returns a list of
lists including referencing object, attribute and object referenced.
If the <tt>-only-list-objects</tt> flag is used only referencing
object is included in the list.

If the <tt>-hide-queue</tt> flag is used, then references through
attributes named "queue" are omitted.

Note that the completion time can be very long when run on large platforms.
""")
